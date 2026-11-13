import logging
import os
import platform
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import allure
import pytest
from selenium.webdriver.support.events import EventFiringWebDriver

from api.car_api import IlCarroAPI
from config import PROJECT_ROOT, settings
from data.data_generator import CarGenerator, UserGenerator
from drivers.factory import SUPPORTED_BROWSERS, GridUnavailableError, attach_session_video, create_driver, wait_for_grid
from models.car import Car
from models.user import User
from pages.login_page import LoginPage
from utils.car_cleanup import CarCleanup, journal_summary
from utils.listener import IlCarroListener
from utils.log_archive import archive_previous_run
from utils.network_faults import block_unhandled_writes
from utils.preconditions import require
from utils.run_journal import JournalError
from utils.user_journal import user_journal_summary

logger = logging.getLogger(__name__)

LOG_DIR = PROJECT_ROOT / "logs"

# Сторонние библиотеки на уровне INFO/DEBUG пишут много служебного шума и топят логи тестов
NOISY_LOGGERS = ("urllib3", "selenium", "faker", "asyncio", "charset_normalizer", "filelock")


def pytest_configure(config):
    """Настраивает логи и журнал фабрики машин для текущего процесса pytest.

    При запуске с xdist тесты выполняют несколько процессов-воркеров; пиши они в один файл,
    строки перемешались бы. Поэтому:
      * обычный запуск             -> logs/pytest.log
      * воркер xdist (gw0, gw1...) -> logs/pytest_gw0.log, logs/pytest_gw1.log, ...
      * главный процесс xdist      -> файла нет: сам он тесты не выполняет
    Явно переданный --log-file имеет приоритет. Формат и уровни — в pytest.ini.

    Главный процесс стартует раньше воркеров, поэтому только он переносит файлы прошлого прогона
    (логи, журнал фабрики машин и журнал пользователей) в logs/archive/ (utils/log_archive.py):
    воркер унёс бы в архив записи соседей. Воркера узнаём по config.workerinput — его задаёт сам xdist.

    Сбор без запуска (--collect-only) логи не трогает: его вызывают проверки
    scripts/check_ci_split.py и scripts/coverage_matrix.py (в том числе хук pre-commit),
    и они не должны архивировать логи и журнал последнего настоящего прогона.
    """
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    # Живые логи в консоли включает настройка из config.py; явный --log-cli-level важнее
    if settings.enable_console_logs and config.getoption("log_cli_level") is None:
        config.option.log_cli_level = "INFO"

    if config.getoption("collectonly", default=False):
        return

    is_xdist_controller = not settings.is_xdist_worker and bool(config.getoption("numprocesses", default=None))

    if not hasattr(config, "workerinput"):
        archive_previous_run(LOG_DIR)

    if config.option.log_file or is_xdist_controller:
        return
    # workerinput есть только у воркера xdist; так id берётся у самого xdist, а не из окружения
    worker_id = getattr(config, "workerinput", {}).get("workerid")
    config.option.log_file = str(LOG_DIR / (f"pytest_{worker_id}.log" if worker_id else "pytest.log"))


# Итоги журналов прогона: (заголовок, текст, журнал испорчен). Считает pytest_sessionfinish,
# печатает pytest_terminal_summary
JOURNAL_SUMMARIES = pytest.StashKey[list[tuple[str, str, bool]]]()


def _summarize_journals(session) -> None:
    """Считает итоги журналов машин и пользователей; испорченный журнал делает прогон красным.

    Считается в pytest_sessionfinish, а не при печати: код выхода прогона задаёт session.exitstatus,
    и менять его надёжно до того, как pytest начал печатать итог. Испорченная строка журнала —
    не повод молча показать заниженные числа: итог журнала заменяется ошибкой с файлом и строкой.
    """
    sections: list[tuple[str, str, bool]] = []
    for title, summarize in (("очистка машин", journal_summary), ("пользователи", user_journal_summary)):
        try:
            text = summarize()
        except JournalError as exc:
            logger.error(f"Журнал прогона испорчен ({title}): {exc}")
            sections.append((title, f"Журнал испорчен, итог не посчитан: {exc}", True))
            continue
        if text:
            sections.append((title, text, False))
    session.config.stash[JOURNAL_SUMMARIES] = sections
    if any(broken for _, _, broken in sections) and session.exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter):
    """Что прогон оставил на общем бэкенде: машины (создано и удалено) и пользователи (удалить нельзя).

    Печатает главный процесс после всех воркеров. Сбор без запуска (--collect-only) ничего
    не регистрирует и журналы не трогает, поэтому итога у него нет.
    """
    for title, text, broken in terminalreporter.config.stash.get(JOURNAL_SUMMARIES, []):
        terminalreporter.write_sep("-", title, red=broken)
        terminalreporter.write_line(text, red=broken, bold=broken)


