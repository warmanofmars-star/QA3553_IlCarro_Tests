import logging
import os
import time
from dataclasses import dataclass

import pytest
import allure
import requests
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.events import EventFiringWebDriver
from selenium.webdriver.support.wait import WebDriverWait
from config import PROJECT_ROOT, settings
from utils.listener import IlCarroListener
from api.car_api import IlCarroAPI
from pages.login_page import LoginPage
from data.data_generator import CarGenerator, UserGenerator
from models.car import Car
from models.user import User
from utils.car_cleanup import CarCleanup, journal_summary, reset_journal
from utils.preconditions import require

logger = logging.getLogger(__name__)

LOG_DIR = PROJECT_ROOT / "logs"

# Сторонние библиотеки на уровне INFO/DEBUG пишут много служебного шума и топят логи тестов
NOISY_LOGGERS = ("urllib3", "selenium", "faker", "asyncio", "charset_normalizer", "filelock")

# Ожидания состояний окружения (секунды). WebDriverWait здесь — просто опрос условия с таймаутом,
# драйвер ему не нужен. Значения сохраняют прежний запас: 5 попыток по 2 с и ~10 опросов видео.
SELENOID_WAKE_TIMEOUT = 10
VIDEO_WAIT_TIMEOUT = 20


def pytest_configure(config):
    """Настраивает логи и журнал фабрики машин для текущего процесса pytest.

    При запуске с xdist тесты выполняют несколько процессов-воркеров; пиши они в один файл,
    строки перемешались бы. Поэтому:
      * обычный запуск             -> logs/pytest.log
      * воркер xdist (gw0, gw1...) -> logs/pytest_gw0.log, logs/pytest_gw1.log, ...
      * главный процесс xdist      -> файла нет: сам он тесты не выполняет
    Явно переданный --log-file имеет приоритет. Формат и уровни — в pytest.ini.

    Главный процесс стартует раньше воркеров, поэтому только он удаляет файлы прошлого прогона
    (логи и журнал фабрики машин): воркер стёр бы записи соседей.
    """
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    # Живые логи в консоли включает настройка из config.py; явный --log-cli-level важнее
    if settings.enable_console_logs and config.getoption("log_cli_level") is None:
        config.option.log_cli_level = "INFO"

    is_xdist_controller = not settings.is_xdist_worker and bool(config.getoption("numprocesses", default=None))

    if not settings.is_xdist_worker:
        LOG_DIR.mkdir(exist_ok=True)
        for old_log in LOG_DIR.glob("*.log"):
            old_log.unlink(missing_ok=True)
        reset_journal()

    if config.option.log_file or is_xdist_controller:
        return
    # workerinput есть только у воркера xdist; так id берётся у самого xdist, а не из окружения
    worker_id = getattr(config, "workerinput", {}).get("workerid")
    config.option.log_file = str(LOG_DIR / (f"pytest_{worker_id}.log" if worker_id else "pytest.log"))


def pytest_terminal_summary(terminalreporter):
    """Итог фабрики машин: сколько создано и сколько удалено. Печатает главный процесс после всех воркеров."""
    if settings.is_xdist_worker:
        return
    summary = journal_summary()
    if summary:
        terminalreporter.write_sep("-", "очистка машин")
        terminalreporter.write_line(summary)


# 👇 Учим pytest понимать флаг --browser_name
def pytest_addoption(parser):
    parser.addoption(
        "--browser_name",
        action="store",
        default="chrome",
        choices=["chrome", "firefox", "edge"],
        help="Browser to run tests in: chrome, firefox, or edge"
    )


