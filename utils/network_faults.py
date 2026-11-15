"""Подмена ответов бэкенда для Playwright-тестов: ответ с нужным статусом и обрыв сети.

    # фикстура backend_write_guard (conftest.py) уже вызвала block_unhandled_writes(page)
    faults = NetworkFaults(page)
    sent = faults.respond(CARS, "POST", 200, CAR_ADDED)   # POST /v1/cars получит подменённый 200
    send_and_settle(page, "POST", "/v1/cars", add_car_page.submit)
    require_intercepted(sent, "POST /v1/cars")            # без пойманного запроса проверять нечего
    body = sent[0].post_data_json

Перехват закрытый по умолчанию: block_unhandled_writes регистрирует общий маршрут, который обрывает
любой не-GET запрос к API, не пойманный конкретной подменой. Playwright проверяет маршруты от
последнего зарегистрированного к первому, поэтому общий маршрут регистрируется ПЕРВЫМ, а подмены
после него: они срабатывают раньше, а их route.fallback() (запрос другого метода) доходит до
общего маршрута. Зачем: опечатка в шаблоне подмены иначе отправила бы запрос на настоящий сервер —
тест создал бы машину на общем бэкенде. С защитой запрос обрывается, require_intercepted роняет
тест, на бэкенде ничего не появляется. GET пропускается: чтение данных не меняет.

Перехваченный запрос до бэкенда не доходит: тест читает, что отправил фронт, и не создаёт данных
на общем сервере. Каждый метод возвращает список перехваченных запросов.

Основа — ../QA3553_Phonebook/utils/network_faults.py (шаг 6.3a: respond и abort); страница посредника,
удержание запроса и пропуск одного настоящего запроса перенесены из research/explore_ui_faults.py
(шаг 7d). Отличие от Phonebook — ожидание: там перехват ждут
циклом с page.wait_for_timeout, а в этом проекте фиксированные паузы запрещены. Здесь тест ждёт
событие сети (send_and_settle: запрос ушёл и завершился ответом или сетевой ошибкой), а затем
вызывает require_intercepted.

Почему предикат ожидания не зависит от шаблона page.route: если шаблон маршрута сломается, запрос
дойдёт до общего маршрута защиты и оборвётся, ожидание всё равно завершится, а require_intercepted
увидит пустой список и уронит тест. Ждали бы по тому же шаблону — тест с проверкой «поля в запросе
нет» остался бы зелёным, ничего не проверив.

Запросы с другим методом уходят дальше (route.fallback): на один адрес можно навесить несколько
подмен для разных методов.

Режимы ответа (правило подмены — CLAUDE.md): respond — успешный ответ (только 2xx) с телом, заданным
тестом: проверка отправленного (а) или успех формы из Swagger на пишущий запрос (в); respond_empty —
статус сбоя с пустым телом; respond_recorded — тело настоящего ответа сервера, записанное в research-log.md
под своим Q-ID (source): тело сверяется с json-блоками этой записи дословно; respond_proxy_page — страница
ошибки посредника (nginx), а не ответ приложения; hold — задержка, затем обрыв. Придуманного тела сбоя нет
ни в одном режиме. Все режимы идут через один _intercept: для backend_write_guard и require_intercepted
они одинаковы.

allow_real — не подмена, а исключение из защиты: ОДИН настоящий запрос уходит на сервер, только если его
одобрил предикат теста; всё остальное, что попало в его шаблон, обрывается и роняет тест через
backend_write_guard. Нужен, когда предмет проверки — реакция UI на настоящий ответ, а запрос по виду
пишущий (повтор занятого email, поиск — тоже POST).
"""

import json
import re
import time
import weakref
from collections.abc import Callable
from typing import Literal
from urllib.parse import urlsplit

from playwright.sync_api import Page, Request, Response, Route

from config import PROJECT_ROOT, settings
from utils.preconditions import require

# Адреса API (glob-шаблоны Playwright)
CARS = "**/v1/cars"  # создание машины
LOGIN = "**/v1/user/login/usernamepassword"
PROFILE = "**/v1/user/profile"
REGISTRATION = "**/v1/user/registration/usernamepassword"
SEARCH = "**/v1/cars/search"

