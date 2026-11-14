"""
Сбои бэкенда и сессия (шаг 7b): REQ-UI-SESSION-03 (неудачный вход и регистрация не создают сессию),
REQ-UI-SESSION-01 (401 удаляет token там, где он был), REQ-UI-CAR-05 (текст сервера при 401 не
показывается) и наблюдение OBS-05 (после 401 на поиске «Log out» остаётся).

Сбой внедряется в запрос, который экран действительно отправляет (Q-UI-27): статус ошибки из Swagger
(400, 401, 500) или обрыв. Тело сбоя — пустое (respond_empty) или тело настоящего ответа из лога
исследования (respond_recorded, источник — Q-ID). Пишущие запросы (регистрация, POST /v1/cars) — только
подменой: до бэкенда они не доходят, а запрос мимо подмены обрывает backend_write_guard. Чтение
и вход — настоящим ответом, если он достижим без следа на общем бэкенде: неверный пароль общего
пользователя даёт настоящий 401 и состояния пользователя не меняет (Q-API-19). Поиск под пользователем
подменён целиком: 401 на поиске настоящим ответом получить нельзя, не испортив токен.

Пользователи — по правилу CLAUDE.md: общий shared_user (вход токеном в localStorage, без запроса входа),
новых пользователей тесты не заводят. Email регистрации фальшивый (example.com): запрос перехвачен,
пользователь не создаётся.
"""

from dataclasses import dataclass
from urllib.parse import urlsplit

import allure
import pytest
from playwright.sync_api import Page, expect

from data.data_generator import CarGenerator, SearchDataGenerator, UserGenerator
from data.observations import observation
from pages.pw_add_car_page import PwAddCarPage
from pages.pw_base_page import PwBasePage
from pages.pw_login_page import PwLoginPage
from pages.pw_registration_page import PwRegistrationPage
from pages.pw_search_page import PwSearchPage
from utils.network_faults import (
    CAR_401_GARBAGE_TOKEN,
    CARS,
    LOGIN,
    REGISTER_400_WEAK_PASSWORD,
    REGISTRATION,
    SEARCH,
    NetworkFaults,
    api_response,
    require_intercepted,
    send_and_settle,
)
from utils.preconditions import require

pytestmark = [pytest.mark.ui, pytest.mark.regression]

LOGIN_PATH = "/v1/user/login/usernamepassword"
REGISTRATION_PATH = "/v1/user/registration/usernamepassword"
SEARCH_PATH = "/v1/cars/search"
CARS_PATH = "/v1/cars"


def _assert_no_session(page_object: PwBasePage, after: str) -> None:
    """Сессии нет: ни токена в localStorage, ни «Log out» в навигации (REQ-UI-SESSION-03)."""
    with allure.step("Проверка: в localStorage нет token, в навигации нет «Log out»"):
        # Значение токена в сообщение не попадает: важно только, есть ли он
        assert page_object.local_storage_item("token") is None, f"После {after} в localStorage появился token"
        expect(PwLoginPage(page_object.page).logout_btn, f"После {after} в навигации есть «Log out»").to_be_hidden()


def _current_path(page: Page) -> str:
    """Путь текущей страницы с параметрами: так фронт записывает postLoginRedirect (Q-UI-36)."""
    url = urlsplit(page.url)
    return f"{url.path}?{url.query}" if url.query else url.path


# ---------------------------------------------------------------- REQ-UI-SESSION-03: вход


@allure.epic("Playwright Testing")
@allure.feature("Session")
@allure.story("Failed login or registration")
@allure.title("Вход, отклонённый сервером (401), не создаёт сессию")
@allure.tag("REQ-UI-SESSION-03")
def test_pw_rejected_login_creates_no_session(page: Page, shared_user):
    """
    Настоящий ответ 401: email общего пользователя, неверный пароль (Q-UI-30 — то же с подменой).
    Подмены нет и защиты записи тоже: неудачный вход состояния пользователя не меняет и выданных
    токенов не отзывает (Q-API-19), на бэкенде он следа не оставляет.
    """
    login_page = PwLoginPage(page)
    login_page.open()
    # Неверный пароль, который проходит проверки формы: настоящий пароль с лишним символом
    wrong_password = f"{shared_user.user.password}x"

    with allure.step("Вход с неверным паролем: настоящий запрос к серверу"):
        with page.expect_response(api_response("POST", LOGIN_PATH)) as answer:
            login_page.login(shared_user.user.email, wrong_password)
        require(answer.value.status == 401, f"Предусловие: вход с неверным паролем ответил {answer.value.status}")
        # Фронт обработал ответ: окно ошибки входа
        login_page.error_dialog.wait_for(state="visible")

    _assert_no_session(login_page, "ответа 401 на вход")