# Фикстуры, через которые тест получает браузер Selenium. shared_authenticated_driver зависит от driver,
# но указан явно: если зависимость когда-нибудь поменяется, отбор для CI не развалится молча
SELENIUM_FIXTURES = frozenset({"driver", "authenticated_driver", "shared_authenticated_driver"})
# Фикстура pytest-playwright, через которую тест получает страницу Playwright. context и browser
# сами по себе тест не размечают: страницу тесты проекта берут только через page
PLAYWRIGHT_FIXTURES = frozenset({"page"})


def pytest_collection_modifyitems(items):
    """Ставит маркеры selenium и playwright по тому, какой браузер тест на самом деле получает.

    Решение принимается по фикстурам, а не по ручным маркерам: ручные ui/hybrid/playwright уже
    расходились с тем, что тест на самом деле запускает. fixturenames — полное замыкание
    зависимостей, поэтому тест, получивший браузер через свою фикстуру-обёртку, тоже будет помечен.
    CI делит прогон по маркеру selenium: "selenium" идёт в матрицу браузеров через Grid,
    "not selenium" (API и Playwright) — один раз. Маркер playwright нужен для ручного отбора.
    """
    for item in items:
        fixtures = getattr(item, "fixturenames", ())
        if SELENIUM_FIXTURES.intersection(fixtures):
            item.add_marker(pytest.mark.selenium)
        if PLAYWRIGHT_FIXTURES.intersection(fixtures):
            item.add_marker(pytest.mark.playwright)


def pytest_sessionfinish(session):
    """Считает итоги журналов прогона и пишет блок Environment для Allure: где и как шёл прогон.

    Блок Environment раньше собирал workflow через echo, и в локальном или Docker-отчёте его не было.
    Теперь файл пишет сам фреймворк — в любом запуске с --alluredir. В CI результаты нескольких
    jobs склеивает scripts/merge_allure_results.py: разные значения одного ключа — через «; ».
    """
    if settings.is_xdist_worker:
        return  # пишет только главный процесс, иначе воркеры перезапишут файл друг за другом

    # Сбор без запуска журналы не трогает (см. pytest_configure): в них итог прошлого прогона
    if not session.config.getoption("collectonly", default=False):
        _summarize_journals(session)

    results_dir = session.config.getoption("allure_report_dir", default=None)
    if not results_dir:
        return  # запуск без --alluredir: отчёта не будет, писать некуда

    if settings.use_grid:
        run_mode = "Selenium Grid"
    elif settings.headless or settings.is_ci:
        run_mode = "Local (headless)"
    else:
        run_mode = "Local"

    environment = {
        # Браузер относится только к Selenium-тестам: Playwright всегда берёт свой chromium.
        # Есть ли в прогоне Selenium-тесты, здесь не узнать: с xdist хук выполняет главный процесс,
        # а тесты собирают воркеры
        "SeleniumBrowser": session.config.getoption("--browser_name"),
        "RunMode": run_mode,
        "MarkerFilter": session.config.getoption("markexpr") or "(все тесты)",
        "UiUrl": settings.ui_url,
        "ApiUrl": settings.api_url,
        "Python": platform.python_version(),
        "OS": f"{platform.system()} {platform.release()}",
    }
    results_path = Path(results_dir)
    results_path.mkdir(parents=True, exist_ok=True)
    (results_path / "environment.properties").write_text(
        "".join(f"{key}={value}\n" for key, value in environment.items()),
        encoding="utf-8",
    )


def pytest_addoption(parser):
    parser.addoption(
        "--browser_name",
        action="store",
        default="chrome",
        choices=SUPPORTED_BROWSERS,
        help=f"Браузер для Selenium-тестов: {', '.join(SUPPORTED_BROWSERS)}",
    )


@pytest.fixture(scope="session")
def grid_ready(request):
    """Проверяет готовность Selenium Grid один раз на воркер.

    Без проверки каждый Selenium-тест тратит время на подключение и падает одной и той же
    невнятной ошибкой. Недоступный Grid — ошибка окружения, поэтому тест не пропускается (skip),
    а получает ERROR с понятным сообщением. Ошибку session-фикстуры pytest кэширует, так что
    остальные тесты воркера падают сразу, без новых запросов к хабу.
    """
    error = None
    try:
        wait_for_grid(request.config.getoption("--browser_name"))
    except GridUnavailableError as unavailable:
        error = str(unavailable)
    if error:
        # fail() вызывается вне except: иначе pytest печатает цепочку исключений
        pytest.fail(error, pytrace=False)


