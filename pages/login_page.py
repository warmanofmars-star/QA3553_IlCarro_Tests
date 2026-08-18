from selenium.webdriver.common.by import By


class LoginPage:
    EMAIL_INPUT = (By.CSS_SELECTOR, "input[name='username']")
    PASSWORD_INPUT = (By.CSS_SELECTOR, "input[name='password']")
    SUBMIT_BTN = (By.CSS_SELECTOR, "button[type='submit']")

    # НОВЫЙ ЛОКАТОР: ищем заголовок h3 с точным текстом
    SUCCESS_MSG = (By.XPATH, "//h3[text()='You are logged in success']")

    def __init__(self, driver):
        self.driver = driver

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

    def login(self, email, password):
        self.fill_email(email)
        self.fill_password(password)
        self.submit_login()

    def is_submit_button_disabled(self):
        submit_btn = self.driver.find_element(*self.SUBMIT_BTN)
        return not submit_btn.is_enabled()

    # НОВЫЙ МЕТОД: получаем текст из всплывающего окна
    def get_success_message_text(self):
        return self.driver.find_element(*self.SUCCESS_MSG).text