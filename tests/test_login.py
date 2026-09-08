import os
import allure
from pages.login_page import LoginPage

# Тестовые данные берем из защищенного .env
VALID_EMAIL = os.getenv("USER_EMAIL")
VALID_PASSWORD = os.getenv("USER_PASSWORD")

INVALID_EMAIL_FORMAT = "123"
UNREGISTERED_EMAIL = "fake_user_12345@gmail.com"


@allure.epic("UI Testing")
@allure.feature("Login Page")
@allure.story("Positive Login")
@allure.severity(allure.severity_level.BLOCKER)
def test_login_success(driver):
    login_page = LoginPage(driver)
    login_page.open()
    login_page.login(VALID_EMAIL, VALID_PASSWORD)

    assert login_page.is_success_message_visible() == True, "Сообщение об успехе не появилось"
    login_page.click_ok_button()
    assert login_page.is_logout_button_visible() == True, "Кнопка 'Log out' не найдена"


@allure.epic("UI Testing")
@allure.feature("Login Page")
@allure.story("Negative Login - Frontend Validation")
@allure.severity(allure.severity_level.NORMAL)
def test_login_invalid_email_format(driver):
    login_page = LoginPage(driver)
    login_page.open()

    login_page.fill_email(INVALID_EMAIL_FORMAT)
    login_page.click_empty_space()  # Кликаем мимо, чтобы вызвать ошибку

    assert login_page.is_error_wrong_email_visible() == True, "Текст 'Wrong email format' не появился"
    assert login_page.is_submit_button_disabled() == True, "Кнопка Y'alla! должна быть заблокирована"


@allure.epic("UI Testing")
@allure.feature("Login Page")
@allure.story("Negative Login - Frontend Validation")
@allure.severity(allure.severity_level.NORMAL)
def test_login_empty_password(driver):
    login_page = LoginPage(driver)
    login_page.open()

    login_page.fill_email(VALID_EMAIL)
    login_page.fill_password("")  # Оставляем пароль пустым
    login_page.click_empty_space()

    assert login_page.is_error_required_field_visible() == True, "Текст 'Password is required' не появился"
    assert login_page.is_submit_button_disabled() == True, "Кнопка Y'alla! должна быть заблокирована"


@allure.epic("UI Testing")
@allure.feature("Login Page")
@allure.story("Negative Login - Backend Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_login_unregistered_user(driver):
    login_page = LoginPage(driver)
    login_page.open()

    # Пытаемся залогиниться под несуществующим юзером
    login_page.login(UNREGISTERED_EMAIL, VALID_PASSWORD)

    assert login_page.is_login_failed_message_visible() == True, "Сообщение 'Login failed' не появилось"


@allure.epic("UI Testing")
@allure.feature("Login Page")
@allure.story("Negative Login - Backend Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_login_wrong_password(driver):
    login_page = LoginPage(driver)
    login_page.open()

    # Вводим настоящий email, но намеренно ложный пароль
    login_page.login(VALID_EMAIL, "WrongPassword123!")

    assert login_page.is_login_failed_message_visible() == True, "Сообщение 'Login failed' не появилось при неверном пароле"