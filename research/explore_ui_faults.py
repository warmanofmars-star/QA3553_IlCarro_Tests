"""
Пробы шага 7a (Q-UI-27 …): как UI ведёт себя при сбоях бэкенда — статусах ошибок, обрыве, задержке.

Каждая ячейка «экран × сбой» внедряет сбой в запрос, который экран реально отправляет (код фронта
и сетевой лог базового прогона), и записывает факты:
  (1) сколько раз сработал маршрут сбоя и на каких URL — 0 означает, что сбой не внедрён, и проба
      падает громко, а не пишет «сообщения нет»;
  (2) базовую линию без сбоя; (3) новый видимый текст относительно базы; (4) кнопку/индикатор и URL;
  (5) есть ли токен в localStorage (только да/нет); (6) сохранились ли введённые данные формы;
  (7) сообщения консоли; (8) восстановление: повтор без сбоя; (9) пишущие запросы, дошедшие до бэкенда.

Правила подмены (CLAUDE.md): только сбои — статус, обрыв, задержка — на эндпоинтах, которые фронт
вызывает; тело сбоя пустое, кроме пробы со страницей посредника (502, text/html) и пробы
register.400.real_body — тело настоящего ответа 400 из лога исследования (Q-API-07). Успешных
ответов скрипт не выдумывает, поэтому у регистрации и формы машины нет настоящей базы «после
отправки»: база — состояние формы перед отправкой, а восстановление — только повторная отправка
(тоже перехваченная).

След на общем бэкенде: не больше одной регистрации (исследовательский пользователь, через
IlCarroAPI.register — он сам пишет журнал пользователей), ни одной машины. До сервера доходят только
входы, поиск и GET; регистрация и POST /v1/cars всегда перехвачены. Защита — block_unhandled_writes
(то же, что делает фикстура backend_write_guard): не-GET запрос к API мимо подмен обрывается,
и ячейка падает. Единственное исключение — отдельная проба настоящего 401 (ячейка car.real401):
POST /v1/cars пропускается к серверу, только если у него мусорный токен и пустой город — машина
не может быть создана ни при каком ответе (Q-UI-04: без города — 400; Q-UI-13: мусорный токен — 401).

Email исследовательского пользователя хранится в research/evidence/explore_ui_faults_user.txt
(в git не попадает): повторный запуск входит этим пользователем, а не регистрирует нового.
Токены не печатаются; FactLog дополнительно маскирует JWT и email.

Ячейки доработки (второй прогон 7a-2): search.stale500.other_city — после сбоя поиска по другому
городу (сам поиск подменён, на сервер уходят только поиски Sderot), search.401.user — 401 на поиске
под пользователем, register.400.real_body — настоящее тело 400 с message-объектом.

Запуск: python research/explore_ui_faults.py --run 7a
Только отдельные ячейки: python research/explore_ui_faults.py --run 7a2 --only search.500,login.abort
Лог: research/evidence/explore_ui_faults_run7a.log. Код выхода 1 — хотя бы одна проба упала.
"""

import argparse
import json
import sys
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

# Скрипт запускается как файл: research/ (common) и корень проекта (api, utils, config) надо добавить
# в путь до импорта, поэтому импорты ниже стоят после кода — E402 подавлен намеренно
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import (  # noqa: E402
    Browser,
    BrowserContext,
    Page,
    Request,
    Route,
    expect,
    sync_playwright,
)
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError  # noqa: E402

from api.car_api import IlCarroAPI  # noqa: E402
from common import EVIDENCE_DIR, REG, ROOT, VALID_PASSWORD, FactLog, new_email, new_serial, short  # noqa: E402
from config import settings  # noqa: E402
from utils import run_journal  # noqa: E402
from utils.network_faults import (  # noqa: E402
    CARS,
    LOGIN,
    PROFILE,
    REGISTER_400_WEAK_PASSWORD,
    REGISTRATION,
    SEARCH,
    NetworkFaults,
    api_request,
    block_unhandled_writes,
)

UI = settings.ui_url
API = settings.api_url
ACTION_TIMEOUT_MS = 30_000
# Сколько ждать, пока экран успокоится после ответа: задержка 35 с плюс настоящий запрос к Heroku
SETTLE_MS = 120_000
DELAYS = (5, 35)
CITY = "Sderot"  # малое число машин (Q-API-14): ответ поиска лёгкий
# Без точек: парсер JWT отклоняет такой токен (Q-UI-13), пользователя за ним нет
GARBAGE_TOKEN = "probe-garbage-token"
# Стандартная страница ошибки nginx — так отвечает посредник, когда приложение за ним недоступно
PROXY_502_HTML = (
    "<html>\r\n<head><title>502 Bad Gateway</title></head>\r\n<body>\r\n"
    "<center><h1>502 Bad Gateway</h1></center>\r\n<hr><center>nginx</center>\r\n</body>\r\n</html>\r\n"
)
# Город сбойного поиска в search.stale500.other_city: есть в списке CityAutocomplete. Запрос с ним до сервера
# не доходит (500 подменой, иначе обрыв) — на общем бэкенде ищем только CITY
OTHER_CITY = "Haifa"
# Настоящий ответ 400 регистрации с message-объектом (Q-API-07): тело — utils/network_faults.py, там же
# объяснено, почему нет timestamp. Строка — только для лога пробы; respond_recorded шлёт те же байты
REGISTER_400_REAL_BODY = json.dumps(REGISTER_400_WEAK_PASSWORD, separators=(",", ":"))
USER_FILE = EVIDENCE_DIR / "explore_ui_faults_user.txt"
LOGS_DIR = ROOT / "logs"
CAR_FIELDS = {
    "manufacture": "ProbeMake",
    "model": "ProbeModel",
    "year": "2020",
    "seats": "4",
    "carClass": "Economy",
    "serialNumber": None,  # заполняется новым номером
    "pricePerDay": "150",
}

