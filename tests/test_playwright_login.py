import allure
import pytest
from playwright.sync_api import Page
from pages.pw_login_page import PwLoginPage


@allure.epic("Playwright Testing")
@allure.feature("Login")
@allure.story("Positive Login (POM)")
@allure.title("Успешная авторизация (Playwright + POM)")
def test_pw_login_success(page: Page, temp_user):
    pw_login_page = PwLoginPage(page)
    pw_login_page.open()

    user = temp_user["user"]
    pw_login_page.login(user.email, user.password)

    pw_login_page.check_success_message()
    pw_login_page.click_ok_button()
    pw_login_page.check_logout_button_visible()


@allure.epic("Playwright Testing")
@allure.feature("Login")
@allure.story("Negative Login - Frontend")
@allure.title("Ошибки валидации формы логина (Playwright)")
@pytest.mark.parametrize("email, password, expected_error, scenario", [
    ("bad-email", "ValidPass123!", "Wrong email format", "Невалидный email"),
    ("valid_user@example.com", "", "Password is required", "Пустой пароль")
])
def test_pw_login_negative(page: Page, email, password, expected_error, scenario):
    with allure.step(f"Сценарий: {scenario}"):
        pw_login_page = PwLoginPage(page)
        pw_login_page.open()

        pw_login_page.fill_email(email)
        pw_login_page.fill_password(password)
        pw_login_page.remove_focus()

        pw_login_page.check_error_message(expected_error)
        pw_login_page.check_submit_button_disabled()