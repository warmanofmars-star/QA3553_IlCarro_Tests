from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


class LoginPage:
    # --- ЛОКАТОРЫ ---
    EMAIL_INPUT = (By.CSS_SELECTOR, "input[name='username']")
    PASSWORD_INPUT = (By.CSS_SELECTOR, "input[name='password']")
    SUBMIT_BTN = (By.CSS_SELECTOR, "button[type='submit']")

    # Для позитивных тестов
    SUCCESS_MSG = (By.XPATH, "//h3[text()='You are logged in success']")
    LOGOUT_BTN = (By.XPATH, "//*[contains(@class, 'navigation-link') and contains(., 'Log out')]")
    OK_BTN = (By.XPATH, "//*[contains(text(), 'OK')]")

    # НОВЫЕ ЛОКАТОРЫ: Для негативных тестов
    PAGE_TITLE = (By.CSS_SELECTOR, "h1.title")  # Заголовок для "холостого" клика
    ERROR_WRONG_EMAIL = (By.XPATH, "//div[contains(text(), 'Wrong email format')]")
    ERROR_REQUIRED_FIELD = (By.XPATH,
                            "//div[contains(text(), 'is required')]")  # Универсальный локатор для пустых полей
    ERROR_LOGIN_FAILED = (By.XPATH, "//h3[contains(text(), 'Login failed')]")

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

    def click_ok_button(self):
        WebDriverWait(self.driver, timeout=5).until(
            EC.element_to_be_clickable(self.OK_BTN)
        ).click()

    def login(self, email, password):
        self.fill_email(email)
        self.fill_password(password)
        self.submit_login()

    # Новый метод: клик в "пустоту" (снимаем фокус с поля ввода)
    def click_empty_space(self):
        self.driver.find_element(*self.PAGE_TITLE).click()

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

    # НОВЫЕ ПРОВЕРКИ: Для текстов ошибок
    def is_error_wrong_email_visible(self):
        try:
            WebDriverWait(self.driver, timeout=3).until(
                EC.visibility_of_element_located(self.ERROR_WRONG_EMAIL)
            )
            return True
        except TimeoutException:
            return False

    def is_error_required_field_visible(self):
        try:
            WebDriverWait(self.driver, timeout=3).until(
                EC.visibility_of_element_located(self.ERROR_REQUIRED_FIELD)
            )
            return True
        except TimeoutException:
            return False

    def is_login_failed_message_visible(self):
        try:
            WebDriverWait(self.driver, timeout=5).until(
                EC.visibility_of_element_located(self.ERROR_LOGIN_FAILED)
            )
            return True
        except TimeoutException:
            return False