LOG: FactLog  # создаётся в main(): имя лога зависит от --run
BASE: dict[str, "Snap"] = {}  # базовые линии экранов (2)
SUMMARY: list[list[str]] = []  # строки сводной таблицы ячеек
FAILED: list[str] = []
REAL_REQUESTS: list[str] = []  # запросы, ушедшие на сервер, по всем ячейкам
WRITES_TO_SERVER: list[str] = []  # пишущие запросы, ушедшие на сервер (ожидается только car.real401)


class ProbeFailure(Exception):
    """Проба не может утверждать факт: сбой не внедрён или запрос ушёл мимо подмены."""


# ---------------------------------------------------------------- пользователь


@dataclass
class ProbeUser:
    email: str
    token: str = field(repr=False)


_USER: list[ProbeUser] = []


def probe_user() -> ProbeUser:
    """Один исследовательский пользователь на все запуски: регистрация — только если его ещё нет."""
    if _USER:
        return _USER[0]
    api = IlCarroAPI()
    if USER_FILE.exists():
        email = USER_FILE.read_text(encoding="utf-8").strip()
        REG.label_user(email)
        resp = api.login(email, VALID_PASSWORD)
        REAL_REQUESTS.append("POST /v1/user/login/usernamepassword (API: вход исследовательского пользователя)")
        if resp.status_code != 200 or not api.token:
            raise ProbeFailure(f"вход исследовательского пользователя не удался: HTTP {resp.status_code}")
        LOG.fact("исследовательский пользователь: уже зарегистрирован раньше, вход через API")
    else:
        email = new_email("fault")
        REG.label_user(email)
        resp = api.register(email, VALID_PASSWORD)  # IlCarroAPI сам пишет журнал пользователей
        REAL_REQUESTS.append("POST /v1/user/registration/usernamepassword (API: исследовательский пользователь)")
        if resp.status_code != 200 or not api.token:
            raise ProbeFailure(f"регистрация исследовательского пользователя не удалась: HTTP {resp.status_code}")
        REG.users_created += 1
        USER_FILE.write_text(email, encoding="utf-8")
        LOG.fact("исследовательский пользователь: зарегистрирован через API (записан в журнал пользователей)")
    REG.tokens[email] = api.token
    _USER.append(ProbeUser(email, api.token))
    return _USER[0]


def journal_counts() -> tuple[int, int]:
    """Записей в журналах прогона logs/: (пользователи, машины фабрики). Только чтение."""
    users = run_journal.read_records(LOGS_DIR, "registered_users", frozenset())
    cars = run_journal.read_records(LOGS_DIR, "car_factory", frozenset())
    return len(users), len(cars)


# ---------------------------------------------------------------- сбои


class Held:
    """Удержанные запросы: висят без ответа, пока скрипт не вызовет release()."""

    def __init__(self) -> None:
        self.routes: list[Route] = []
        self.released = False

    def release(self) -> None:
        # fallback, а не continue_: запрос проходит дальше по цепочке маршрутов (разрешение чтения
        # и входа, затем защита), поэтому и после задержки пишущий запрос не уйдёт на сервер
        self.released = True
        while self.routes:
            self.routes.pop(0).fallback()


class ProbeFaults(NetworkFaults):
    """Сбои, которых нет в utils/network_faults: страница посредника и задержка.

    Пустое тело (respond_empty) и тело настоящего ответа (respond_recorded) — из utils (шаг 7b).
    Счётчик срабатываний — тот же _intercept.
    """

    def respond_proxy_page(self, url: str, method: str, status: int) -> list[Request]:
        return self._intercept(
            url, method, lambda route: route.fulfill(status=status, content_type="text/html", body=PROXY_502_HTML)
        )

    def hold(self, url: str, method: str) -> tuple[list[Request], Held]:
        held = Held()

        def action(route: Route) -> None:
            if held.released:
                route.fallback()
            else:
                held.routes.append(route)

        return self._intercept(url, method, action), held


def allow_reads_and_logins(page: Page, real: list[str]) -> None:
    """Регистрируется ПОСЛЕ защиты: поиск (POST, но чтение) и вход уходят на сервер, GET — тоже.

    Остальные не-GET запросы проходят дальше, к защите, и обрываются.
    """

    def handler(route: Route) -> None:
        request = route.request
        path = urlsplit(request.url).path
        if request.method == "POST" and path in ("/v1/cars/search", "/v1/user/login/usernamepassword"):
            real.append(f"POST {path}")
            REAL_REQUESTS.append(f"POST {path}")
            route.continue_()
            return
        if request.method == "GET":
            real.append(f"GET {path}")
            REAL_REQUESTS.append(f"GET {path}")
        route.fallback()

    page.route(lambda url: url.startswith(API), handler)


# ---------------------------------------------------------------- экраны


def restore_session(page: Page, token: str) -> None:
    page.goto(f"{UI}/login")
    page.evaluate(
        "(t) => { localStorage.setItem('token', t); localStorage.setItem('tokenType', 'Bearer'); }",
        token,
    )


def pick_dates(page: Page) -> None:
    """Диапазон: сегодня — завтра (два клика в календаре)."""
    page.click("#dates")
    page.locator(".rdrDayToday").click()
    tomorrow = date.today() + timedelta(days=1)
    if tomorrow.month != date.today().month:
        page.click(".rdrNextButton")
    page.locator(f"button.rdrDay:not(.rdrDayPassive):not(.rdrDayDisabled) >> text='{tomorrow.day}'").first.click()


def submit_button(page: Page):
    return page.locator("form button[type=submit]")


def button_state(page: Page) -> str:
    button = submit_button(page)
    if not button.count():
        return "кнопки отправки нет"
    state = "недоступна" if button.is_disabled() else "доступна"
    return f"кнопка {button.inner_text()!r}, {state}"


def filled(page: Page, selector: str) -> bool:
    locator = page.locator(selector)
    return bool(locator.count()) and bool(locator.input_value())


def not_loading(page: Page) -> None:
    expect(submit_button(page)).not_to_have_text("Loading...", timeout=SETTLE_MS)