# Настоящий ответ бэкенда на успешное создание машины (Q-API-04, Q-UI-05)
CAR_ADDED = {"message": "Car added successfully"}

# Тела настоящих ответов сервера для respond_recorded — одно место истины для тестов и research/explore_ui_faults.py.
# Каждое дословно записано в research-log.md, подраздел «Тело ответа (используется в тестах)» записи
# из комментария; respond_recorded сверяет тело с записью при каждой подмене. timestamp опущен, а не выдуман:
# в логах его значение замаскировано («<ts>»), а фронт читает из тела ошибки только message (Q-UI-37).
# Регистрация с паролем abc123 — Q-API-07 (используется и в Q-UI-40)
REGISTER_400_WEAK_PASSWORD = {
    "status": 400,
    "error": "Bad Request",
    "message": {
        "password": " At least 8 characters; Must contain at least 1 uppercase letter, 1 lowercase letter, "
        "and 1 number; Can contain special characters [@$#^&*!]"
    },
    "path": "/v1/user/registration/usernamepassword",
}
# Регистрация с password = "" — Q-API-16: поля message в теле нет. Форма такой запрос не отправляет
# (пароль обязателен, REQ-UI-REG-01), поэтому в UI этот ответ — только подменой (OBS-15)
REGISTER_400_EMPTY_PASSWORD = {
    "status": 400,
    "error": "Bad Request",
    "path": "/v1/user/registration/usernamepassword",
}
# POST /v1/cars с токеном без точек — Q-API-09 (схема Basic). Тот же message у мусорного токена в UI (Q-UI-34),
# но там записан только message, а полное тело — в Q-API-09
CAR_401_GARBAGE_TOKEN = {
    "status": 401,
    "error": "Unauthorized",
    "message": "JWT strings must contain exactly 2 period characters. Found: 0",
    "path": "/v1/cars",
}
# POST /v1/cars с городом, которого нет в API, из формы — Q-UI-03
CAR_400_CITY_NOT_SUPPORTED = {
    "status": 400,
    "error": "Bad Request",
    "message": "City Beersheba is not supported",
    "path": "/v1/cars",
}
# POST /v1/cars с пустым городом из формы — Q-UI-04
CAR_400_CITY_BLANK = {
    "status": 400,
    "error": "Bad Request",
    "message": {"city": "must not be blank"},
    "path": "/v1/cars",
}

# Страницы посредника для respond_proxy_page: стандартная страница ошибки nginx, когда приложение за ним
# недоступно (Q-UI-28, research/explore_ui_faults.py). Это ответ посредника, а не приложения: тела ответа
# сервера она не изображает. Других страниц в пробах не было — другой статус не подменяется
PROXY_502_HTML = (
    "<html>\r\n<head><title>502 Bad Gateway</title></head>\r\n<body>\r\n"
    "<center><h1>502 Bad Gateway</h1></center>\r\n<hr><center>nginx</center>\r\n</body>\r\n</html>\r\n"
)
PROXY_PAGES = {502: PROXY_502_HTML}

RESEARCH_LOG = PROJECT_ROOT / "docs" / "requirements" / "research-log.md"
_SOURCE_ID = re.compile(r"Q-(?:API|UI)-\d+")
_JSON_BLOCK = re.compile(r"^```json\n(.*?)^```", re.MULTILINE | re.DOTALL)


