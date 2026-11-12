import allure
import pytest
from playwright.sync_api import Page

from data.data_generator import UserGenerator
from data.known_bugs import known_bug
from pages.pw_login_page import PwLoginPage
from utils.network_faults import LOGIN, NetworkFaults, require_intercepted, send_and_settle
from utils.preconditions import require

pytestmark = pytest.mark.ui


@pytest.mark.smoke
@allure.epic("Playwright Testing")
@allure.feature("Login")
@allure.story("Positive Login (POM)")
@allure.title("Успешная авторизация (Playwright + POM)")
@allure.tag("REQ-UI-LOGIN-02")
def test_pw_login_success(page: Page, temp_user):
    pw_login_page = PwLoginPage(page)
    pw_login_page.open()

    user = temp_user.user
    pw_login_page.login(user.email, user.password)

    pw_login_page.check_success_message()
    pw_login_page.click_ok_button()
    pw_login_page.check_logout_button_visible()


@pytest.mark.regression
@allure.epic("Playwright Testing")
@allure.feature("Login")
@allure.story("Negative Login - Frontend")
@allure.title("Ошибки валидации формы логина (Playwright)")
@allure.tag("REQ-UI-LOGIN-01")
@pytest.mark.parametrize(
    "email, password, expected_error, scenario",
    [
        ("bad-email", "ValidPass123!", "Wrong email format", "Невалидный email"),
        ("valid_user@example.com", "", "Password is required", "Пустой пароль"),
    ],
)
def test_pw_login_negative(page: Page, email, password, expected_error, scenario):
    with allure.step(f"Сценарий: {scenario}"):
        pw_login_page = PwLoginPage(page)
        pw_login_page.open()

        pw_login_page.fill_email(email)
        pw_login_page.fill_password(password)
        pw_login_page.remove_focus()

        pw_login_page.check_error_message(expected_error)
        pw_login_page.check_submit_button_disabled()


LOGIN_PATH = "/v1/user/login/usernamepassword"


@pytest.mark.regression
@allure.epic("Playwright Testing")
@allure.feature("Login")
@allure.story("Negative Login - Backend Failure")
@allure.title("Ошибка входа, отличная от 401: «Login failed. Try again»")
@known_bug("LOGIN_ERROR_TEXT_HARDCODED")
@allure.tag("REQ-UI-LOGIN-03")
@pytest.mark.parametrize("login_failure", ["server_error_500", "bad_request_400", "network_error"])
def test_pw_login_other_error_text(page: Page, backend_write_guard, login_failure):
    """
    Ветка «любая другая ошибка» REQ-UI-LOGIN-03: при сбое, отличном от 401, окно должно сказать
    «Login failed. Try again», а не обвинять пользователя в неверном пароле (Q-UI-10).
    Ответ входа подменён, запрос до бэкенда не доходит; ветку 401 проверяет test_login_negative_backend.
    """
    # Пользователь не регистрируется: данные нужны только, чтобы форма отправила запрос
    user = UserGenerator.get_random_user()
    pw_login_page = PwLoginPage(page)
    pw_login_page.open()

    faults = NetworkFaults(page)
    if login_failure == "network_error":
        sent = faults.abort(LOGIN, "POST")
    else:
        status = {"server_error_500": 500, "bad_request_400": 400}[login_failure]
        sent = faults.respond(LOGIN, "POST", status)

    with allure.step(f"Вход: запрос перехвачен, сбой — {login_failure}"):
        send_and_settle(page, "POST", LOGIN_PATH, lambda: pw_login_page.login(user.email, user.password))
        # Без пойманного запроса текст окна относился бы к настоящему ответу сервера (401), а не к сбою
        require_intercepted(sent, f"POST {LOGIN_PATH}")

    with allure.step("Проверка текста окна ошибки"):
        # wait_for и require, а не expect: под xfail остаётся только проверка текста
        pw_login_page.error_dialog.wait_for(state="visible")
        title = pw_login_page.error_dialog_title.inner_text()
        require(title == "Login failed", f"Ожидали окно «Login failed», получили «{title}»")
        details = pw_login_page.error_dialog_text.inner_text()

        assert "Login failed. Try again" in details, (
            f"При сбое {login_failure} ожидали текст «Login failed. Try again», в окне: {details}"
        )


@pytest.mark.regression
@allure.epic("Playwright Testing")
@allure.feature("Login")
@allure.story("Email case")
@allure.title("Email уходит во вход в нижнем регистре")
@allure.tag("REQ-UI-LOGIN-01")
def test_pw_login_sends_email_lowercase(page: Page, backend_write_guard):
    """
    Фронт приводит email к нижнему регистру перед отправкой (REQ-UI-LOGIN-01, Q-UI-09). Запрос входа
    перехвачен, ответ подменён на 401: пользователь не нужен, на бэкенд ничего не уходит.
    """
    user = UserGenerator.get_random_user()
    typed_email = user.email.replace("user_", "User_").replace("@example.com", "@Example.COM")
    require(typed_email != typed_email.lower(), f"Предусловие: в email {typed_email} нет заглавных букв")
    pw_login_page = PwLoginPage(page)
    pw_login_page.open()
    sent = NetworkFaults(page).respond(LOGIN, "POST", 401)

    with allure.step(f"Вход с email {typed_email}: запрос перехвачен"):
        send_and_settle(page, "POST", LOGIN_PATH, lambda: pw_login_page.login(typed_email, user.password))
        require_intercepted(sent, f"POST {LOGIN_PATH}")
        body = sent[0].post_data_json
        require(isinstance(body, dict), f"Тело запроса входа — не JSON-объект: {type(body).__name__}")

    with allure.step("Проверка: username в запросе — email в нижнем регистре"):
        assert body.get("username") == typed_email.lower(), (
            f"Ввели {typed_email}, в запросе username={body.get('username')!r}, ожидали {typed_email.lower()!r}"
        )
