from selenium.webdriver.support.abstract_event_listener import AbstractEventListener
from selenium.common.exceptions import WebDriverException, NoSuchElementException
from utils.logger import get_logger

class IlCarroListener(AbstractEventListener):
    def __init__(self):
        self.logger = get_logger("UI")

    def before_navigate_to(self, url, driver):
        self.logger.info(f"Переход по ссылке: {url}")

    def before_find(self, by, value, driver):
        self.logger.info(f"Поиск элемента -> By: {by}, Value: '{value}'")

    def before_click(self, element, driver):
        try:
            element_text = element.text
            tag_name = element.tag_name
            self.logger.info(f"Клик по элементу <{tag_name}> с текстом: '{element_text}'")
        except WebDriverException:
            self.logger.info("Клик по элементу (текст недоступен)")

    def before_change_value_of(self, element, driver):
        self.logger.info("Ввод данных в поле формы...")

    def on_exception(self, exception, driver):
        if isinstance(exception, NoSuchElementException):
            return
        self.logger.error(f"ПЕРЕХВАТ ОШИБКИ WEBDRIVER: {exception}")