def require_recorded_source(source: str, body: dict) -> None:
    """Тело respond_recorded дословно записано в research-log.md, в разделе «## <source>».

    Это ошибка автора теста, а не предусловие прогона: ValueError при регистрации подмены, до запроса.
    Без сверки «настоящее» тело ничем не отличалось бы от придуманного: достаточно было бы поменять
    букву в message. Сравнение — как dict после json-парсинга: порядок ключей и пробелы не важны.
    """
    if not isinstance(source, str) or not _SOURCE_ID.fullmatch(source):
        raise ValueError(
            f"respond_recorded: source={source!r} — нужен ID записи research-log.md (Q-API-NN или Q-UI-NN), "
            "откуда взято тело ответа"
        )
    text = RESEARCH_LOG.read_text(encoding="utf-8")
    header = re.search(rf"^## {re.escape(source)}(?!\d).*$", text, re.MULTILINE)
    if header is None:
        raise ValueError(f"respond_recorded: записи {source} нет в {RESEARCH_LOG.name} — тело ответа не из лога")
    # Раздел — до следующего заголовка второго уровня; подразделы «###» входят в него
    next_header = re.search(r"^## ", text[header.end() :], re.MULTILINE)
    section = text[header.end() : header.end() + next_header.start()] if next_header else text[header.end() :]
    recorded = []
    for block in _JSON_BLOCK.findall(section):
        try:
            recorded.append(json.loads(block))
        except json.JSONDecodeError as exc:
            raise ValueError(f"respond_recorded: в записи {source} json-блок не разбирается: {exc}") from exc
    if body not in recorded:
        raise ValueError(
            f"respond_recorded: тела нет в записи {source} ({RESEARCH_LOG.name}): "
            f"{json.dumps(body, ensure_ascii=False)}. "
            f"Json-блоков в записи: {len(recorded)}. Тело берётся дословно из подраздела «Тело ответа "
            "(используется в тестах)» — не правится и не придумывается"
        )


def api_request(method: str, path: str) -> Callable[[Request], bool]:
    """Предикат «это запрос method path к бэкенду» — для page.expect_request и expect_event."""

    def matches(request: Request) -> bool:
        return (
            request.url.startswith(settings.api_url) and request.method == method and urlsplit(request.url).path == path
        )

    return matches


def api_response(method: str, path: str) -> Callable[[Response], bool]:
    """Предикат «это ответ на запрос method path к бэкенду» — для page.expect_response."""
    matches = api_request(method, path)
    return lambda response: matches(response.request)


# Список оборванных защитой запросов каждой страницы: allow_real дописывает туда отклонённые запросы,
# чтобы backend_write_guard уронил тест на teardown. Слабые ссылки: закрытая страница не держится в памяти
_WRITE_GUARDS: "weakref.WeakKeyDictionary[Page, list[Request]]" = weakref.WeakKeyDictionary()


def block_unhandled_writes(page: Page) -> list[Request]:
    """Общий маршрут защиты: обрывает не-GET запросы к API, не пойманные подменами; GET пропускает.

    Вызывается до любых page.route подмен (см. начало модуля). Возвращает список оборванных запросов.
    """
    blocked: list[Request] = []
    _WRITE_GUARDS[page] = blocked

    def handler(route: Route) -> None:
        if route.request.method in ("GET", "HEAD", "OPTIONS"):
            route.fallback()
            return
        blocked.append(route.request)
        route.abort()

    page.route(lambda url: url.startswith(settings.api_url), handler)
    return blocked


def send_and_settle(page: Page, method: str, path: str, action: Callable[[], None]) -> Request:
    """Выполняет действие и ждёт, пока запрос method path уйдёт и завершится — ответом или сетевой ошибкой.

    Ожидание не зависит от шаблона подмены: оборванный защитой запрос тоже его завершает,
    и тест доходит до require_intercepted, а не висит до таймаута.
    """
    with page.expect_request(api_request(method, path)) as request_info:
        action()
    request = request_info.value
    request.response()  # ответ или None, если запрос оборван
    return request


def require_intercepted(requests: list[Request], what: str, count: int = 1) -> None:
    """Предусловие проверки содержимого запроса: запрос действительно перехвачен, и ровно count раз.

    Это require(), а не assert: под known_bug / observation непойманный запрос должен дать FAILED,
    а не спрятаться за ожидаемым падением.
    """
    require(
        len(requests) == count,
        f"Перехват {what}: поймано запросов {len(requests)}, ожидалось {count}. Проверять содержимое запроса "
        "или реакцию на подменённый ответ нельзя: запрос либо не ушёл, либо ушёл мимо перехвата на настоящий сервер",
    )


