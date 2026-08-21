import random
import uuid

from models.user import User
from pages.registration_page import RegistrationPage


# --- НОВЫЙ ТЕСТ: Проверка навигации (меню) ---
def test_navigation_to_registration(driver):
    registration_page = RegistrationPage(driver)

    # Заходим на главную и кликаем по кнопке в верхнем меню
    registration_page.open_main_page()
    registration_page.click_registration_button_in_menu()

    # Проверяем, что URL изменился на правильный
    current_url = registration_page.get_current_url()
    assert "register" in current_url, f"Переход из меню не удался. Текущий URL: {current_url}"


# --- ТВОИ ТЕСТЫ ДЛЯ ФОРМЫ (Атомарные) ---
def test_registration_success(driver):
    registration_page = RegistrationPage(driver)
    random_suffix = uuid.uuid4().hex[:8]

    user = User(
        name="Tonny",
        last_name="Molly",
        email=f"tony_{random_suffix}@gmail.com",
        password="Password123$"
    )

    print(random_suffix)

    registration_page.open_registration_form()
    registration_page.fill_registration_form(user)
    registration_page.check_policy()
    registration_page.submit_registration()

    assert registration_page.confirmation_text() == "Registered", "Заголовок об успехе не появился!"
    assert registration_page.confirmation_text_1() == "You are logged in success", "Текст успешного входа не совпадает!"
    registration_page.close_window()


def test_registration_with_empty_name(driver):
    registration_page = RegistrationPage(driver)

    user = User(
        name="",
        last_name="Molly",
        email="tony@gmail.com",
        password="Password123$"
    )

    registration_page.open_registration_form()
    registration_page.fill_registration_form(user)
    registration_page.check_policy()
    registration_page.submit_registration()

    assert registration_page.error_message_text() == "Name is required", "Ошибка пустого имени не появилась"
    assert registration_page.submit_button_disabled() == True, "Кнопка Y'alla! не заблокировалась при пустом имени"


def test_registration_with_empty_last_name(driver):
    registration_page = RegistrationPage(driver)

    user = User(
        name="Tony",
        last_name="",
        email="tony@gmail.com",
        password="Password123$"
    )

    registration_page.open_registration_form()
    registration_page.fill_registration_form(user)
    registration_page.check_policy()
    registration_page.submit_registration()

    assert registration_page.error_message_text() == "Last name is required", "Ошибка пустой фамилии не появилась"
    assert registration_page.submit_button_disabled() == True, "Кнопка не заблокировалась при пустой фамилии"


def test_registration_with_wrong_email(driver):
    registration_page = RegistrationPage(driver)

    user = User(
        name="Tony",
        last_name="Molly",
        email="tonygmail.com",
        password="Password123$"
    )

    registration_page.open_registration_form()
    registration_page.fill_registration_form(user)
    registration_page.check_policy()
    registration_page.submit_registration()

    assert registration_page.error_message_text() == "Wrong email format", "Ошибка формата email не появилась"
    assert registration_page.submit_button_disabled() == True, "Кнопка не заблокировалась при кривом email"


def test_registration_with_empty_email(driver):
    registration_page = RegistrationPage(driver)

    user = User(
        name="Tony",
        last_name="Molly",
        email="",
        password="Password123$"
    )

    registration_page.open_registration_form()
    registration_page.fill_registration_form(user)
    registration_page.check_policy()
    registration_page.submit_registration()

    assert registration_page.error_message_text() == "Email is required", "Ошибка пустого email не появилась"
    assert registration_page.submit_button_disabled() == True, "Кнопка не заблокировалась при пустом email"


def test_registration_with_wrong_password(driver):
    registration_page = RegistrationPage(driver)

    user = User(
        name="Tony",
        last_name="Molly",
        email="tony@gmail.com",
        password="P123$"
    )

    registration_page.open_registration_form()
    registration_page.fill_registration_form(user)
    registration_page.check_policy()
    registration_page.submit_registration()

    assert registration_page.error_message_text() == "Password must contain minimum 6 symbols", "Ошибка короткого пароля не появилась"
    assert registration_page.submit_button_disabled() == True, "Кнопка не заблокировалась при коротком пароле"


def test_registration_with_empty_password(driver):
    registration_page = RegistrationPage(driver)

    user = User(
        name="Tony",
        last_name="Molly",
        email="tony@gmail.com",
        password=""
    )

    registration_page.open_registration_form()
    registration_page.fill_registration_form(user)
    registration_page.check_policy()
    registration_page.submit_registration()

    assert registration_page.error_message_text() == "Password is required", "Ошибка пустого пароля не появилась"
    assert registration_page.submit_button_disabled() == True, "Кнопка не заблокировалась при пустом пароле"


def test_registration_without_check_box(driver):
    registration_page = RegistrationPage(driver)

    user = User(
        name="Tony",
        last_name="Molly",
        email="tony@gmail.com",
        password="Password133$"
    )

    registration_page.open_registration_form()
    registration_page.fill_registration_form(user)

    # Кликаем дважды, чтобы в итоге чекбокс остался пустым
    registration_page.check_policy()
    registration_page.check_policy()
    registration_page.submit_registration()

    assert registration_page.error_message_text() == "You must accept the terms", "Ошибка чекбокса не появилась"
    assert registration_page.submit_button_disabled() == True, "Кнопка не заблокировалась без чекбокса"