def dismiss_dialog(page: Page) -> None:
    """Закрывает окно ошибки (кнопка OK), если оно есть: окно перекрывает форму."""
    ok = page.locator("[role=dialog] button", has_text="OK")
    if ok.count():
        ok.first.click()


# Поиск (гость)
def search_prepare(page: Page) -> None:
    page.goto(f"{UI}/search")
    page.fill("#city", CITY)
    page.locator(f'[data-testid="city-option"][data-value="{CITY}"]').first.click()
    pick_dates(page)
    page.locator("h1.title").click()


def search_form(page: Page) -> str:
    city = page.input_value("#city")
    return (
        f"город {'сохранён' if city == CITY else repr(city)}; даты {'заполнены' if filled(page, '#dates') else 'пусто'}"
    )


def search_outcome(page: Page) -> str:
    return f"карточек {page.locator('a.car-container').count()}"


def choose_city(page: Page, city: str) -> None:
    page.fill("#city", city)
    page.locator(f'[data-testid="city-option"][data-value="{city}"]').first.click()


def pick_range(page: Page, start: date, end: date) -> None:
    """Диапазон дат в календаре. Как и pick_dates, считает, что календарь открывается на текущем месяце."""
    page.click("#dates")
    shown = (date.today().year, date.today().month)
    for day in (start, end):
        if (day.year, day.month) != shown:
            page.click(".rdrNextButton")
            shown = (day.year, day.month)
        page.locator(f"button.rdrDay:not(.rdrDayPassive):not(.rdrDayDisabled) >> text='{day.day}'").first.click()
    page.locator("h1.title").click()


def search_state(page: Page) -> str:
    """Форма и выдача поиска: город, строка дат, URL, карточки."""
    url = urlsplit(page.url)
    return (
        f"город {page.input_value('#city')!r}; даты {page.input_value('#dates')!r}; URL {url.path}?{url.query}; "
        f"{search_outcome(page)}"
    )


def card_links(page: Page) -> list[str]:
    """Ссылки карточек (по serialNumber): чтобы сравнить наборы, не печатая номера."""
    return page.locator("a.car-container").evaluate_all("els => els.map(e => e.getAttribute('href'))")


# Поиск под исследовательским пользователем (вход токеном)
def search_user_prepare(page: Page) -> None:
    restore_session(page, probe_user().token)
    search_prepare(page)


# Вход (гость)
def login_prepare(page: Page) -> None:
    page.goto(f"{UI}/login")
    page.fill("[name=username]", probe_user().email)
    page.fill("[name=password]", VALID_PASSWORD)


def login_form(page: Page) -> str:
    email = "заполнен" if filled(page, "[name=username]") else "пусто"
    password = "заполнен" if filled(page, "[name=password]") else "пусто"
    return f"email {email}; пароль {password}"


def logout_link(page: Page) -> str:
    return f"«Log out» {'есть' if page.get_by_role('button', name='Log out').count() else 'нет'}"


# Регистрация (гость, запрос всегда перехвачен)
def register_prepare(page: Page) -> None:
    page.goto(f"{UI}/register")
    email = new_email("fake")
    REG.label_user(email)
    page.fill("[name=firstName]", "Probe")
    page.fill("[name=lastName]", "Fault")
    page.fill("[name=username]", email)
    page.fill("[name=password]", VALID_PASSWORD)
    page.check("#terms-of-use")


def register_form(page: Page) -> str:
    names = ("firstName", "lastName", "username", "password")
    kept = sum(filled(page, f"[name={name}]") for name in names)
    terms = "отмечено" if page.is_checked("#terms-of-use") else "снято"
    return f"заполнено полей {kept} из 4; согласие {terms}"


# Форма машины (вход токеном, POST /v1/cars всегда перехвачен, кроме car.real401)
def fill_car_form(page: Page, *, with_city: bool = True) -> None:
    if with_city:
        page.fill("#city", CITY)
        page.locator(f'[data-testid="city-option"][data-value="{CITY}"]').first.click()
    for name, value in CAR_FIELDS.items():
        page.fill(f"[name={name}]", value or new_serial("RF"))
    page.select_option("[name=fuel]", label="Petrol")


def car_prepare(page: Page) -> None:
    restore_session(page, probe_user().token)
    page.goto(f"{UI}/let-car-work")
    fill_car_form(page)


def car_settle(page: Page) -> None:
    expect(submit_button(page)).to_be_enabled(timeout=SETTLE_MS)


def car_form(page: Page) -> str:
    kept = sum(filled(page, f"[name={name}]") for name in CAR_FIELDS)
    city = "сохранён" if filled(page, "#city") else "пусто"
    return f"заполнено полей {kept} из {len(CAR_FIELDS)}; город {city}"


# Профиль (вход токеном; GET /v1/user/profile нет в Swagger и на бэкенде — DISC-05)
def profile_prepare(page: Page) -> None:
    restore_session(page, probe_user().token)


def profile_trigger(page: Page) -> None:
    page.goto(f"{UI}/profile")


def profile_settle(page: Page) -> None:
    expect(page.get_by_text("Загрузка...")).to_have_count(0, timeout=SETTLE_MS)


def profile_indicator(page: Page) -> str:
    return f"индикатор «Загрузка...» {'есть' if page.get_by_text('Загрузка...').count() else 'нет'}"


def profile_outcome(page: Page) -> str:
    return f"main: {short(page.locator('main').inner_text().strip(), 120)}"


@dataclass(frozen=True)
class Screen:
    key: str
    title: str
    method: str
    path: str
    pattern: str
    write: bool  # пишущий запрос: до сервера не доходит, успешного ответа нет
    prepare: Callable[[Page], None]
    trigger: Callable[[Page], None]
    settle: Callable[[Page], None]
    form: Callable[[Page], str]
    outcome: Callable[[Page], str]
    indicator: Callable[[Page], str] = button_state
    retrigger: Callable[[Page], None] | None = None


