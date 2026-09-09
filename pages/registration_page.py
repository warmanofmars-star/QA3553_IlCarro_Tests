import allure
from selenium.webdriver.common.by import By
from pages.base_page import BasePage

class RegistrationPage(BasePage):
    # --- ЛОКАТОРЫ ---
    NAV_REGISTRATION_BTN = (By.CSS_SELECTOR, "[href='/register']")
    NAME_INPUT = (By.CSS_SELECTOR, "[name='firstName']")
    LAST_NAME_INPUT = (By.CSS_SELECTOR, "[name='lastName']")
    EMAIL_INPUT = (By.CSS_SELECTOR, "[name='username']")
    PASSWORD_INPUT = (By.CSS_SELECTOR, "[name='password']")
    YALLA_BTN = (By.XPATH, "//button[text()='Y’alla!']")
    CHECK_BOX = (By.ID, "terms-of-use")
    CONFIRMATION_TEXT = (By.CSS_SELECTOR, "h3")
    CONFIRMATION_TEXT_1 = (By.CSS_SELECTOR, "p")
    OK_BTN = (By.XPATH, "//*[text()='OK']")
    ERROR_MESSAGE = (By.CLASS_NAME, "error")

    # --- НАВИГАЦИЯ ---
    def open_main_page(self):
        self.open_url("/")

    def click_registration_button_in_menu(self):
        self.click(self.NAV_REGISTRATION_BTN)

    def get_current_url(self):
        return self.driver.current_url

    def open_registration_form(self):
        self.open_url("/register")

    # --- ДЕЙСТВИЯ С ФОРМОЙ ---
    def fill_name(self, name):
        self.fill(self.NAME_INPUT, name)

    def fill_last_name(self, last_name):
        self.fill(self.LAST_NAME_INPUT, last_name)

    def fill_email(self, email):
        self.fill(self.EMAIL_INPUT, email)

    def fill_password(self, password):
        self.fill(self.PASSWORD_INPUT, password)

    def submit_registration(self):
        self.click(self.YALLA_BTN)

    @allure.step("Установка чекбокса 'Terms of use' в состояние: {state}")
    def set_policy_checkbox(self, state: bool):
        element = self.find(self.CHECK_BOX)
        # Если текущее состояние не совпадает с тем, что нам нужно — кликаем
        if element.is_selected() != state:
            self.click(self.CHECK_BOX)

    def fill_registration_form(self, user):
        self.fill_name(user.name)
        self.fill_last_name(user.last_name)
        self.fill_email(user.email)
        self.fill_password(user.password)

    def close_window(self):
        self.click(self.OK_BTN)

    # --- ПРОВЕРКИ И ЧТЕНИЕ ТЕКСТА ---
    def confirmation_text(self):
        return self.get_text(self.CONFIRMATION_TEXT)

    def confirmation_text_1(self):
        return self.get_text(self.CONFIRMATION_TEXT_1)

    def error_message_text(self):
        return self.get_text(self.ERROR_MESSAGE)

    def submit_button_disabled(self):
        return self.is_element_disabled(self.YALLA_BTN)