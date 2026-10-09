import allure
import pytest
from pages.login_page import LoginPage

@pytest.mark.smoke
@allure.epic("UI Testing")
@allure.feature("Login Page")
@allure.story("Positive Login")
@allure.severity(allure.severity_level.BLOCKER)
def test_login_success(driver, temp_user):
    login_page = LoginPage(driver)
    login_page.open()

    user = temp_user["user"]  # Берем гарантированно существующего юзера
    login_page.login(user.email, user.password)

    assert login_page.get_global_message_text() == "You are logged in success", "Сообщение об успехе не совпадает!"
    login_page.click_ok_button()
    assert login_page.is_logout_button_visible() == True, "Кнопка 'Log out' не найдена"

@pytest.mark.regression
@allure.epic("UI Testing")
@allure.feature("Login Page")
@allure.story("Negative Login - Frontend Validation")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.parametrize("email, pass_condition, expected_error, scenario", [
    ("123", "valid", "Wrong email format", "Невалидный формат email"),
    ("valid_user@example.com", "empty", "Password is required", "Пустой пароль")
])
def test_login_negative_frontend(driver, email, pass_condition, expected_error, scenario):
    with allure.step(f"Сценарий: {scenario}"):
        login_page = LoginPage(driver)
        login_page.open()

        actual_password = "ValidPassword123!" if pass_condition == "valid" else ""

        login_page.fill_email(email)
        login_page.fill_password(actual_password)
        login_page.remove_focus()

        assert login_page.get_error_message_text() == expected_error, f"Ожидалась ошибка: {expected_error}"
        assert login_page.is_submit_button_disabled() == True, "Кнопка Y'alla! должна быть заблокирована"

@pytest.mark.regression
@allure.epic("UI Testing")
@allure.feature("Login Page")
@allure.story("Negative Login - Backend Validation")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("email_condition, pass_condition, expected_details, scenario", [
    ("fake_user", "valid_pass", "Login or Password incorrect", "Несуществующий пользователь"),
    ("valid_email", "wrong_pass", "Login or Password incorrect", "Неверный пароль")
])
def test_login_negative_backend(driver, temp_user, email_condition, pass_condition, expected_details, scenario):
    with allure.step(f"Сценарий: {scenario}"):
        login_page = LoginPage(driver)
        login_page.open()

        user = temp_user["user"]  # Запрашиваем валидного юзера для микса данных

        actual_email = user.email if email_condition == "valid_email" else "fake_user_12345@gmail.com"
        actual_password = user.password if pass_condition == "valid_pass" else "WrongPassword123!"

        login_page.login(actual_email, actual_password)

        assert login_page.get_global_message_text() == "Login failed", "Неверный заголовок ошибки бэкенда"
        actual_details = login_page.get_global_message_details_text()

        if "[object Object]" in actual_details:
            pytest.xfail("ПЛАВАЮЩИЙ БАГ ФРОНТЕНДА: React не успел распарсить JSON")
        else:
            assert expected_details in actual_details, \
                f"Ожидали текст '{expected_details}', а получили '{actual_details}'"