@pytest.fixture
def driver(request):
    """Браузер для Selenium-теста. Как именно он создаётся — решает drivers/factory.py."""
    browser = request.config.getoption("--browser_name")
    if settings.use_grid:
        # Фикстура подключается только здесь: API- и Playwright-тестам Grid не нужен
        request.getfixturevalue("grid_ready")
    raw_driver = create_driver(browser)
    session_id = raw_driver.session_id  # по нему после теста находим видео сессии
    decorated_driver = EventFiringWebDriver(raw_driver, IlCarroListener())

    yield decorated_driver

    if settings.use_grid:
        # Осознанная фиксированная пауза: рекордер узла пишет экран с задержкой и останавливается
        # вместе с сессией, поэтому без паузы в видео не попадают последние кадры теста.
        # Состояния «кадры записаны», которого можно дождаться, Grid наружу не отдаёт.
        time.sleep(1.5)
    decorated_driver.quit()

    if settings.use_grid:
        attach_session_video(session_id, browser)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        # Учитываем, что фикстура может называться driver или shared_authenticated_driver
        driver = item.funcargs.get("driver") or item.funcargs.get("shared_authenticated_driver")
        if driver:
            test_name = item.name.replace("/", "_").replace("::", "_")
            allure.attach(
                driver.get_screenshot_as_png(),
                name=f"Скриншот ошибки: {test_name}",
                attachment_type=allure.attachment_type.PNG,
            )


@dataclass
class TempUser:
    """Временный пользователь и API-клиент, уже авторизованный под ним.

    Раньше фикстура возвращала словарь {"user": ..., "api": ...}. С dataclass опечатка в имени
    поля даёт понятную ошибку сразу, а IDE подсказывает поля.
    """

    user: User
    api: IlCarroAPI


@dataclass
class PairUser(TempUser):
    """Участник пары «владелец — чужой» со своей очисткой машин на тест (см. user_pair)."""

    cleanup: CarCleanup


def _register_temp_user(role: str) -> TempUser:
    """Регистрирует нового пользователя через API и возвращает его данные и авторизованный клиент."""
    user = UserGenerator.get_random_user()
    api = IlCarroAPI()

    with allure.step(f"Setup Fixture: Генерация {role} {user.email}"):
        response = api.register(user.email, user.password)
        require(response.status_code == 200, f"Не удалось зарегистрировать {role}: {response.text}")

    return TempUser(user=user, api=api)


@pytest.fixture
def temp_user() -> TempUser:
    """Свежий пользователь на тест — только там, где без нового аккаунта проверку не сделать.

    Состояние пользователя на сервере — только его машины и брони (Q-API-21); вход его не меняет
    и чужих токенов не отзывает (Q-API-19). Свежий пользователь нужен, когда предмет проверки —
    регистрация или выход и токен после выхода; остальным тестам — shared_user (см. CLAUDE.md).
    Пользователей API удалить не умеет: каждый temp_user навсегда остаётся на общем бэкенде.
    """
    return _register_temp_user("временного пользователя")


@pytest.fixture(scope="session")
def shared_user() -> TempUser:
    """Один пользователь на процесс pytest (на воркер xdist): его берут все тесты, кроме выхода и регистрации.

    Пользователей API удалить не умеет: каждый temp_user навсегда остаётся на общем бэкенде.
    Вход состояния пользователя не меняет и выданные раньше токены не отзывает (Q-API-19), поэтому
    вход через форму под этим пользователем не мешает ни токену клиента, ни соседним тестам.
    Тесты находят свои машины по serialNumber, а не по составу всех машин пользователя: тесты
    одного воркера идут последовательно, и свои машины каждый удаляет сам (shared_car_cleanup),
    но машина, которую очистка не смогла удалить, осталась бы у него до конца прогона.
    """
    return _register_temp_user("общего пользователя")


@pytest.fixture(scope="session")
def other_shared_user() -> TempUser:
    """Второй общий пользователь процесса — «чужой» в проверках «владелец и чужой» (см. user_pair).

    Регистрируется лениво: только на воркере, которому достался тест с парой.
    """
    return _register_temp_user("второго общего пользователя")


