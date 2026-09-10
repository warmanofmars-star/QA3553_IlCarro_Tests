import allure
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Импортируем наш инженерный логгер
from utils.logger import get_logger

# Инициализируем логгер один раз для всего базового класса
logger = get_logger()


class BasePage:
    BASE_URL = "https://icarro-v1.netlify.app"
    DEFAULT_TIMEOUT = 5

    def __init__(self, driver):
        self.driver = driver

    @allure.step("Открытие URL: {path}")
    def open_url(self, path=""):
        full_url = f"{self.BASE_URL}{path}"
        logger.info(f"Переходим по ссылке: {full_url}")
        self.driver.get(full_url)

    @allure.step("Поиск элемента: {locator}")
    def find(self, locator):
        logger.info(f"Ищем элемент: {locator}")
        return WebDriverWait(self.driver, self.DEFAULT_TIMEOUT).until(
            EC.presence_of_element_located(locator)
        )

    @allure.step("Клик по элементу: {locator}")
    def click(self, locator):
        logger.info(f"Кликаем по элементу: {locator}")
        element = WebDriverWait(self.driver, self.DEFAULT_TIMEOUT).until(
            EC.element_to_be_clickable(locator)
        )
        element.click()


    def fill(self, locator, value, is_secret=False):
        # Если флаг is_secret=True, заменяем текст на звездочки для логов
        display_value = "********" if is_secret else value

        with allure.step(f"Ввод текста '{display_value}' в поле: {locator}"):
            logger.info(f"Вводим текст '{display_value}' в поле: {locator}")
            element = self.find(locator)
            element.clear()
            element.send_keys(value)  # А вот в сам браузер отправляем реальный пароль!

    @allure.step("Проверка видимости элемента: {locator}")
    def is_element_visible(self, locator):
        logger.info(f"Проверяем видимость элемента: {locator}")
        try:
            WebDriverWait(self.driver, self.DEFAULT_TIMEOUT).until(
                EC.visibility_of_element_located(locator)
            )
            return True
        except TimeoutException:
            # Если элемент не появился, пишем warning в консоль/файл
            logger.warning(f"Элемент {locator} не появился в течение {self.DEFAULT_TIMEOUT} сек.")
            return False

    @allure.step("Проверка блокировки элемента: {locator}")
    def is_element_disabled(self, locator):
        logger.info(f"Проверяем блокировку элемента: {locator}")
        element = self.find(locator)
        return not element.is_enabled()

    @allure.step("Получение текста из элемента: {locator}")
    def get_text(self, locator):
        logger.info(f"Получаем текст из элемента: {locator}")
        element = self.find(locator)
        return element.text

    @allure.step("Проверка невидимости элемента: {locator}")
    def is_element_invisible(self, locator):
        logger.info(f"Проверяем исчезновение элемента: {locator}")
        try:
            # Ждем, пока элемент физически исчезнет или станет display: none
            WebDriverWait(self.driver, self.DEFAULT_TIMEOUT).until(
                EC.invisibility_of_element_located(locator)
            )
            return True
        except TimeoutException:
            logger.error(f"Элемент {locator} не исчез в течение {self.DEFAULT_TIMEOUT} сек.")
            return False

    @allure.step("Снятие фокуса с элемента (клик по фону)")
    def remove_focus(self):
        logger.info("Кликаем по пустому месту (body) для снятия фокуса")
        self.click((By.CSS_SELECTOR, "body"))