SCREENS = {
    "search": Screen(
        "search", "Поиск /search (гость)", "POST", "/v1/cars/search", SEARCH, False,
        search_prepare, lambda p: submit_button(p).click(), not_loading, search_form, search_outcome,
    ),
    "login": Screen(
        "login", "Вход /login (гость)", "POST", "/v1/user/login/usernamepassword", LOGIN, False,
        login_prepare, lambda p: submit_button(p).click(), not_loading, login_form, logout_link,
    ),
    "register": Screen(
        "register", "Регистрация /register (гость)", "POST", "/v1/user/registration/usernamepassword", REGISTRATION,
        True, register_prepare, lambda p: submit_button(p).click(), not_loading, register_form, logout_link,
    ),
    "car": Screen(
        "car", "Форма машины /let-car-work (вход токеном)", "POST", "/v1/cars", CARS, True,
        car_prepare, lambda p: submit_button(p).click(), car_settle, car_form, logout_link,
    ),
    "profile": Screen(
        "profile", "Профиль /profile (вход токеном)", "GET", "/v1/user/profile", PROFILE, False,
        profile_prepare, profile_trigger, profile_settle, lambda p: "полей ввода нет", profile_outcome,
        indicator=profile_indicator, retrigger=lambda p: p.reload(),
    ),
    # Базы нет: состояние «до отправки» снимает сама ячейка (search.401.user)
    "search_user": Screen(
        "search_user", "Поиск /search (вход токеном)", "POST", "/v1/cars/search", SEARCH, False,
        search_user_prepare, lambda p: submit_button(p).click(), not_loading, search_form,
        lambda p: f"{search_outcome(p)}; {logout_link(p)}",
    ),
}  # fmt: skip


# ---------------------------------------------------------------- снимок состояния


@dataclass
class Snap:
    lines: list[str]
    messages: list[str]
    indicator: str
    url: str
    token: bool
    redirect: str | None
    form: str
    outcome: str
    console: list[str]  # консоль и окна браузера на момент снимка, без последующего повтора
    dialogs: list[str]


def snap(probe: "Probe", screen: Screen) -> Snap:
    page = probe.page
    body = page.locator("body").inner_text()
    url = urlsplit(page.url)
    messages = [
        " / ".join(x.strip() for x in text.splitlines() if x.strip())
        for text in page.locator("[role=dialog], [role=alert], [role=status]").all_inner_texts()
    ]
    return Snap(
        lines=[x.strip() for x in body.splitlines() if x.strip()],
        messages=messages,
        indicator=screen.indicator(page),
        url=url.path + (f"?{url.query}" if url.query else ""),
        token=page.evaluate("() => localStorage.getItem('token') !== null"),
        redirect=page.evaluate("() => localStorage.getItem('postLoginRedirect')"),
        form=screen.form(page),
        outcome=screen.outcome(page),
        console=list(probe.console),
        dialogs=list(probe.dialogs),
    )


def diff(base: Snap | None, after: Snap) -> tuple[str, str]:
    """Новые и исчезнувшие строки видимого текста относительно базы."""
    if base is None:
        return "база не снята в этом запуске", ""
    base_set, after_set = set(base.lines), set(after.lines)
    new = [x for x in after.lines if x not in base_set]
    gone = [x for x in base.lines if x not in after_set]
    return short(new, 260), short(gone, 160)


# ---------------------------------------------------------------- ячейка


@dataclass
class Probe:
    context: BrowserContext
    page: Page
    blocked: list[Request]
    real: list[str] = field(default_factory=list)
    console: list[str] = field(default_factory=list)
    api_log: list[str] = field(default_factory=list)
    dialogs: list[str] = field(default_factory=list)


def listed(items: list, limit: int) -> str:
    """Список для лога; пустой — «нет» (short() печатает его как «[]»)."""
    return short(items, limit) if items else "нет"


def console_text(message) -> str:
    """Текст сообщения консоли. Объект ошибки Playwright отдаёт именем класса (у минифицированного axios — «L»),
    поэтому для первого аргумента берутся name и message самой ошибки."""
    try:
        detail = (
            message.args[0].evaluate("e => (e && e.message) ? `${e.name}: ${e.message}` : null")
            if message.args
            else None
        )
    except Exception:  # аргумент уже недоступен (страница ушла) — хватит текста
        detail = None
    return detail or message.text


def api_path(url: str) -> str:
    return urlsplit(url).path


def open_probe(browser: Browser) -> Probe:
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.set_default_timeout(ACTION_TIMEOUT_MS)
    # Защита — первой: маршрут, зарегистрированный раньше, проверяется позже (utils/network_faults)
    probe = Probe(context, page, block_unhandled_writes(page))
    allow_reads_and_logins(page, probe.real)

    def on_console(message) -> None:
        if message.type in ("error", "warning"):
            probe.console.append(f"{message.type}: {console_text(message)}")

    def on_dialog(dialog) -> None:
        probe.dialogs.append(f"{dialog.type}: {dialog.message}")
        dialog.dismiss()

    def on_response(response) -> None:
        if response.url.startswith(API):
            probe.api_log.append(f"{response.request.method} {api_path(response.url)} → HTTP {response.status}")

    def on_failed(request) -> None:
        if request.url.startswith(API):
            probe.api_log.append(f"{request.method} {api_path(request.url)} → сбой {request.failure}")

    page.on("console", on_console)
    page.on("pageerror", lambda error: probe.console.append(f"pageerror: {error}"))
    page.on("dialog", on_dialog)
    page.on("response", on_response)
    page.on("requestfailed", on_failed)
    return probe


def send(probe: Probe, screen: Screen, action: Callable[[Page], None]) -> Request:
    """Действие экрана и запрос, который оно отправило (ожидание не зависит от шаблона подмены)."""
    with probe.page.expect_request(api_request(screen.method, screen.path), timeout=ACTION_TIMEOUT_MS) as info:
        action(probe.page)
    return info.value


def finish(request: Request) -> str:
    """Ждёт завершения запроса: ответ или сетевая ошибка."""
    response = request.response()
    return f"HTTP {response.status}" if response else f"сбой {request.failure}"


