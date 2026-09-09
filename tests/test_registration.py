import pytest
import allure
from pages.registration_page import RegistrationPage
from data.data_generator import UserGenerator


@allure.epic("UI Testing")
@allure.feature("Registration Page")
@allure.story("Navigation")
@allure.severity(allure.severity_level.NORMAL)
# --- ТЕСТ 1: Проверка навигации (меню) ---
def test_navigation_to_registration(driver):
    registration_page = RegistrationPage(driver)
    registration_page.open_main_page()
    registration_page.click_registration_button_in_menu()

    assert "register" in registration_page.get_current_url(), "Переход из меню не удался"


@allure.epic("UI Testing")
@allure.feature("Registration Page")
@allure.story("Positive Registration")
@allure.severity(allure.severity_level.BLOCKER)
# --- ПОЗИТИВНЫЙ ТЕСТ ---
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


# ===========================================================================
# ПАРАМЕТРИЗОВАННЫЙ НЕГАТИВНЫЙ ТЕСТ (6 проверок в 1 функции!)
# ===========================================================================
@allure.epic("UI Testing")
@allure.feature("Registration Page")
@allure.story("Negative Registration")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("field_name, invalid_value, expected_error", [
    ("name", "", "Name is required"),
    ("last_name", "", "Last name is required"),
    ("email", "tonygmail.com", "Wrong email format"),
    ("email", "", "Email is required"),
    ("password", "P123$", "Password must contain minimum 6 symbols"),
    ("password", "", "Password is required")
])
def test_registration_negative_fields(driver, field_name, invalid_value, expected_error):
    registration_page = RegistrationPage(driver)

    # Динамически создаем словарь с "битым" полем и передаем его в генератор
    kwargs = {field_name: invalid_value}
    user = UserGenerator.get_random_user(**kwargs)

    registration_page.open_registration_form()
    registration_page.fill_registration_form(user)
    registration_page.set_policy_checkbox(True)

    # Универсальный клик в пустоту для вызова onBlur валидации во всех сценариях
    registration_page.remove_focus()

    assert registration_page.error_message_text() == expected_error, f"Ожидалась ошибка '{expected_error}'"
    assert registration_page.submit_button_disabled() == True, "Кнопка Y'alla! не заблокировалась"


# --- НЕГАТИВНЫЙ ТЕСТ: ЧЕКБОКС (Отдельный флоу) ---
@allure.epic("UI Testing")
@allure.feature("Registration Page")
@allure.story("Negative Registration - Checkbox")
@allure.severity(allure.severity_level.NORMAL)
def test_registration_without_check_box(driver):
    registration_page = RegistrationPage(driver)
    user = UserGenerator.get_random_user()

    registration_page.open_registration_form()
    registration_page.fill_registration_form(user)

    # Имитируем сомнения: поставили галочку и сразу убрали, чтобы триггернуть валидацию
    registration_page.set_policy_checkbox(True)
    registration_page.set_policy_checkbox(False)

    # СНИМАЕМ ФОКУС: кликаем в пустоту
    registration_page.remove_focus()

    assert registration_page.error_message_text() == "You must accept the terms", "Ошибка чекбокса не появилась"
    assert registration_page.submit_button_disabled() == True, "Кнопка не заблокировалась без чекбокса"