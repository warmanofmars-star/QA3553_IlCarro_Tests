from selenium.webdriver.common.by import By
from pages.base_page import BasePage


class LoginPage(BasePage):
    ENDPOINT = "/login"

    # --- ЛОКАТОРЫ ---
    EMAIL_INPUT = (By.CSS_SELECTOR, "input[name='username']")
    PASSWORD_INPUT = (By.CSS_SELECTOR, "input[name='password']")
    SUBMIT_BTN = (By.CSS_SELECTOR, "button[type='submit']")
    OK_BTN = (By.XPATH, "//*[contains(text(), 'OK')]")

    # Кнопка Logout - это единственный <button> с таким классом в шапке (остальные это ссылки <a>)
    LOGOUT_BTN = (By.CSS_SELECTOR, "button.navigation-link")

    # Универсальные локаторы сообщений (без хардкода текста)
    PAGE_TITLE = (By.CSS_SELECTOR, "h1.title")
    ERROR_MESSAGE = (By.CSS_SELECTOR, ".error")  # Текст ошибки под полем ввода
    GLOBAL_MESSAGE = (By.CSS_SELECTOR, "h3")  # Текст в модальном окне (успех/фейл)

    # --- ДЕЙСТВИЯ ---
    def open(self):
        self.open_url(self.ENDPOINT)

    def fill_email(self, email):
        self.fill(self.EMAIL_INPUT, email)

    def fill_password(self, password):
        self.fill(self.PASSWORD_INPUT, password, is_secret=True) # Добавили флаг

    def submit_login(self):
        self.click(self.SUBMIT_BTN)

    def click_ok_button(self):
        self.click(self.OK_BTN)

    def login(self, email, password):
        self.fill_email(email)
        self.fill_password(password)
        self.submit_login()

    # --- ПРОВЕРКИ И ЧТЕНИЕ ТЕКСТА ---
    def is_submit_button_disabled(self):
        return self.is_element_disabled(self.SUBMIT_BTN)

    def is_logout_button_visible(self):
        return self.is_element_visible(self.LOGOUT_BTN)

    def get_error_message_text(self):
        """Читает красную ошибку под полями ввода"""
        return self.get_text(self.ERROR_MESSAGE)

    def get_global_message_text(self):
        """Читает текст из модального окна (успешный вход или ошибка бэкенда)"""
        return self.get_text(self.GLOBAL_MESSAGE)