def check_guard(probe: Probe) -> None:
    """То же, что backend_write_guard после теста: оборванный пишущий запрос — падение пробы."""
    if probe.blocked:
        aborted = "; ".join(f"{r.method} {api_path(r.url)}" for r in probe.blocked)
        raise ProbeFailure(
            f"защита перехвата оборвала запросы к API мимо подмен: {aborted}. Подмена не сработала — "
            "без защиты запрос ушёл бы на общий бэкенд"
        )


def check_intercepted(sent: list[Request], what: str) -> str:
    if not sent:
        raise ProbeFailure(
            f"маршрут сбоя «{what}» не сработал ни разу: сбой не внедрён, факты ячейки ничего не говорят о сбое"
        )
    return f"срабатываний {len(sent)}; URL: {short(sorted({api_path(r.url) for r in sent}), 120)}"


def report(cell: str, facts: dict[str, str], summary: list[str]) -> None:
    for key, value in facts.items():
        LOG.fact(f"{key}: {value}")
    SUMMARY.append([cell, *summary])


def common_facts(probe: Probe, screen: Screen, after: Snap, pre: Snap | None = None) -> dict[str, str]:
    """pre — состояние перед отправкой: база экрана, если отдельной базы у него нет (search_user)."""
    new, gone = diff(BASE.get(screen.key) or pre, after)
    writes = [r for r in probe.real if not r.startswith("GET")]
    return {
        "(2) база": describe_base(screen, pre),
        "(3) новый видимый текст относительно базы": new,
        "(3) исчез относительно базы": gone or "—",
        "(3) окна и сообщения (role=dialog/alert/status)": listed(after.messages, 200),
        "(3) window.alert/confirm": listed(after.dialogs, 120),
        "(4) индикатор и URL": f"{after.indicator}; URL {after.url}; {after.outcome}",
        "(5) токен в localStorage": f"{'да' if after.token else 'нет'}; postLoginRedirect={after.redirect!r}",
        "(6) введённые данные": after.form,
        "(7) консоль": f"{len(after.console)}: {short(after.console, 300)}" if after.console else "0",
        "(9) вход и поиск на сервер (разрешены)": listed(writes, 160),
        "(9) оборвано защитой": str(len(probe.blocked)),
        "API-запросы ячейки": short(probe.api_log, 300),
    }


def describe_base(screen: Screen, pre: Snap | None = None) -> str:
    base = BASE.get(screen.key)
    if base is None and pre is not None:
        token = "да" if pre.token else "нет"
        return f"состояние перед отправкой: {pre.outcome}; {pre.indicator}; токен {token}; {pre.form}"
    if base is None:
        return "не снята в этом запуске"
    if screen.write:
        return f"форма перед отправкой (успешного ответа нет — не подменяем): {base.indicator}; {base.form}"
    token = "да" if base.token else "нет"
    return f"{base.outcome}; {base.indicator}; токен {token}; сообщения {listed(base.messages, 120)}"


def summary_row(after: Snap, recovery: str, probe: Probe, count: str) -> list[str]:
    messages = short(after.messages, 90) if after.messages else "нет"
    return [
        count.split(";")[0],
        messages,
        f"{after.indicator}; {after.outcome}",
        "да" if after.token else "нет",
        after.form,
        str(len(after.console)),
        recovery,
        str(len(probe.blocked)),
    ]


# ---------------------------------------------------------------- виды ячеек


def base_cell(browser: Browser, screen: Screen) -> None:
    probe = open_probe(browser)
    try:
        screen.prepare(probe.page)
        if screen.write:
            BASE[screen.key] = snap(probe, screen)
            LOG.fact(
                "база — форма перед отправкой: успешный ответ на запись подменять нельзя (CLAUDE.md), "
                "настоящую запись бюджет следа не допускает"
            )
            report(f"{screen.key}.base", {"снимок": short(BASE[screen.key].__dict__, 400)}, ["—"] * 8)
            return
        started = time.monotonic()
        request = send(probe, screen, screen.trigger)
        result = finish(request)
        screen.settle(probe.page)
        elapsed = time.monotonic() - started
        after = snap(probe, screen)
        BASE[screen.key] = after
        check_guard(probe)
        facts = {
            "(1) маршрут сбоя": "нет (база)",
            "ответ сервера": f"{result}; от действия до спокойного экрана {elapsed:.1f} с",
            "(3) окна и сообщения": listed(after.messages, 200),
            "(4) индикатор и URL": f"{after.indicator}; URL {after.url}; {after.outcome}",
            "(5) токен в localStorage": f"{'да' if after.token else 'нет'}; postLoginRedirect={after.redirect!r}",
            "(6) введённые данные": after.form,
            "(7) консоль": f"{len(after.console)}: {short(after.console, 300)}" if after.console else "0",
            "API-запросы ячейки": short(probe.api_log, 300),
        }
        report(f"{screen.key}.base", facts, ["база", listed(after.messages, 90), f"{after.indicator}; "
               f"{after.outcome}", "да" if after.token else "нет", after.form, str(len(after.console)),
               f"{result}, {elapsed:.1f} с", str(len(probe.blocked))])  # fmt: skip
    finally:
        probe.context.close()


