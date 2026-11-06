import pytest
import allure
from pages.registration_page import RegistrationPage
from data.data_generator import UserGenerator
from data.known_bugs import known_bug
from utils.preconditions import require

pytestmark = pytest.mark.ui

@pytest.mark.smoke
@allure.epic("UI Testing")
@allure.feature("Registration Page")
@allure.story("Navigation")
@allure.severity(allure.severity_level.NORMAL)
def test_navigation_to_registration(driver):
    registration_page = RegistrationPage(driver)
    registration_page.open_main_page()
    registration_page.click_registration_button_in_menu()
    assert "register" in registration_page.get_current_url(), "Переход из меню не удался"


@pytest.mark.smoke
@allure.epic("UI Testing")
@allure.feature("Registration Page")
@allure.story("Positive Registration")
@allure.severity(allure.severity_level.BLOCKER)
def test_registration_success(driver):
    registration_page = RegistrationPage(driver)
    user = UserGenerator.get_random_user()

    registration_page.open_registration_form()
    registration_page.fill_registration_form(user)
    registration_page.set_policy_checkbox(True)
    registration_page.submit_registration()

    assert registration_page.confirmation_text() == "Registered", "Заголовок об успехе не появился!"
    assert registration_page.confirmation_text_1() == "You are logged in success", "Текст успешного входа не совпадает!"
    registration_page.close_window()
    UserGenerator.save_created_user(user)


@pytest.mark.regression
@allure.epic("UI Testing")
@allure.feature("Registration Page")
@allure.story("Negative Registration - Frontend")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("field_name, invalid_value, expected_error, scenario", [
    ("name", "", "Name is required", "Пустое имя"),
    ("last_name", "", "Last name is required", "Пустая фамилия"),
    ("email", "tonygmail.com", "Wrong email format", "Неверный формат email"),
    ("email", "", "Email is required", "Пустой email"),
    ("password", "P123$", "Password must contain minimum 6 symbols", "Слишком короткий пароль"),
    ("password", "", "Password is required", "Пустой пароль")
])
def test_registration_negative_fields(driver, field_name, invalid_value, expected_error, scenario):
    with allure.step(f"Сценарий: {scenario}"):
        registration_page = RegistrationPage(driver)

        kwargs = {field_name: invalid_value}
        user = UserGenerator.get_random_user(**kwargs)

        registration_page.open_registration_form()
        registration_page.fill_registration_form(user)
        registration_page.set_policy_checkbox(True)
        registration_page.remove_focus()

        assert registration_page.error_message_text() == expected_error, f"Ожидалась ошибка '{expected_error}'"
        assert registration_page.submit_button_disabled() == True, "Кнопка Y'alla! не заблокировалась"


@pytest.mark.regression
@pytest.mark.security
@allure.epic("UI Testing")
@allure.feature("Registration Page")
@allure.story("Negative Registration - Backend")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-AUTH-04", "REQ-UI-REG-03")
@pytest.mark.parametrize("password_strategy, scenario", [
    ("same_password", "Занятый email + Тот же пароль"),
    ("new_valid_password", "Занятый email + Другой пароль (валидный и для фронта, и для API)"),
])
def test_registration_existing_user(driver, temp_user, password_strategy, scenario, sys_logger):
    """
    Повторная регистрация занятого email отклоняется (REQ-AUTH-04), окно «Registration failed»
    показывает текст ошибки сервера (REQ-UI-REG-03). Пароль проходит правила и фронта, и API
    (DISC-01), поэтому сервер отказывает именно из-за занятого email.
    """
    with allure.step(f"Сценарий: {scenario}"):
        registration_page = RegistrationPage(driver)

        # 1. Забираем уже зарегистрированного юзера из песочницы
        existing_user = temp_user["user"]

        # 2. Определяем пароль для попытки повторной регистрации
        if password_strategy == "same_password":
            actual_password = existing_user.password
        else:
            actual_password = UserGenerator.generate_valid_password()

        # 3. Формируем юзера: старый email + выбранный пароль
        user = UserGenerator.get_random_user(email=existing_user.email, password=actual_password)

        registration_page.open_registration_form()
        registration_page.fill_registration_form(user)
        registration_page.set_policy_checkbox(True)

        registration_page.submit_registration()

    with allure.step("Проверка окна ошибки"):
        title = registration_page.confirmation_text()
        actual_error_details = registration_page.confirmation_text_1()
        sys_logger.info(f"Окно: '{title}' / '{actual_error_details}'")

        assert title == "Registration failed", f"Бэкенд не отбил регистрацию занятого email! Заголовок окна: '{title}'"
        assert "User already exists" in actual_error_details,             f"Ожидали текст 'User already exists', а получили '{actual_error_details}'"


@pytest.mark.regression
@allure.epic("UI Testing")
@allure.feature("Registration Page")
@allure.story("Negative Registration - Password Rules Mismatch")
@allure.severity(allure.severity_level.NORMAL)
@known_bug("PASSWORD_RULES_MISMATCH")
@allure.tag("DISC-01", "REQ-UI-REG-03")
def test_registration_password_rejected_by_api(driver, sys_logger):
    """
    Пароль, который фронт пропускает (не короче 6, буква и цифра), а API отклоняет (нет заглавной
    и спецсимвола, короче 8) — DISC-01. Окно ошибки должно показать читаемый текст ошибки сервера
    (REQ-UI-REG-03), а не "[object Object]" (Q-UI-07).
    """
    registration_page = RegistrationPage(driver)
    user = UserGenerator.get_random_user(password="abc123")

    with allure.step("Регистрация нового email с паролем abc123"):
        registration_page.open_registration_form()
        registration_page.fill_registration_form(user)
        registration_page.set_policy_checkbox(True)
        registration_page.remove_focus()
        # Предмет бага — текст окна; то, что фронт пропускает пароль, — предусловие сценария
        require(not registration_page.submit_button_disabled(), "Фронт не пропустил пароль abc123: сценарий DISC-01 не воспроизвести")
        registration_page.submit_registration()

    with allure.step("Проверка текста окна ошибки"):
        title = registration_page.confirmation_text()
        require(title == "Registration failed", f"Ожидали окно 'Registration failed', получили '{title}'")
        details = registration_page.confirmation_text_1()
        sys_logger.info(f"Текст окна ошибки: '{details}'")

        assert details.strip() and "[object Object]" not in details,             f"Текст окна ошибки нечитаемый: '{details}'"


@pytest.mark.regression
@allure.epic("UI Testing")
@allure.feature("Registration Page")
@allure.story("Negative Registration - Checkbox")
@allure.severity(allure.severity_level.NORMAL)
def test_registration_without_check_box(driver):
    registration_page = RegistrationPage(driver)
    user = UserGenerator.get_random_user()

    registration_page.open_registration_form()
    registration_page.fill_registration_form(user)
    registration_page.set_policy_checkbox(True)
    registration_page.set_policy_checkbox(False)
    registration_page.remove_focus()

    assert registration_page.error_message_text() == "You must accept the terms", "Ошибка чекбокса не появилась"
    assert registration_page.submit_button_disabled() == True, "Кнопка не заблокировалась без чекбокса"