@pytest.fixture
def user_pair(shared_user, shared_car_cleanup, other_shared_user, request) -> tuple[PairUser, PairUser]:
    """Пара «владелец — чужой», одна на процесс: владелец — shared_user, чужой — other_shared_user.

    Пользователи общие для всех тестов процесса, очистка машин — своя у каждого теста. У владельца это
    shared_car_cleanup: машины, созданные shared_create_car, удаляет та же очистка. Проверки пары
    опираются на номер машины, а не на состав всех машин владельца или чужого.
    """
    owner = PairUser(user=shared_user.user, api=shared_user.api, cleanup=shared_car_cleanup)
    other = PairUser(
        user=other_shared_user.user,
        api=other_shared_user.api,
        cleanup=CarCleanup(other_shared_user.api, other_shared_user.user.email, request.node.nodeid),
    )
    yield owner, other
    other.cleanup.run()


@pytest.fixture
def shared_api(shared_user) -> IlCarroAPI:
    """API-клиент общего пользователя (см. shared_user)."""
    return shared_user.api


@pytest.fixture
def shared_car_cleanup(shared_user, request):
    """Очистка машин общего пользователя после теста.

    Тест, который создаёт машину не через shared_create_car (через UI или «сырым» запросом, чтобы
    проверить сам ответ), регистрирует её номер: shared_car_cleanup.register(car.reg_number).
    """
    cleanup = CarCleanup(shared_user.api, shared_user.user.email, request.node.nodeid)
    yield cleanup
    cleanup.run()


@pytest.fixture
def shared_create_car(shared_user, shared_car_cleanup):
    """Фабрика: создаёт машину через API у общего пользователя и возвращает её данные (Car).

    Фикстура возвращает ФУНКЦИЮ, поэтому тест создаёт сколько угодно машин с нужными полями:

        car = shared_create_car(city="Sderot", price="250")
        car = shared_create_car(extra_fields={"owner": "x@example.com"})  # поля сверх CarDto генератора

    Все созданные машины удаляются после теста (см. shared_car_cleanup). Ответ, отличный от 200, —
    сбой предусловия (require), а не найденный дефект.
    """
    return car_factory(shared_user.api, shared_car_cleanup)


def car_factory(api: IlCarroAPI, cleanup: CarCleanup):
    """Функция создания машины для клиента api: машина регистрируется в cleanup до запроса создания."""

    def _create(*, extra_fields: dict | None = None, **overrides) -> Car:
        car = CarGenerator.get_random_car(**overrides)
        payload = car.to_api_payload() | (extra_fields or {})
        # Регистрируем до запроса: если ответ потеряется, а машина создастся, её всё равно удалят
        cleanup.register(car.reg_number)
        with allure.step(f"Setup: создание машины {car.reg_number} через API ({car.city})"):
            response = api.add_car(payload)
            require(
                response.status_code == 200,
                f"Предусловие: машина {car.reg_number} не создана: {response.status_code} {response.text}",
            )
        cleanup.mark_created(car.reg_number)
        return car

    return _create


@pytest.fixture
def car_cleanup(temp_user, request):
    """Очистка машин temp_user после теста.

    Тест, который создаёт машину не через create_car (через UI или «сырым» запросом, чтобы
    проверить сам ответ), регистрирует её номер: car_cleanup.register(car.reg_number).
    """
    cleanup = CarCleanup(temp_user.api, temp_user.user.email, request.node.nodeid)
    yield cleanup
    cleanup.run()


@pytest.fixture
def create_car(temp_user, car_cleanup):
    """Фабрика: создаёт машину через API у temp_user и возвращает её данные (Car).

    Фикстура возвращает ФУНКЦИЮ, поэтому тест создаёт сколько угодно машин с нужными полями:

        car = create_car(city="Sderot", price="250")
        car = create_car(extra_fields={"owner": "x@example.com"})  # поля сверх CarDto генератора

    Все созданные машины удаляются после теста (см. car_cleanup). Ответ, отличный от 200, —
    сбой предусловия (require), а не найденный дефект.
    """
    return car_factory(temp_user.api, car_cleanup)


@pytest.fixture
def auth_api(temp_user):
    """
    Фикстура-адаптер: берет изолированного API-клиента из песочницы (temp_user)
    и отдает его чистым API-тестам. Никаких изменений в самих тестах не потребуется!
    """
    return temp_user.api


