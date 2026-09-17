import os
import allure
from playwright.sync_api import Page
from pages.pw_login_page import PwLoginPage

VALID_EMAIL = os.getenv("USER_EMAIL")
VALID_PASSWORD = os.getenv("USER_PASSWORD")

@allure.epic("Playwright Testing")
@allure.feature("Login")
@allure.story("Positive Login (POM)")
@allure.title("Успешная авторизация (Playwright + POM)")
def test_pw_login_success(page: Page):
    # Инициализируем наш новый Page Object
    pw_login_page = PwLoginPage(page)

    # 1. Открываем страницу и логинимся
    pw_login_page.open()
    pw_login_page.login(VALID_EMAIL, VALID_PASSWORD)

    # 2. Проверяем результаты
    pw_login_page.check_success_message()
    pw_login_page.click_ok_button()
    pw_login_page.check_logout_button_visible()