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
@pytest.mark.parametrize("email, pass_condition, expected_error, scenario", [
    ("123", "valid", "Wrong email format", "Невалидный формат email"),
    (VALID_EMAIL, "empty", "Password is required", "Пустой пароль")
])
def test_login_negative_frontend(driver, email, pass_condition, expected_error, scenario):
    with allure.step(f"Сценарий: {scenario}"):
        login_page = LoginPage(driver)
        login_page.open()

        # БЕЗОПАСНАЯ ЛОГИКА: Достаем реальный пароль только внутри функции!
        actual_password = VALID_PASSWORD if pass_condition == "valid" else ""

        login_page.fill_email(email)
        # В метод уйдет реальный пароль, но Allure увидит в параметрах только слово "valid"
        login_page.fill_password(actual_password)
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
@pytest.mark.parametrize("email_condition, pass_condition, scenario", [
    # Вместо реальных данных из .env передаем текстовые флаги
    ("fake_user_12345@gmail.com", "valid_pass", "Несуществующий пользователь"),
    ("valid_email", "WrongPassword123!", "Неверный пароль")
])
def test_login_negative_backend(driver, email_condition, pass_condition, scenario):
    """Проверка ошибок, которые возвращает сервер после попытки авторизации"""
    with allure.step(f"Сценарий: {scenario}"):
        login_page = LoginPage(driver)
        login_page.open()

        # БЕЗОПАСНАЯ ЛОГИКА: Расшифровываем флаги внутри теста
        actual_email = VALID_EMAIL if email_condition == "valid_email" else email_condition
        actual_password = VALID_PASSWORD if pass_condition == "valid_pass" else pass_condition

        # Отправляем форму (в браузер уходят реальные креды, а в отчет Allure - только слова из параметризации)
        login_page.login(actual_email, actual_password)

        # Ожидаем глобальное сообщение об ошибке
        assert login_page.get_global_message_text() == "Login failed", "Неверный текст ошибки бэкенда"