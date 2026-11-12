import allure
from playwright.sync_api import Page

from pages.pw_base_page import PwBasePage


class PwRegistrationPage(PwBasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.endpoint = "/register"

        self.first_name_input = page.locator("[name='firstName']")
        self.last_name_input = page.locator("[name='lastName']")
        self.email_input = page.locator("[name='username']")
        self.password_input = page.locator("[name='password']")
        self.terms_checkbox = page.locator("#terms-of-use")
        self.submit_btn = page.locator("button[type='submit']")
        # Окно результата регистрации (FE: Register): role=dialog, заголовок h3, кнопка OK
        self.dialog = page.get_by_role("dialog")
        self.dialog_title = self.dialog.locator("h3")
        self.dialog_ok_btn = self.dialog.get_by_role("button", name="OK")

    def open(self):
        self.open_url(self.endpoint)

    def fill_form(self, user):
        with allure.step(f"Заполнение формы регистрации: {user.email}"):
            self.first_name_input.fill(user.name)
            self.last_name_input.fill(user.last_name)
            self.email_input.fill(user.email)
            # Пароль — не аргумент шага: в отчёт он не попадает
            self.password_input.fill(user.password)
            self.terms_checkbox.check()

    @allure.step("Клик «Y'alla!»")
    def submit(self):
        self.submit_btn.click()