@pytest.fixture
def authenticated_driver(driver, temp_user):
    """Автоматически логинится через UI под свежесозданным временным юзером."""
    with allure.step("Setup Fixture: Автоматическая UI-авторизация (Sandbox)"):
        login_page = LoginPage(driver)
        login_page.open()

        # Берем данные уникального юзера из песочницы
        user = temp_user.user

        login_page.login(user.email, user.password)
        require(login_page.is_logout_button_visible(), "Setup Failed: Кнопка Logout не появилась после авторизации!")

    return driver


@pytest.fixture
def shared_authenticated_driver(driver, shared_user):
    """Браузер Selenium, залогиненный общим пользователем токеном в localStorage, без запроса входа.

    Для тестов, которым вход — только предусловие, а не предмет проверки. Selenium-тесты идут в CI
    в трёх браузерах: свежий пользователь с входом через форму стоил бы нового аккаунта на каждый
    тест в каждом браузере.
    """
    page = LoginPage(driver)
    page.restore_session(shared_user.api.token)
    return driver


def pytest_make_parametrize_id(val):
    # Если параметр — это функция или lambda, возвращаем статичную строку без адреса памяти (0x...),
    # чтобы воркеры pytest-xdist получали одинаковые ID тестов
    if callable(val):
        return "lambda_mutation"
    return str(val)


# Параметры теста с такими именами — секреты (пароли, токены). Правило то же, что у сканера
# отчёта scripts/scan_report_secrets.py: меняешь здесь — меняй и там
SECRET_PARAM_NAME = re.compile(r"password|token|secret", re.IGNORECASE)
SECRET_PLACEHOLDER = "********"


@pytest.fixture(autouse=True)
def _mask_secret_params(request):
    """Маскирует в Allure параметры параметризации, имя которых похоже на секрет.

    allure-pytest записывает значения параметров pytest в result.json после setup, но только
    тех, чьего имени ещё нет среди параметров теста. Фикстура срабатывает в setup раньше: параметр
    с заглушкой и режимом MASKED уже есть, и настоящее значение в файл не попадает.
    Один режим MASKED не помог бы: он скрывает значение только на экране отчёта, а в result.json
    оно остаётся (и при повторном вызове allure.dynamic.parameter режим не обновляется).
    """
    callspec = getattr(request.node, "callspec", None)
    for name in callspec.params if callspec else ():
        if SECRET_PARAM_NAME.search(name):
            allure.dynamic.parameter(name, SECRET_PLACEHOLDER, mode=allure.parameter_mode.MASKED)


@pytest.fixture
def backend_write_guard(page):
    """Перехват закрытый по умолчанию: не-GET запросы к API, не пойманные подменами, обрываются.

    Нужна тестам, которые подменяют пишущие запросы (utils/network_faults.py). Фикстура должна
    сработать ДО подмен теста: маршрут, зарегистрированный раньше, проверяется позже. Поэтому
    фикстуры и тесты с подменами запрашивают её явно, до регистрации своих маршрутов.

    После теста оборванный запрос — ошибка теста (ERROR на teardown), а не запись в логе. Иначе защита
    могла бы тихо оборвать запрос, который фронт начал слать после исправления бага (например, POST
    выхода), и xfail продолжил бы показывать «известный баг»: ошибка teardown строгим xfail не
    прячется. Запрос, ушедший мимо подмены из-за опечатки в шаблоне, роняет тест раньше —
    в require_intercepted.
    """
    blocked = block_unhandled_writes(page)
    yield blocked
    if blocked:
        aborted = "; ".join(f"{request.method} {urlsplit(request.url).path}" for request in blocked)
        pytest.fail(
            f"Защита перехвата оборвала запросы к API мимо подмен: {aborted}. Тест их не ждал: либо шаблон "
            "подмены не совпал, либо фронт шлёт новый пишущий запрос — проверить, что изменилось",
            pytrace=False,
        )


@pytest.fixture
def page(context):
    """
    Переопределяем базовую фикстуру Playwright для авто-сохранения видео в Allure.
    Она прозрачно заменяет стандартный page во всех тестах.
    """
    page = context.new_page()
    yield page

    # 1. Запоминаем путь к видео (если запись была включена флагом --video=on)
    video_path = page.video.path() if page.video else None

    # 2. КРИТИЧЕСКИЙ ШАГ: Принудительно закрываем страницу и контекст.
    # Если этого не сделать, Playwright не успеет финализировать и сохранить .mp4 файл.
    page.close()
    context.close()

    # 3. Прикрепляем готовый файл в Allure
    if video_path and os.path.exists(video_path):
        allure.attach.file(video_path, name="Видео Playwright", attachment_type=allure.attachment_type.MP4)
