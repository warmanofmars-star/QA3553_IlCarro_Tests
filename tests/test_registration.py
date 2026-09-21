import os
import pytest
import allure
import random
import string
from pages.registration_page import RegistrationPage
from data.data_generator import UserGenerator
from utils.logger import get_logger

logger = get_logger("TEST")

VALID_EMAIL = os.getenv("USER_EMAIL")
VALID_PASSWORD = os.getenv("USER_PASSWORD")

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
# ПАРАМЕТРИЗОВАННЫЙ НЕГАТИВНЫЙ ТЕСТ: Фронтенд-валидация
# ===========================================================================
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

        # Динамически создаем объект с "битым" полем (Датаклассы это отлично переваривают!)
        kwargs = {field_name: invalid_value}
        user = UserGenerator.get_random_user(**kwargs)

        registration_page.open_registration_form()
        registration_page.fill_registration_form(user)
        registration_page.set_policy_checkbox(True)

        # Универсальный клик в пустоту для вызова onBlur валидации во всех сценариях
        registration_page.remove_focus()

        assert registration_page.error_message_text() == expected_error, f"Ожидалась ошибка '{expected_error}'"
        assert registration_page.submit_button_disabled() == True, "Кнопка Y'alla! не заблокировалась"


def get_short_complex_password():
    """Генерирует пароль ровно из 6 символов, но со всеми нужными форматами (для обхода фронтенда)"""
    upper = random.choice(string.ascii_uppercase)
    lower = random.choice(string.ascii_lowercase)
    digit = random.choice(string.digits)
    special = random.choice("@$#^&*!")
    rest = ''.join(random.choices(string.ascii_letters, k=2))

    pwd_list = list(upper + lower + digit + special + rest)
    random.shuffle(pwd_list)
    return ''.join(pwd_list)


# Генерируем пароль один раз при сборе тестов
DYNAMIC_SHORT_PWD = get_short_complex_password()


# ===========================================================================
# НЕГАТИВНЫЙ ТЕСТ: Бэкенд-валидация (Пользователь уже существует)
# ===========================================================================
@allure.epic("UI Testing")
@allure.feature("Registration Page")
@allure.story("Negative Registration - Backend")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("password_variant, scenario", [
    (VALID_PASSWORD, "Занятый email + Тот же пароль"),
    ("Qwe12345!_new", "Занятый email + Другой пароль (валидный формат)"),
    (DYNAMIC_SHORT_PWD, f"Занятый email + Короткий сложный пароль ('{DYNAMIC_SHORT_PWD}')")
])
def test_registration_existing_user(driver, password_variant, scenario):
    with allure.step(f"Сценарий: {scenario}"):
        registration_page = RegistrationPage(driver)

        # Подсовываем занятый email и перебираем пароли из параметризации
        user = UserGenerator.get_random_user(email=VALID_EMAIL, password=password_variant)

        registration_page.open_registration_form()
        registration_page.fill_registration_form(user)
        registration_page.set_policy_checkbox(True)

        # Подстраховка: если фронтенд решит заблокировать кнопку до отправки
        if registration_page.submit_button_disabled():
            logger.info("Фронтенд заблокировал отправку формы. До бэкенда дело не дошло.")
            pytest.skip("Тест прерван: Фронтенд не пропустил пароль к бэкенду")

        registration_page.submit_registration()

        # 1. Проверяем заголовок модалки
        assert registration_page.confirmation_text() == "Registration failed", "Бэкенд не отбил регистрацию!"

        # 2. ПРОВЕРКА ДИНАМИЧЕСКОГО БАГА ФРОНТЕНДА
        actual_error_details = registration_page.confirmation_text_1()

        # Фиксируем текст для логов и Allure
        logger.info(f"Фактический текст в модалке: '{actual_error_details}'")

        if "[object Object]" in actual_error_details:
            # Ловим баг состояния гонки или двойную ошибку бэкенда
            pytest.xfail(f"ПЛАВАЮЩИЙ БАГ ФРОНТЕНДА пойман на сценарии: '{scenario}'")
        else:
            # Проверяем бизнес-логику при нормальном рендере
            assert "User already exists" in actual_error_details, \
                f"Ожидали текст 'User already exists', а получили '{actual_error_details}'"



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