@allure.epic("Playwright Testing")
@allure.feature("Session")
@allure.story("Failed login or registration")
@allure.title("Сбой входа (500, обрыв) не создаёт сессию")
@allure.tag("REQ-UI-SESSION-03")
@pytest.mark.parametrize("login_failure", ["server_error_500", "network_error"])
def test_pw_failed_login_creates_no_session(page: Page, backend_write_guard, login_failure):
    """Ответ входа подменён (Q-UI-30): 500 с пустым телом или обрыв. Пользователь не регистрируется:
    данные нужны только, чтобы форма отправила запрос, а запрос до бэкенда не доходит."""
    user = UserGenerator.get_random_user()
    login_page = PwLoginPage(page)
    login_page.open()

    faults = NetworkFaults(page)
    sent = faults.abort(LOGIN, "POST") if login_failure == "network_error" else faults.respond_empty(LOGIN, "POST", 500)

    with allure.step(f"Вход: запрос перехвачен, сбой — {login_failure}"):
        send_and_settle(page, "POST", LOGIN_PATH, lambda: login_page.login(user.email, user.password))
        # Без пойманного запроса фронт получил бы настоящий ответ сервера, а не сбой
        require_intercepted(sent, f"POST {LOGIN_PATH}")
        login_page.error_dialog.wait_for(state="visible")

    _assert_no_session(login_page, f"сбоя входа {login_failure}")


# ---------------------------------------------------------------- REQ-UI-SESSION-03: регистрация


@allure.epic("Playwright Testing")
@allure.feature("Session")
@allure.story("Failed login or registration")
@allure.title("Неудачная регистрация (400, 401, 500, обрыв) не создаёт сессию")
@allure.tag("REQ-UI-SESSION-03")
@pytest.mark.parametrize(
    "registration_failure", ["bad_request_400", "unauthorized_401", "server_error_500", "network_error"]
)
def test_pw_failed_registration_creates_no_session(page: Page, backend_write_guard, registration_failure):
    """
    Регистрация — только подменой (Q-UI-31, Q-UI-40): 400 — тело настоящего ответа сервера на слабый
    пароль (Q-API-07, без timestamp — его значение в логе замаскировано), 401 и 500 — пустое тело,
    обрыв. Ответ 409 не используется: в Swagger его нет. Email фальшивый, пользователь не создаётся.
    """
    registration_page = PwRegistrationPage(page)
    registration_page.open()

    faults = NetworkFaults(page)
    if registration_failure == "bad_request_400":
        sent = faults.respond_recorded(REGISTRATION, "POST", 400, REGISTER_400_WEAK_PASSWORD, source="Q-API-07")
    elif registration_failure == "network_error":
        sent = faults.abort(REGISTRATION, "POST")
    else:
        status = {"unauthorized_401": 401, "server_error_500": 500}[registration_failure]
        sent = faults.respond_empty(REGISTRATION, "POST", status)

    with allure.step(f"Регистрация: запрос перехвачен, сбой — {registration_failure}"):
        registration_page.fill_form(UserGenerator.get_random_user())
        send_and_settle(page, "POST", REGISTRATION_PATH, registration_page.submit)
        require_intercepted(sent, f"POST {REGISTRATION_PATH}")
        # Фронт обработал ответ: окно «Registration failed» (400) или role=alert (остальные, Q-UI-31)
        page.get_by_role("dialog").or_(page.get_by_role("alert")).first.wait_for(state="visible")

    _assert_no_session(registration_page, f"неудачной регистрации {registration_failure}")


# ---------------------------------------------------------------- 401 там, где был token


@dataclass
class After401:
    """Экран, получивший 401 под залогиненным пользователем, и перехваченный запрос."""

    screen: PwBasePage
    request_path: str


def _logged_in(screen: PwBasePage, token: str) -> None:
    """Вход токеном и открытие экрана; token и «Log out» есть до сбоя — предусловие."""
    screen.restore_session(token)
    screen.open()
    PwLoginPage(screen.page).logout_btn.wait_for(state="visible")
    require(screen.local_storage_item("token") is not None, "Предусловие: после входа в localStorage нет token")


def _require_sent_with_token(sent: list, what: str) -> None:
    require_intercepted(sent, what)
    require(
        bool(sent[0].headers.get("authorization")),
        f"Предусловие: {what} ушёл без заголовка Authorization — сессии не было ещё до ответа 401",
    )


@pytest.fixture
def car_form_after_401(page: Page, shared_user, shared_car_cleanup, backend_write_guard) -> After401:
    """Форма машины под shared_user: POST /v1/cars получил 401 с пустым телом (Q-UI-32)."""
    add_car_page = PwAddCarPage(page)
    _logged_in(add_car_page, shared_user.api.token)
    car = CarGenerator.get_random_car()
    # Страховка: если перехват не сработает и машина создастся на бэкенде, очистка её удалит
    shared_car_cleanup.register(car.reg_number)
    add_car_page.fill_form(car)

    sent = NetworkFaults(page).respond_empty(CARS, "POST", 401)
    with allure.step("Отправка формы: POST /v1/cars перехвачен, ответ — 401 с пустым телом"):
        send_and_settle(page, "POST", CARS_PATH, add_car_page.submit)
        _require_sent_with_token(sent, f"POST {CARS_PATH}")
        # Фронт обработал ответ: форма показала ошибку отправки (Q-UI-32)
        add_car_page.submit_error_message.wait_for(state="visible")
    return After401(add_car_page, CARS_PATH)