def fault_cell(
    browser: Browser, screen: Screen, kind: str, status: int | None = None, *, name: str | None = None
) -> None:
    """Сбой одного вида на запросе экрана: kind — status | recorded | proxy502 | abort."""
    probe = open_probe(browser)
    try:
        screen.prepare(probe.page)
        pre = snap(probe, screen)
        faults = ProbeFaults(probe.page)
        if kind == "recorded":
            sent = faults.respond_recorded(
                screen.pattern, screen.method, 400, REGISTER_400_WEAK_PASSWORD, source="Q-API-07"
            )
            what = f"{screen.method} {screen.path} → 400, тело настоящего ответа (Q-API-07): {REGISTER_400_REAL_BODY}"
        elif kind == "status":
            sent = faults.respond_empty(screen.pattern, screen.method, status)
            what = f"{screen.method} {screen.path} → {status}, тело пустое"
        elif kind == "proxy502":
            sent = faults.respond_proxy_page(screen.pattern, screen.method, 502)
            what = f"{screen.method} {screen.path} → 502, страница nginx (text/html)"
        else:
            sent = faults.abort(screen.pattern, screen.method)
            what = f"{screen.method} {screen.path} → обрыв"
        request = send(probe, screen, screen.trigger)
        result = finish(request)
        screen.settle(probe.page)
        after = snap(probe, screen)
        check_guard(probe)
        count = check_intercepted(sent, what)

        # (8) восстановление
        dismiss_dialog(probe.page)
        if screen.write:
            # Без сбоя повторить нельзя: запись не должна дойти до сервера. Проверяется только, что форма
            # позволяет отправить ещё раз; повтор перехвачен тем же сбоем
            again = send(probe, screen, screen.trigger)
            finish(again)
            screen.settle(probe.page)
            recovery = f"повторная отправка ушла (перехвачено всего {len(sent)}); нормальный результат не проверялся"
        else:
            probe.page.unroute(screen.pattern)
            try:
                again = send(probe, screen, screen.retrigger or screen.trigger)
            except PlaywrightTimeoutError:
                # Повтор не отправил запрос (например, защищённый маршрут увёл на вход) — это факт ячейки
                gone = snap(probe, screen)
                token = "да" if gone.token else "нет"
                recovery = (
                    f"повтор не отправил запрос за {ACTION_TIMEOUT_MS // 1000} с: URL {gone.url}; токен {token}; "
                    f"{gone.indicator}"
                )
            else:
                real = finish(again)
                screen.settle(probe.page)
                recovered = snap(probe, screen)
                recovery = f"без сбоя: {real}; {recovered.outcome}; токен {'да' if recovered.token else 'нет'}"
        check_guard(probe)

        facts = {
            "(1) маршрут сбоя": f"{what}; {count}; браузер получил: {result}",
            "(5) до отправки": f"токен {'да' if pre.token else 'нет'}; {pre.outcome}",
        }
        facts.update(common_facts(probe, screen, after, pre))
        facts["(8) восстановление"] = recovery
        cell = name or f"{screen.key}.{status or kind}"
        report(cell, facts, summary_row(after, recovery, probe, count))
    finally:
        probe.context.close()


def delay_cell(browser: Browser, screen: Screen, seconds: int) -> None:
    """Задержка: запрос удерживается seconds секунд, затем уходит на настоящий сервер."""
    probe = open_probe(browser)
    try:
        screen.prepare(probe.page)
        sent, held = ProbeFaults(probe.page).hold(screen.pattern, screen.method)
        started = time.monotonic()
        request = send(probe, screen, screen.trigger)
        at_start = snap(probe, screen)
        # Пауза — это и есть внедрённый сбой: у задержки сервера нет наблюдаемого состояния, которого
        # можно ждать. wait_for_timeout, а не time.sleep: в синхронном Playwright sleep остановил бы
        # обработку событий страницы (маршруты, консоль), и снимок «во время задержки» был бы ложным
        probe.page.wait_for_timeout(seconds * 1000)
        during = snap(probe, screen)
        failed_during = [x for x in probe.api_log if "сбой" in x]
        check_intercepted(sent, f"{screen.method} {screen.path} → задержка {seconds} с")
        held.release()
        result = finish(request)
        screen.settle(probe.page)
        elapsed = time.monotonic() - started
        after = snap(probe, screen)
        check_guard(probe)

        facts = {
            "(1) маршрут сбоя": f"задержка {seconds} с; срабатываний {len(sent)}; затем настоящий запрос: {result}",
            "в начале задержки": f"{at_start.indicator}; {at_start.outcome}; "
            f"сообщения {listed(at_start.messages, 120)}",
            f"через {seconds} с": f"{during.indicator}; {during.outcome}; сообщения {listed(during.messages, 120)}; "
            f"новый текст относительно начала: {diff(at_start, during)[0]}",
            "фронт сам прервал запрос во время задержки": listed(failed_during, 120),
            "от действия до спокойного экрана": f"{elapsed:.1f} с",
        }
        facts.update(common_facts(probe, screen, after))
        recovery = f"после отпускания: {result}; {after.outcome}"
        facts["(8) восстановление"] = recovery
        report(f"{screen.key}.delay{seconds}", facts, summary_row(after, recovery, probe, f"{len(sent)}"))
    finally:
        probe.context.close()


def search_stale_cell(browser: Browser) -> None:
    """Сбой после успешного поиска: что остаётся на экране от прошлой выдачи."""
    screen = SCREENS["search"]
    probe = open_probe(browser)
    try:
        screen.prepare(probe.page)
        first = finish(send(probe, screen, screen.trigger))
        screen.settle(probe.page)
        before = snap(probe, screen)
        sent = ProbeFaults(probe.page).respond_empty(SEARCH, "POST", 500)
        result = finish(send(probe, screen, screen.trigger))
        screen.settle(probe.page)
        after = snap(probe, screen)
        check_guard(probe)
        count = check_intercepted(sent, "POST /v1/cars/search → 500 после успешного поиска")
        probe.page.unroute(SEARCH)
        real = finish(send(probe, screen, screen.trigger))
        screen.settle(probe.page)
        recovered = snap(probe, screen)
        recovery = f"без сбоя: {real}; {recovered.outcome}"
        facts = {
            "(1) маршрут сбоя": f"500, тело пустое; {count}; браузер получил: {result}",
            "до сбоя (настоящий поиск)": f"{first}; {before.outcome}",
            "(3) новый текст относительно экрана до сбоя": diff(before, after)[0],
            "(3) исчез относительно экрана до сбоя": diff(before, after)[1] or "—",
        }
        facts.update(common_facts(probe, screen, after))
        facts["(8) восстановление"] = recovery
        report("search.stale500", facts, summary_row(after, recovery, probe, count))
    finally:
        probe.context.close()


