import os
import allure
from playwright.sync_api import Page, expect

VALID_EMAIL = os.getenv("USER_EMAIL")
VALID_PASSWORD = os.getenv("USER_PASSWORD")


@allure.epic("Playwright Testing")
@allure.feature("Login")
@allure.story("Positive Login")
@allure.title("Успешная авторизация (Playwright версия)")
def test_pw_login_success(page: Page):
    with allure.step("1. Открытие страницы логина"):
        # page.goto сам дождется, пока страница полностью загрузится
        page.goto("https://icarro-v1.netlify.app/login")

    with allure.step("2. Ввод учетных данных и отправка формы"):
        # Playwright сам ждет, пока поля появятся и станут интерактивными!
        # Пароль нигде в Allure не логируется, всё безопасно.
        page.locator("input[name='username']").fill(VALID_EMAIL)
        page.locator("input[name='password']").fill(VALID_PASSWORD)
        page.locator("button[type='submit']").click()

    with allure.step("3. Проверка успешной авторизации"):
        # Умный expect() будет опрашивать DOM, пока не появится нужный текст
        expect(page.locator("h3")).to_have_text("You are logged in success")

        page.get_by_role("link", name="OK", exact=True).click()

        # Ждем появления кнопки Logout
        expect(page.locator("button.navigation-link")).to_be_visible()