@pytest.fixture
def search_after_401(page: Page, shared_user, backend_write_guard) -> After401:
    """Поиск под shared_user: POST /v1/cars/search получил 401 с пустым телом (Q-UI-39).

    Поиск подменён целиком и до бэкенда не доходит; защита записи нужна и ему: поиск — тоже POST.
    """
    search_page = PwSearchPage(page)
    _logged_in(search_page, shared_user.api.token)

    sent = NetworkFaults(page).respond_empty(SEARCH, "POST", 401)
    with allure.step("Поиск: POST /v1/cars/search перехвачен, ответ — 401 с пустым телом"):
        send_and_settle(page, "POST", SEARCH_PATH, lambda: search_page.search_today(SearchDataGenerator.SMALL_CITY))
        _require_sent_with_token(sent, f"POST {SEARCH_PATH}")
        # Фронт обработал ответ: сообщений поиск не показывает (Q-UI-39), признак конца — кнопка
        # снова «Yalla!» вместо «Loading...»
        search_page.submit_btn.filter(has_text="Yalla!").wait_for(state="visible")
    return After401(search_page, SEARCH_PATH)


@allure.epic("Playwright Testing")
@allure.feature("Session")
@allure.story("Response 401")
@allure.title("401 на экране залогиненного пользователя удаляет token и запоминает postLoginRedirect")
@allure.tag("REQ-UI-SESSION-01")
@pytest.mark.parametrize("screen_after_401", ["car_form_after_401", "search_after_401"])
def test_pw_401_on_screen_clears_token(request, page: Page, screen_after_401):
    """Перехватчик ответов фронта (FE: `index`) срабатывает на любом экране, где был token:
    форма машины (Q-UI-32) и поиск под пользователем (Q-UI-39)."""
    after_401: After401 = request.getfixturevalue(screen_after_401)
    expected_redirect = _current_path(page)

    with allure.step("Проверка localStorage после ответа 401"):
        assert after_401.screen.local_storage_item("token") is None, (
            f"После ответа 401 на {after_401.request_path} token остался в localStorage"
        )
        redirect = after_401.screen.local_storage_item("postLoginRedirect")
        assert redirect == expected_redirect, (
            f"После ответа 401 ожидали postLoginRedirect={expected_redirect!r}, в localStorage {redirect!r}"
        )


@allure.epic("Playwright Testing")
@allure.feature("Session")
@allure.story("Response 401")
@allure.title("После 401 на поиске в навигации нет «Log out»")
@observation("STALE_SESSION_UI_AFTER_401")
@allure.tag("OBS-05")
def test_pw_search_401_hides_logout(page: Page, search_after_401):
    """Токен удалён (Q-UI-39), а навигация показывает пользователя залогиненным (OBS-05)."""
    require(search_after_401.screen.local_storage_item("token") is None, "Предусловие: после 401 token не удалён")
    with allure.step("Проверка: кнопки «Log out» в навигации нет"):
        expect(
            PwLoginPage(page).logout_btn, "После ответа 401 на поиске токен удалён, но «Log out» остался в навигации"
        ).to_be_hidden()


# ---------------------------------------------------------------- REQ-UI-CAR-05: текст сервера


def _page_text(page: Page) -> str:
    return page.locator("body").inner_text()


@allure.epic("Playwright Testing")
@allure.feature("Cars Management")
@allure.story("Submit error text")
@allure.title("При 401 на отправку машины текст ошибки сервера не показывается")
@allure.tag("REQ-UI-CAR-05")
def test_pw_car_form_401_hides_server_message(page: Page, shared_user, shared_car_cleanup, backend_write_guard):
    """
    Ответ 401 с текстом парсера JWT (Q-UI-34) не должен попасть на экран (ASVS V7.4.1). В логе
    исследования записан только message настоящего ответа, поэтому тело подмены — только message:
    остальные поля не выдумываются. Проверка отсутствия текста опирается на require_intercepted:
    без пойманного запроса фронт этого текста не получал, и его отсутствие ничего бы не доказало.
    """
    server_message = CAR_401_GARBAGE_TOKEN["message"]
    add_car_page = PwAddCarPage(page)
    _logged_in(add_car_page, shared_user.api.token)
    car = CarGenerator.get_random_car()
    # Страховка: если перехват не сработает и машина создастся на бэкенде, очистка её удалит
    shared_car_cleanup.register(car.reg_number)
    add_car_page.fill_form(car)

    sent = NetworkFaults(page).respond_recorded(CARS, "POST", 401, CAR_401_GARBAGE_TOKEN, source="Q-UI-34")
    with allure.step("Отправка формы: POST /v1/cars перехвачен, ответ — 401 с текстом сервера"):
        send_and_settle(page, "POST", CARS_PATH, add_car_page.submit)
        require_intercepted(sent, f"POST {CARS_PATH}")
        add_car_page.submit_error_message.wait_for(state="visible")

    with allure.step("Проверка: текста ошибки сервера на странице нет"):
        assert server_message not in _page_text(page), f"На странице показан текст ошибки сервера: {server_message}"
