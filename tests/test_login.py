import os
import allure
import pytest
from pages.login_page import LoginPage

VALID_EMAIL = os.getenv("USER_EMAIL")
VALID_PASSWORD = os.getenv("USER_PASSWORD")


# ==========================================
# ПОЗИТИВНЫЙ ТЕСТ
# ==========================================
@allure.epic("UI Testing")
@allure.feature("Login Page")
@allure.story("Positive Login")
@allure.severity(allure.severity_level.BLOCKER)
def test_login_success(driver):
    login_page = LoginPage(driver)
    login_page.open()
    login_page.login(VALID_EMAIL, VALID_PASSWORD)

    assert login_page.get_global_message_text() == "You are logged in success", "Сообщение об успехе не совпадает!"
    login_page.click_ok_button()
    assert login_page.is_logout_button_visible() == True, "Кнопка 'Log out' не найдена"


# ==========================================
# НЕГАТИВНЫЕ ТЕСТЫ: Фронтенд-валидация
# ==========================================
@allure.epic("UI Testing")
@allure.feature("Login Page")
@allure.story("Negative Login - Frontend Validation")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.parametrize("email, password, expected_error, scenario", [
    ("123", VALID_PASSWORD, "Wrong email format", "Невалидный формат email"),
    (VALID_EMAIL, "", "Password is required", "Пустой пароль")
])
def test_login_negative_frontend(driver, email, password, expected_error, scenario):
    """Проверка ошибок, которые отлавливаются на стороне браузера (без отправки на сервер)"""
    with allure.step(f"Сценарий: {scenario}"):
        login_page = LoginPage(driver)
        login_page.open()

        login_page.fill_email(email)
        login_page.fill_password(password)
        login_page.remove_focus()

        assert login_page.get_error_message_text() == expected_error, f"Ожидалась ошибка: {expected_error}"
        assert login_page.is_submit_button_disabled() == True, "Кнопка Y'alla! должна быть заблокирована"


# ==========================================
# НЕГАТИВНЫЕ ТЕСТЫ: Бэкенд-валидация
# ==========================================
@allure.epic("UI Testing")
@allure.feature("Login Page")
@allure.story("Negative Login - Backend Validation")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("email, password, scenario", [
    ("fake_user_12345@gmail.com", VALID_PASSWORD, "Несуществующий пользователь"),
    (VALID_EMAIL, "WrongPassword123!", "Неверный пароль")
])
def test_login_negative_backend(driver, email, password, scenario):
    """Проверка ошибок, которые возвращает сервер после попытки авторизации"""
    with allure.step(f"Сценарий: {scenario}"):
        login_page = LoginPage(driver)
        login_page.open()

        # Здесь мы отправляем форму полностью
        login_page.login(email, password)

        # Ожидаем глобальное сообщение об ошибке (оно одинаковое для обоих сценариев)
        assert login_page.get_global_message_text() == "Login failed", "Неверный текст ошибки бэкенда"