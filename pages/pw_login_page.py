import allure
from playwright.sync_api import Page, expect
from pages.pw_base_page import PwBasePage


class PwLoginPage(PwBasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.endpoint = "/login"

        # --- ЛОКАТОРЫ ---
        # В Playwright мы сохраняем готовые объекты локаторов
        self.email_input = page.locator("input[name='username']")
        self.password_input = page.locator("input[name='password']")
        self.submit_btn = page.locator("button[type='submit']")
        self.error_message = page.locator(".error")
        # Используем мощный селектор "по роли", который Playwright понимает из коробки
        self.ok_btn = page.get_by_role("link", name="OK", exact=True)
        self.global_message = page.locator("h3")
        self.logout_btn = page.locator("button.navigation-link")

    # --- ДЕЙСТВИЯ ---
    def open(self):
        self.open_url(self.endpoint)

    @allure.step("Ввод email")
    def fill_email(self, email: str):
        self.email_input.fill(email)

    @allure.step("Ввод пароля")
    def fill_password(self, password: str):
        self.password_input.fill(password)

    @allure.step("Клик по кнопке отправки")
    def submit_login(self):
        self.submit_btn.click()

    def login(self, email, password):
        self.fill_email(email)
        self.fill_password(password)
        self.submit_login()

    # --- ПРОВЕРКИ ---
    # Переносим магию expect() прямо внутрь Page Object
    @allure.step("Проверка успешного сообщения об авторизации")
    def check_success_message(self):
        expect(self.global_message).to_have_text("You are logged in success")

    @allure.step("Закрытие модального окна")
    def click_ok_button(self):
        self.ok_btn.click()

    @allure.step("Проверка, что кнопка Logout появилась")
    def check_logout_button_visible(self):
        expect(self.logout_btn).to_be_visible()

    #for Playwright:
    @allure.step("Проверка ошибки валидации: {expected_text}")
    def check_error_message(self, expected_text: str):
        # Playwright сам будет ждать, пока текст не совпадет!
        expect(self.error_message).to_have_text(expected_text)

    @allure.step("Проверка блокировки кнопки Submit")
    def check_submit_button_disabled(self):
        expect(self.submit_btn).to_be_disabled()

    @allure.step("Снятие фокуса (клик по фону)")
    def remove_focus(self):
        self.page.locator("body").click()