def search_other_city_cell(browser: Browser) -> None:
    """Настоящий поиск CITY, затем другой город и другие даты — этот поиск 500, затем повтор с CITY."""
    screen = SCREENS["search"]
    probe = open_probe(browser)
    foreign: list[str] = []

    def only_main_city(route: Route) -> None:
        # Регистрируется до маршрута сбоя, значит проверяется после него: сюда доходит поиск, который
        # подмена не поймала. На общем бэкенде ищем только CITY — остальное обрывается, ячейка падает
        body = route.request.post_data_json or {}
        if body.get("city") != CITY:
            foreign.append(f"POST /v1/cars/search city={body.get('city')!r}")
            route.abort()
            return
        route.fallback()

    try:
        probe.page.route(SEARCH, only_main_city)
        screen.prepare(probe.page)
        first = finish(send(probe, screen, screen.trigger))
        screen.settle(probe.page)
        before = snap(probe, screen)
        before_state, before_links = search_state(probe.page), card_links(probe.page)
        first_card = probe.page.locator("a.car-container").first.inner_text() if before_links else ""

        today = date.today()
        choose_city(probe.page, OTHER_CITY)
        pick_range(probe.page, today + timedelta(days=2), today + timedelta(days=3))
        changed_state = search_state(probe.page)
        sent = ProbeFaults(probe.page).respond_empty(SEARCH, "POST", 500)
        request = send(probe, screen, screen.trigger)
        result = finish(request)
        screen.settle(probe.page)
        after = snap(probe, screen)
        after_state, after_links = search_state(probe.page), card_links(probe.page)
        count = check_intercepted(sent, f"POST /v1/cars/search ({OTHER_CITY}) → 500, тело пустое")
        if foreign:
            raise ProbeFailure(f"поиск не по {CITY} дошёл до защиты и оборван: {foreign}")
        check_guard(probe)
        cards_text = " ".join(probe.page.locator("a.car-container").all_inner_texts())
        sent_body = request.post_data_json or {}
        marks = [
            CITY,
            OTHER_CITY,
            probe.page.input_value("#dates"),
            *(str(sent_body.get(k)) for k in ("startDate", "endDate")),
        ]
        in_cards = [m for m in marks if m and m in cards_text]

        # unroute снимает все обработчики шаблона, в том числе защиту «только CITY» — она ставится заново
        probe.page.unroute(SEARCH)
        probe.page.route(SEARCH, only_main_city)
        choose_city(probe.page, CITY)
        pick_dates(probe.page)
        probe.page.locator("h1.title").click()
        again_state = search_state(probe.page)
        real = finish(send(probe, screen, screen.trigger))
        screen.settle(probe.page)
        recovered_links = card_links(probe.page)
        same = "да" if sorted(recovered_links) == sorted(before_links) else "нет"
        recovery = (
            f"повтор с {CITY} (форма: {again_state}): {real}; {search_outcome(probe.page)}; "
            f"набор карточек как у первого поиска: {same}"
        )
        if foreign:
            raise ProbeFailure(f"поиск не по {CITY} дошёл до защиты и оборван: {foreign}")
        check_guard(probe)

        facts = {
            "(1) маршрут сбоя": f"500, тело пустое; {count}; тело перехваченного запроса: "
            f"{json.dumps(request.post_data_json, ensure_ascii=False)}; браузер получил: {result}",
            "до сбоя (настоящий поиск)": f"{first}; {before_state}",
            "форма перед сбойным поиском": changed_state,
            "после сбоя": after_state,
            "набор карточек после сбоя тот же, что после первого поиска": "да"
            if sorted(after_links) == sorted(before_links) and after_links
            else f"нет (до {len(before_links)}, после {len(after_links)})",
            "видимый текст первой карточки": repr(first_card),
            f"в тексте карточек после сбоя есть город или даты ({', '.join(map(repr, marks))})": listed(in_cards, 80),
            "(3) новый текст относительно экрана до сбоя": diff(before, after)[0],
            "(3) исчез относительно экрана до сбоя": diff(before, after)[1] or "—",
            "поиски не по основному городу, оборванные защитой": str(len(foreign)),
        }
        facts.update(common_facts(probe, screen, after))
        facts["(8) восстановление"] = recovery
        report("search.stale500.other_city", facts, summary_row(after, recovery, probe, count))
    finally:
        probe.context.close()


def car_real_401_cell(browser: Browser) -> None:
    """Настоящий 401 без подмены: мусорный токен, форма без города — машина не может быть создана."""
    screen = SCREENS["car"]
    probe = open_probe(browser)
    passed: list[Request] = []

    def passthrough(route: Route) -> None:
        request = route.request
        body = request.post_data_json or {}
        if (
            request.method == "POST"
            and request.header_value("authorization") == f"Bearer {GARBAGE_TOKEN}"
            and body.get("city") == ""
        ):
            passed.append(request)
            WRITES_TO_SERVER.append("POST /v1/cars (car.real401: мусорный токен, пустой город)")
            route.continue_()
            return
        route.fallback()  # всё остальное — к защите: оборвёт и уронит пробу

    try:
        probe.page.route(CARS, passthrough)
        restore_session(probe.page, GARBAGE_TOKEN)
        probe.page.goto(f"{UI}/let-car-work")
        fill_car_form(probe.page, with_city=False)
        before = snap(probe, screen)
        request = send(probe, screen, screen.trigger)
        response = request.response()
        screen.settle(probe.page)
        after = snap(probe, screen)
        check_guard(probe)
        if not passed:
            raise ProbeFailure("POST /v1/cars не прошёл к серверу: настоящего 401 нет, проба ничего не показала")
        message = ""
        status = f"сбой {request.failure}"
        if response:
            status = f"HTTP {response.status}"
            try:
                message = str(response.json().get("message", ""))
            except Exception:  # тело не JSON — так и записываем
                message = f"тело не JSON: {short(response.text(), 80)}"
        shown = bool(message) and any(message in line for line in after.lines)
        facts = {
            "(1) запрос": f"POST /v1/cars пропущен к серверу: {len(passed)}; ответ сервера {status}; "
            f"message={short(message, 120)!r}",
            "(3) текст сервера на экране": "да" if shown else "нет",
            "(3) новый видимый текст относительно формы до отправки": diff(before, after)[0],
            "(3) окна и сообщения": listed(after.messages, 200),
            "(4) индикатор и URL": f"{after.indicator}; URL {after.url}; {after.outcome}",
            "(5) токен в localStorage": f"{'да' if after.token else 'нет'}; postLoginRedirect={after.redirect!r}",
            "(6) введённые данные": after.form,
            "(7) консоль": f"{len(after.console)}: {short(after.console, 300)}" if after.console else "0",
            "(8) восстановление": "неприменимо: нормальный результат — создание машины, бюджет следа его не допускает",
            "(9) пишущих запросов на сервер": f"{len(passed)} (намеренно, машина не может быть создана)",
            "API-запросы ячейки": short(probe.api_log, 300),
        }
        report("car.real401", facts, [f"пропущено {len(passed)}", listed(after.messages, 90),
               f"{after.indicator}; {status}", "да" if after.token else "нет", after.form,
               str(len(after.console)), "неприменимо", str(len(passed))])  # fmt: skip
    finally:
        probe.context.close()