@pytest.fixture(scope="session")
def selenoid_hub():
    """Проверяет доступность хаба Selenoid один раз на воркер.

    Без проверки каждый Selenium-тест тратит время на повторные попытки подключения и падает
    одной и той же невнятной ошибкой. Недоступный Selenoid — ошибка окружения, поэтому тест не
    пропускается (skip), а получает ERROR с понятным сообщением. Результат session-фикстуры
    кэшируется, так что остальные тесты воркера падают сразу, без новых запросов к хабу.
    """
    hub_url = settings.selenoid_hub_url
    error = None
    try:
        # В docker compose Selenoid может подниматься чуть дольше контейнера с тестами, поэтому
        # хаб опрашивается до SELENOID_WAKE_TIMEOUT секунд, а не один раз.
        # Достаточно любого HTTP-ответа: нам важно, что по адресу кто-то слушает, а не что вернул /status
        WebDriverWait(
            None, SELENOID_WAKE_TIMEOUT, poll_frequency=0.5, ignored_exceptions=(requests.RequestException,)
        ).until(lambda _: requests.get(f"{hub_url}/status", timeout=3))
    except TimeoutException:
        error = f"не ответил за {SELENOID_WAKE_TIMEOUT} с"
    if error:
        # fail() вызывается вне except: иначе pytest печатает длинную цепочку исключений requests/urllib3
        pytest.fail(
            f"Selenoid недоступен: {hub_url} ({error}). Запусти Selenoid или USE_SELENOID=false.",
            pytrace=False,
        )


@pytest.fixture
def driver(request):  # <--- Добавили request
    # Читаем флаг
    browser_name = request.config.getoption("--browser_name")

    is_headless = settings.headless
    is_ci = settings.is_ci
    use_selenoid = settings.use_selenoid

    session_id = None
    driver_instance = None

    if is_ci:
        # ЗАПУСК В GITHUB ACTIONS (Локально на машине-раннере, если без Docker)
        if browser_name == "firefox":
            options = FirefoxOptions()
            options.add_argument('--headless')
            driver_instance = webdriver.Firefox(options=options)
        elif browser_name == "edge":
            options = EdgeOptions()
            options.add_argument('--headless')
            driver_instance = webdriver.Edge(options=options)
        else:
            options = ChromeOptions()
            options.add_argument('--headless=new')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            driver_instance = webdriver.Chrome(options=options)

    else:
        if use_selenoid:
            # Фикстура подключается только здесь: API- и Playwright-тестам хаб не нужен
            request.getfixturevalue("selenoid_hub")
            logger.info(f"Маршрутизация в изолированный Docker-контейнер (Selenoid). Браузер: {browser_name}")

            # Подготавливаем опции в зависимости от браузера
            if browser_name == "firefox":
                options = FirefoxOptions()
                selenoid_browser = "firefox"
            elif browser_name == "edge":
                options = EdgeOptions()
                selenoid_browser = "MicrosoftEdge"
            else:
                options = ChromeOptions()
                selenoid_browser = "chrome"

            options.set_capability("browserName", selenoid_browser)
            # В Selenoid 1.11+ версия задается через browserVersion (или просто берется default из browsers.json)
            # options.set_capability("browserVersion", "128.0") # <-- Можно закомментировать или убрать жесткую привязку
            options.set_capability("selenoid:options", {
                "enableVNC": True,
                "enableVideo": True,
            })

            # Готовность хаба уже дождалась фикстура selenoid_hub; запуск контейнера браузера
            # Selenoid ждёт сам, поэтому ошибка здесь — настоящая, а не «хаб ещё спит»
            driver_instance = webdriver.Remote(command_executor=settings.selenoid_hub_url, options=options)
            session_id = driver_instance.session_id

        else:
            try:
                if browser_name == "firefox":
                    options = FirefoxOptions()
                    if is_headless:
                        options.add_argument('--headless')
                    driver_instance = webdriver.Firefox(options=options)
                elif browser_name == "edge":
                    options = EdgeOptions()
                    if is_headless:
                        options.add_argument('--headless')
                    options.add_argument('--window-size=1920,1080')
                    driver_instance = webdriver.Edge(options=options)
                else:
                    options = ChromeOptions()
                    if is_headless:
                        options.add_argument('--headless=new')
                    options.add_argument('--window-size=1920,1080')
                    driver_instance = webdriver.Chrome(options=options)
            except Exception as e:
                logger.warning(f"Браузер {browser_name} не запустился. Причина: {e}")
                raise e

    if not is_headless and not use_selenoid:
        driver_instance.maximize_window()
    elif use_selenoid:
        driver_instance.maximize_window()

    driver_instance.set_page_load_timeout(30)
    decorated_driver = EventFiringWebDriver(driver_instance, IlCarroListener())

    yield decorated_driver

    if use_selenoid:
        # Осознанная фиксированная пауза: рекордер Selenoid пишет экран с задержкой, и без неё
        # в видео не попадают последние кадры теста. Состояния «кадры записаны», которого можно
        # дождаться, Selenoid наружу не отдаёт.
        time.sleep(1.5)

    decorated_driver.quit()

    # === ИНТЕГРАЦИЯ ВИДЕО В ALLURE ===
    if use_selenoid and session_id:
        video_path = os.path.join(settings.video_dir, f"{session_id}.mp4")
        video = _read_finished_video(video_path)
        if video is None:
            logger.warning(f"Видео ({browser_name}) не готово за {VIDEO_WAIT_TIMEOUT} с: {video_path}")
        else:
            allure.attach(
                video,
                name=f"Видео прохождения теста ({browser_name})",
                attachment_type=allure.attachment_type.MP4
            )
            logger.info(f"Видео ({browser_name}) прикреплено к отчету")


