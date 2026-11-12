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

Перенесён минимум из ../QA3553_Phonebook/utils/network_faults.py, нужный шагу 6.3a: respond и abort.
Удержание запроса (hold) и остальное — шаг 7. Отличие от Phonebook — ожидание: там перехват ждут
циклом с page.wait_for_timeout, а в этом проекте фиксированные паузы запрещены. Здесь тест ждёт
событие сети (send_and_settle: запрос ушёл и завершился ответом или сетевой ошибкой), а затем
вызывает require_intercepted.

Почему предикат ожидания не зависит от шаблона page.route: если шаблон маршрута сломается, запрос
дойдёт до общего маршрута защиты и оборвётся, ожидание всё равно завершится, а require_intercepted
увидит пустой список и уронит тест. Ждали бы по тому же шаблону — тест с проверкой «поля в запросе
нет» остался бы зелёным, ничего не проверив.

Запросы с другим методом уходят дальше (route.fallback): на один адрес можно навесить несколько
подмен для разных методов.
"""

from collections.abc import Callable
from urllib.parse import urlsplit

from playwright.sync_api import Page, Request, Response, Route

from config import settings
from utils.preconditions import require

# Адреса API (glob-шаблоны Playwright)
CARS = "**/v1/cars"  # создание машины
LOGIN = "**/v1/user/login/usernamepassword"
PROFILE = "**/v1/user/profile"
REGISTRATION = "**/v1/user/registration/usernamepassword"

# Настоящий ответ бэкенда на успешное создание машины (Q-API-04, Q-UI-05)
CAR_ADDED = {"message": "Car added successfully"}

# Тела ошибок: поля как у настоящих ошибок бэкенда (status, error, message, path — Q-API-07),
# текст message написан тестом
_ERROR_TITLES = {400: "Bad Request", 401: "Unauthorized", 500: "Internal Server Error"}


def error_body(status: int, path: str) -> dict:
    return {
        "status": status,
        "error": _ERROR_TITLES.get(status, "Error"),
        "message": "Сбой, подставленный тестом",
        "path": path,
    }


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


def block_unhandled_writes(page: Page) -> list[Request]:
    """Общий маршрут защиты: обрывает не-GET запросы к API, не пойманные подменами; GET пропускает.

    Вызывается до любых page.route подмен (см. начало модуля). Возвращает список оборванных запросов.
    """
    blocked: list[Request] = []

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

    def respond(self, url: str, method: str, status: int, body: dict | None = None) -> list[Request]:
        """Ответ с заданным статусом и телом (по умолчанию — тело ошибки в формате бэкенда)."""

        def action(route: Route) -> None:
            payload = body if body is not None else error_body(status, urlsplit(route.request.url).path)
            route.fulfill(status=status, json=payload)

        return self._intercept(url, method, action)

    def abort(self, url: str, method: str) -> list[Request]:
        """Обрыв сети: браузер получает сетевую ошибку, ответа нет."""
        return self._intercept(url, method, lambda route: route.abort())