# ---------------------------------------------------------------- список ячеек


def cells() -> dict[str, tuple[str, Callable[[Browser], None]]]:
    s = SCREENS
    table: dict[str, tuple[str, Callable[[Browser], None]]] = {}
    plan = {
        "search": [("status", 401), ("status", 500), ("abort", None), ("proxy502", None)],
        "login": [("status", 401), ("status", 500), ("abort", None)],
        "register": [("status", 400), ("status", 409), ("status", 401), ("status", 500), ("abort", None)],
        "car": [("status", 401), ("status", 500), ("abort", None)],
        "profile": [("status", 401), ("status", 500), ("abort", None)],
    }
    for key, faults in plan.items():
        screen = s[key]
        table[f"{key}.base"] = (f"{screen.title}: база без сбоя", lambda b, sc=screen: base_cell(b, sc))
        for kind, status in faults:
            name = f"{key}.{status or kind}"
            label = f"{screen.title}: {f'ответ {status}, тело пустое' if status else kind}"
            table[name] = (label, lambda b, sc=screen, k=kind, st=status: fault_cell(b, sc, k, st))
        if not screen.write:  # задержка — только на чтении и входе
            for seconds in DELAYS:
                table[f"{key}.delay{seconds}"] = (
                    f"{screen.title}: задержка {seconds} с, затем настоящий запрос",
                    lambda b, sc=screen, sec=seconds: delay_cell(b, sc, sec),
                )
    table["search.stale500"] = ("Поиск: 500 после успешного поиска", search_stale_cell)
    table["search.stale500.other_city"] = (
        f"Поиск: {CITY} (200), затем {OTHER_CITY} и другие даты → 500, затем повтор с {CITY}",
        search_other_city_cell,
    )
    table["search.401.user"] = (
        "Поиск под пользователем (вход токеном): ответ 401, тело пустое",
        lambda b: fault_cell(b, s["search_user"], "status", 401, name="search.401.user"),
    )
    table["register.400.real_body"] = (
        "Регистрация: ответ 400 с телом настоящего ответа сервера (Q-API-07, message — объект)",
        lambda b: fault_cell(b, s["register"], "recorded", 400, name="register.400.real_body"),
    )
    table["car.real401"] = ("Форма машины: настоящий 401 (мусорный токен), без подмены", car_real_401_cell)
    return table


def print_summary() -> None:
    LOG.header("СВОДКА", "Ячейки «экран × сбой»")
    LOG.line(
        "| Ячейка | (1) срабатываний | (3) окна/сообщения | (4) индикатор; результат | (5) токен | (6) форма "
        "| (7) консоль | (8) восстановление | (9) пишущих мимо подмены |"
    )
    LOG.line("|---|---|---|---|---|---|---|---|---|")
    for row in SUMMARY:
        LOG.line("| " + " | ".join(cell.replace("|", "/") for cell in row) + " |")


def main() -> None:
    global LOG
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--run", default="1")
    parser.add_argument("--only", default="", help="ячейки через запятую, например search.500,login.abort")
    args = parser.parse_args()
    LOG = FactLog(f"explore_ui_faults_run{args.run}")
    table = cells()
    selected = [x.strip() for x in args.only.split(",") if x.strip()] or list(table)
    unknown = [x for x in selected if x not in table]
    if unknown:
        raise SystemExit(f"неизвестные ячейки: {unknown}; есть: {', '.join(table)}")

    LOG.line(f"# explore_ui_faults, {datetime.now().isoformat(timespec='seconds')}")
    users_before, cars_before = journal_counts()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                for name in selected:
                    title, run = table[name]
                    LOG.header(name, title)
                    try:
                        run(browser)
                    except ProbeFailure as exc:
                        FAILED.append(name)
                        LOG.line(f"!!! ПРОБА УПАЛА ({name}): {exc}")
                    except Exception:
                        FAILED.append(name)
                        LOG.line(f"!!! ПРОБА УПАЛА ({name}) с исключением:\n{traceback.format_exc()}")
            finally:
                browser.close()
    finally:
        print_summary()
        users_after, cars_after = journal_counts()
        LOG.header("ИТОГ", "След на бэкенде")
        LOG.fact(f"регистраций (журнал logs/registered_users_*.jsonl): +{users_after - users_before}")
        LOG.fact(f"машин (журнал logs/car_factory_*.jsonl): +{cars_after - cars_before}; скрипт машин не создаёт")
        LOG.fact(f"пишущих запросов на сервер мимо подмен: {len(WRITES_TO_SERVER)} {WRITES_TO_SERVER}")
        kinds = {x: REAL_REQUESTS.count(x) for x in sorted(set(REAL_REQUESTS))}
        LOG.fact(f"запросы на сервер (вход, поиск, GET): {kinds}")
        LOG.fact(f"упавших проб: {len(FAILED)} {FAILED}")
        LOG.fact(f"дата и время прогона: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if FAILED:
        sys.exit(1)


if __name__ == "__main__":
    main()
