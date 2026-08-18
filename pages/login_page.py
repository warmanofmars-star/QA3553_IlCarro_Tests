from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


class LoginPage:
    # --- ЛОКАТОРЫ ---
    EMAIL_INPUT = (By.CSS_SELECTOR, "input[name='username']")
    PASSWORD_INPUT = (By.CSS_SELECTOR, "input[name='password']")
    SUBMIT_BTN = (By.CSS_SELECTOR, "button[type='submit']")

    SUCCESS_MSG = (By.XPATH, "//h3[text()='You are logged in success']")

    # Гибкие локаторы через contains()
    LOGOUT_BTN = (By.XPATH, "//a[contains(text(), 'Log out')]")
    OK_BTN = (By.XPATH, "//button[contains(text(), 'OK')]")

    def __init__(self, driver):
        self.driver = driver

    # --- ДЕЙСТВИЯ (ACTIONS) ---
    def open(self):
        self.driver.get("https://icarro-v1.netlify.app/login")

    def fill_email(self, email):
        email_field = self.driver.find_element(*self.EMAIL_INPUT)
        email_field.clear()
        email_field.send_keys(email)

    def fill_password(self, password):
        password_field = self.driver.find_element(*self.PASSWORD_INPUT)
        password_field.clear()
        password_field.send_keys(password)

    def submit_login(self):
        self.driver.find_element(*self.SUBMIT_BTN).click()

    # Новый клик по кнопке OK
    def click_ok_button(self):
        self.driver.find_element(*self.OK_BTN).click()

    # Комплексный метод логина
    def login(self, email, password):
        self.fill_email(email)
        self.fill_password(password)
        self.submit_login()

    # --- ПРОВЕРКИ (ASSERTIONS HELPERS) ---
    def is_submit_button_disabled(self):
        submit_btn = self.driver.find_element(*self.SUBMIT_BTN)
        return not submit_btn.is_enabled()

    def is_success_message_visible(self):
        try:
            WebDriverWait(self.driver, timeout=5).until(
                EC.visibility_of_element_located(self.SUCCESS_MSG)
            )
            return True
        except TimeoutException:
            return False

    def is_logout_button_visible(self):
        try:
            WebDriverWait(self.driver, timeout=5).until(
                EC.visibility_of_element_located(self.LOGOUT_BTN)
            )
            return True
        except TimeoutException:
            return False