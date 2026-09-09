from selenium.webdriver.common.by import By
from pages.base_page import BasePage


# Наследуемся от BasePage
class LoginPage(BasePage):
    ENDPOINT = "/login"

    # --- ЛОКАТОРЫ ---
    EMAIL_INPUT = (By.CSS_SELECTOR, "input[name='username']")
    PASSWORD_INPUT = (By.CSS_SELECTOR, "input[name='password']")
    SUBMIT_BTN = (By.CSS_SELECTOR, "button[type='submit']")

    SUCCESS_MSG = (By.XPATH, "//h3[text()='You are logged in success']")
    LOGOUT_BTN = (By.XPATH, "//*[contains(@class, 'navigation-link') and contains(., 'Log out')]")
    OK_BTN = (By.XPATH, "//*[contains(text(), 'OK')]")

    PAGE_TITLE = (By.CSS_SELECTOR, "h1.title")
    ERROR_WRONG_EMAIL = (By.XPATH, "//div[contains(text(), 'Wrong email format')]")
    ERROR_REQUIRED_FIELD = (By.XPATH, "//div[contains(text(), 'is required')]")
    ERROR_LOGIN_FAILED = (By.XPATH, "//h3[contains(text(), 'Login failed')]")

    # --- ДЕЙСТВИЯ ---
    def open(self):
        self.open_url(self.ENDPOINT)  # Используем метод из BasePage

    def fill_email(self, email):
        self.fill(self.EMAIL_INPUT, email)

    def fill_password(self, password):
        self.fill(self.PASSWORD_INPUT, password)

    def submit_login(self):
        self.click(self.SUBMIT_BTN)

    def click_ok_button(self):
        self.click(self.OK_BTN)

    def login(self, email, password):
        self.fill_email(email)
        self.fill_password(password)
        self.submit_login()


    # --- ПРОВЕРКИ ---
    def is_submit_button_disabled(self):
        return self.is_element_disabled(self.SUBMIT_BTN)

    def is_success_message_visible(self):
        return self.is_element_visible(self.SUCCESS_MSG)

    def is_logout_button_visible(self):
        return self.is_element_visible(self.LOGOUT_BTN)

    def is_error_wrong_email_visible(self):
        return self.is_element_visible(self.ERROR_WRONG_EMAIL)

    def is_error_required_field_visible(self):
        return self.is_element_visible(self.ERROR_REQUIRED_FIELD)

    def is_login_failed_message_visible(self):
        return self.is_element_visible(self.ERROR_LOGIN_FAILED)