def _read_finished_video(video_path: str) -> bytes | None:
    """Ждёт, пока Selenoid допишет видео сессии, и возвращает его содержимое (None — не дождались).

    Видео дописывает отдельный контейнер уже после закрытия сессии: файл появляется не сразу и
    какое-то время растёт. Готовым считается непустой файл, размер которого не изменился между
    двумя опросами. Нет файла или он ещё занят записью (PermissionError на Windows) — не готов.
    """
    last_size = -1

    def finished(_):
        nonlocal last_size
        size = os.path.getsize(video_path)
        if size == 0 or size != last_size:
            last_size = size
            return False
        with open(video_path, "rb") as video_file:
            return video_file.read()

    try:
        return WebDriverWait(
            None, VIDEO_WAIT_TIMEOUT, poll_frequency=1, ignored_exceptions=(OSError,)
        ).until(finished)
    except TimeoutException:
        return None

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == 'call' and report.failed:
        # Учитываем, что фикстура может называться driver или authenticated_driver
        driver = item.funcargs.get('driver') or item.funcargs.get('authenticated_driver')
        if driver:
            test_name = item.name.replace("/", "_").replace("::", "_")
            allure.attach(
                driver.get_screenshot_as_png(),
                name=f"Скриншот ошибки: {test_name}",
                attachment_type=allure.attachment_type.PNG
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
class SecondUser(TempUser):
    """«Чужой» пользователь со своей очисткой машин (см. фикстуру second_user)."""

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
    """Создает уникального пользователя через API для полной изоляции тестов."""
    return _register_temp_user("временного пользователя")


@pytest.fixture
def second_user(request):
    """Второй временный пользователь: «чужой» для проверок доступа (BOLA, подмена владельца).

    У него своя очистка машин (поле cleanup): если из-за дефекта машина окажется у него,
    тест регистрирует её номер и здесь, и она не останется на общем бэкенде.
    """
    registered = _register_temp_user("второго пользователя")
    data = SecondUser(
        user=registered.user,
        api=registered.api,
        cleanup=CarCleanup(registered.api, registered.user.email, request.node.nodeid),
    )
    yield data
    data.cleanup.run()


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
    api = temp_user.api

    def _create(*, extra_fields: dict | None = None, **overrides) -> Car:
        car = CarGenerator.get_random_car(**overrides)
        payload = car.to_api_payload() | (extra_fields or {})
        # Регистрируем до запроса: если ответ потеряется, а машина создастся, её всё равно удалят
        car_cleanup.register(car.reg_number)
        with allure.step(f"Setup: создание машины {car.reg_number} через API ({car.city})"):
            response = api.add_car(payload)
            require(
                response.status_code == 200,
                f"Предусловие: машина {car.reg_number} не создана: {response.status_code} {response.text}",
            )
        car_cleanup.mark_created(car.reg_number)
        return car

    return _create


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


def pytest_make_parametrize_id(val):
    # Если параметр — это функция или lambda, возвращаем статичную строку без адреса памяти (0x...),
    # чтобы воркеры pytest-xdist получали одинаковые ID тестов
    if callable(val):
        return "lambda_mutation"
    return str(val)


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
        allure.attach.file(
            video_path,
            name="Видео Playwright",
            attachment_type=allure.attachment_type.MP4
        )