class HeldRequests:
    """Запросы, удержанные hold: висят без ответа seconds секунд с момента перехвата первого, затем then.

    Обработчик маршрута не ждёт сам: он кладёт route в список и сразу возвращается. Ждёт тест — в wait(),
    и он же отпускает запросы — в finish(). Так проверка «через seconds секунд» идёт, пока запрос ещё висит
    (обрыв раньше проверки показал бы окно ошибки, а не ожидание), а при закрытии страницы ни один
    обработчик не ждёт: прежний вариант проб ждал внутри обработчика, и закрытие страницы во время
    ожидания давало ERROR на teardown. Неотпущенные запросы при закрытии страницы просто забываются.
    """

    def __init__(self, page: Page, seconds: float, then: Literal["abort", "fallback"]):
        self.page = page
        self.seconds = seconds
        self.then = then
        self.requests: list[Request] = []  # все перехваченные запросы, как у остальных режимов
        self._waiting: list[Route] = []
        self._caught_at: float | None = None
        self._finished = False
        self._closed = False
        page.once("close", lambda _: self._forget())

    def _forget(self) -> None:
        # Страница закрыта: отвечать на её запросы нельзя и не нужно
        self._closed = True
        self._waiting.clear()

    def _release(self, route: Route) -> None:
        # fallback, а не continue_: запрос идёт дальше по цепочке маршрутов (в тестах — к backend_write_guard),
        # поэтому и после задержки пишущий запрос не уйдёт на сервер мимо защиты
        if self.then == "abort":
            route.abort()
        else:
            route.fallback()

    def catch(self, route: Route) -> None:
        if self._finished:
            self._release(route)
            return
        if self._caught_at is None:
            self._caught_at = time.monotonic()
        self._waiting.append(route)

    def wait(self) -> None:
        """Ждёт, пока с перехвата первого запроса пройдёт seconds; запросы всё это время висят.

        Вызывается после действия, отправившего запрос (например, после page.expect_request). Событие
        «request» и вызов обработчика маршрута синхронный Playwright может доставить в любом порядке: если
        обработчик ещё не сработал, отсчёт идёт от вызова wait — разница в доли секунды. Что запрос
        действительно удержан, проверяется после ожидания: к этому моменту обработчик сработал наверняка.
        """
        started = self._caught_at if self._caught_at is not None else time.monotonic()
        remaining = started + self.seconds - time.monotonic()
        if remaining > 0:
            # Пауза — это и есть внедрённый сбой: у задержки сервера нет наблюдаемого состояния, которого
            # можно ждать. wait_for_timeout, а не time.sleep: в синхронном Playwright sleep остановил бы
            # обработку событий страницы (маршруты, консоль), и состояние «во время задержки» было бы ложным
            self.page.wait_for_timeout(remaining * 1000)
        require(
            self._caught_at is not None,
            f"Удержание {self.seconds} с: ни один запрос не перехвачен — задержка не внедрена, "
            "состояние «во время ожидания» ничего о ней не говорит",
        )

    def finish(self) -> None:
        """Срок вышел — удержанные запросы обрываются (then="abort") или идут дальше (then="fallback").

        Раньше срока не отпускает: сначала дожидается его, иначе задержка оказалась бы короче заявленной.
        Запросы, пойманные после finish, получают then сразу.
        """
        if self._closed:
            return
        if self._caught_at is not None:
            self.wait()
        self._finished = True
        while self._waiting:
            self._release(self._waiting.pop(0))


