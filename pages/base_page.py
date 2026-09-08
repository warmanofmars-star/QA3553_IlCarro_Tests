from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


class BasePage:
    # Базовый URL выносим сюда, чтобы потом легко менять окружения
    BASE_URL = "https://icarro-v1.netlify.app"
    DEFAULT_TIMEOUT = 5

    def __init__(self, driver):
        self.driver = driver

    def open_url(self, path=""):
        """Открывает указанный путь относительно базового URL"""
        self.driver.get(f"{self.BASE_URL}{path}")

    def find(self, locator):
        """Ищет элемент с ожиданием его появления в DOM"""
        return WebDriverWait(self.driver, self.DEFAULT_TIMEOUT).until(
            EC.presence_of_element_located(locator)
        )

    def click(self, locator):
        """Ждет кликабельности и кликает"""
        element = WebDriverWait(self.driver, self.DEFAULT_TIMEOUT).until(
            EC.element_to_be_clickable(locator)
        )
        element.click()

    def fill(self, locator, value):
        """Очищает поле и вводит текст"""
        element = self.find(locator)
        element.clear()
        element.send_keys(value)

    def is_element_visible(self, locator):
        """Безопасная проверка видимости элемента (возвращает True/False)"""
        try:
            WebDriverWait(self.driver, self.DEFAULT_TIMEOUT).until(
                EC.visibility_of_element_located(locator)
            )
            return True
        except TimeoutException:
            return False

    def is_element_disabled(self, locator):
        """Проверяет, заблокирован ли элемент (например, кнопка)"""
        element = self.find(locator)
        return not element.is_enabled()

    def get_text(self, locator):
        """Ожидает появления элемента и возвращает его текст"""
        element = self.find(locator)
        return element.text