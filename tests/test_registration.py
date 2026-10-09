import pytest
import allure
import random
import string
from pages.registration_page import RegistrationPage
from data.data_generator import UserGenerator

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


def get_short_complex_password():
    upper = random.choice(string.ascii_uppercase)
    lower = random.choice(string.ascii_lowercase)
    digit = random.choice(string.digits)
    special = random.choice("@$#^&*!")
    rest = ''.join(random.choices(string.ascii_letters, k=2))
    pwd_list = list(upper + lower + digit + special + rest)
    random.shuffle(pwd_list)
    return ''.join(pwd_list)


@pytest.mark.regression
@allure.epic("UI Testing")
@allure.feature("Registration Page")
@allure.story("Negative Registration - Backend")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("password_strategy, scenario", [
    ("same_password", "Занятый email + Тот же пароль"),
    ("new_valid_password", "Занятый email + Другой пароль (валидный формат)"),
    ("short_complex_password", "Занятый email + Короткий сложный пароль")
])
def test_registration_existing_user(driver, temp_user, password_strategy, scenario, sys_logger):
    with allure.step(f"Сценарий: {scenario}"):
        registration_page = RegistrationPage(driver)

        # 1. Забираем уже зарегистрированного юзера из песочницы
        existing_user = temp_user["user"]

        # 2. Определяем пароль для попытки повторной регистрации
        if password_strategy == "same_password":
            actual_password = existing_user.password
        elif password_strategy == "new_valid_password":
            actual_password = "Qwe12345!_new"
        else:
            actual_password = get_short_complex_password()

        # 3. Формируем юзера: старый email + выбранный пароль
        user = UserGenerator.get_random_user(email=existing_user.email, password=actual_password)

        registration_page.open_registration_form()
        registration_page.fill_registration_form(user)
        registration_page.set_policy_checkbox(True)

        if registration_page.submit_button_disabled():
            sys_logger.info("Фронтенд заблокировал отправку формы. До бэкенда дело не дошло.")
            pytest.skip("Тест прерван: Фронтенд не пропустил пароль к бэкенду")

        registration_page.submit_registration()

        assert registration_page.confirmation_text() == "Registration failed", "Бэкенд не отбил регистрацию!"
        actual_error_details = registration_page.confirmation_text_1()

        sys_logger.info(f"Фактический текст в модалке: '{actual_error_details}'")

        if "[object Object]" in actual_error_details:
            pytest.xfail(f"ПЛАВАЮЩИЙ БАГ ФРОНТЕНДА пойман на сценарии: '{scenario}'")
        else:
            assert "User already exists" in actual_error_details, \
                f"Ожидали текст 'User already exists', а получили '{actual_error_details}'"


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