class NetworkFaults:
    def __init__(self, page: Page):
        self.page = page

    def _intercept(self, url: str, method: str, action: Callable[[Route], None]) -> list[Request]:
        intercepted: list[Request] = []

        def handler(route: Route) -> None:
            if route.request.method != method:
                route.fallback()
                return
            intercepted.append(route.request)
            action(route)

        self.page.route(url, handler)
        return intercepted

    def respond(self, url: str, method: str, status: int, body: dict) -> list[Request]:
        """Успешный ответ (2xx) с телом, заданным тестом: пункты (а) и (в) правила подмены в CLAUDE.md.

        Статус вне 2xx — ValueError до регистрации маршрута: тело сбоя тестом не придумывается.
        """
        if not 200 <= status <= 299:
            raise ValueError(
                f"respond: статус {status} — не 2xx. Тело сбоя тест не придумывает (правило подмены, CLAUDE.md): "
                "пустое тело — respond_empty(url, method, status), настоящее тело из research-log.md — "
                'respond_recorded(url, method, status, body, source="Q-…")'
            )
        return self._intercept(url, method, lambda route: route.fulfill(status=status, json=body))

    def respond_empty(self, url: str, method: str, status: int) -> list[Request]:
        """Статус сбоя с пустым телом: фронт получает только статус."""
        return self._intercept(url, method, lambda route: route.fulfill(status=status, body=""))

    def respond_recorded(self, url: str, method: str, status: int, body: dict, *, source: str) -> list[Request]:
        """Тело настоящего ответа сервера, записанное в research-log.md; source — ID записи (Q-…).

        Без source, с ID, которого нет в research-log.md, с телом, которого нет среди json-блоков записи,
        или со статусом, не совпадающим с полем status тела, — ValueError до регистрации маршрута.
        """
        require_recorded_source(source, body)
        if "status" in body and body["status"] != status:
            raise ValueError(f"respond_recorded: статус {status}, а в записанном теле {source} status={body['status']}")
        payload = json.dumps(body, separators=(",", ":"))

        def action(route: Route) -> None:
            route.fulfill(status=status, content_type="application/json", body=payload)

        return self._intercept(url, method, action)

    def abort(self, url: str, method: str) -> list[Request]:
        """Обрыв сети: браузер получает сетевую ошибку, ответа нет."""
        return self._intercept(url, method, lambda route: route.abort())

    def respond_proxy_page(self, url: str, method: str, status: int) -> list[Request]:
        """Страница ошибки посредника (text/html) вместо ответа приложения: так отвечает nginx перед бэкендом.

        Статус — только тот, для которого страница записана (PROXY_PAGES), иначе ValueError до регистрации
        маршрута: страница «502 Bad Gateway» со статусом 503 была бы придуманным ответом.
        """
        if status not in PROXY_PAGES:
            raise ValueError(
                f"respond_proxy_page: страницы посредника для статуса {status} нет; есть {sorted(PROXY_PAGES)}"
            )
        page_html = PROXY_PAGES[status]
        return self._intercept(
            url, method, lambda route: route.fulfill(status=status, content_type="text/html", body=page_html)
        )

    def hold(self, url: str, method: str, seconds: float, then: Literal["abort", "fallback"] = "abort") -> HeldRequests:
        """Задержка: запрос висит seconds секунд без ответа, затем обрывается (then="abort").

        then="fallback" — после задержки запрос идёт дальше по цепочке маршрутов (пробы шага 7a: затем
        настоящий запрос). Порядок в тесте: hold → действие → held.wait() → проверка «во время ожидания» →
        held.finish(). Перехваченные запросы — held.requests.
        """
        if then not in ("abort", "fallback"):
            raise ValueError(f'hold: then={then!r} — только "abort" или "fallback"')
        held = HeldRequests(self.page, seconds, then)
        held.requests = self._intercept(url, method, held.catch)
        return held

    def allow_real(self, url: str, method: str, guard: Callable[[Request], bool]) -> list[Request]:
        """Пропускает на настоящий сервер ОДИН запрос method url, если guard(request) истинен.

        Это исключение из backend_write_guard, а не подмена: запрос уходит мимо защиты (continue_).
        Запрос, отклонённый guard, и любой следующий после первого пропущенного обрываются и дописываются
        в список защиты — backend_write_guard уронит тест на teardown; тест, который ждёт пропущенный
        запрос через require_intercepted, упадёт ещё раньше. Без backend_write_guard на странице —
        ValueError: отклонённому запросу некуда было бы громко упасть.
        Возвращает список пропущенных запросов (0 или 1).
        """
        blocked = _WRITE_GUARDS.get(self.page)
        if blocked is None:
            raise ValueError(
                "allow_real: на странице нет backend_write_guard — запросите фикстуру до allow_real, "
                "иначе отклонённый запрос не уронит тест"
            )
        passed: list[Request] = []

        def action(route: Route) -> None:
            request = route.request
            try:
                approved = not passed and guard(request)
            except Exception:  # предикат упал на запросе (например, тело не JSON) — такой запрос не пропускается
                approved = False
            if approved:
                passed.append(request)
                route.continue_()
                return
            blocked.append(request)
            route.abort()

        self._intercept(url, method, action)
        return passed
