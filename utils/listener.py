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
            tag_name = element.tag_name

            # 1. Запрещаем собирать текст с глобальных контейнеров
            if tag_name.lower() in ['body', 'html', 'form']:
                self.logger.info(f"Клик по фону <{tag_name}> (снятие фокуса/сабмит)")
            else:
                # 2. Вычитываем текст и убираем переносы строк для красоты лога
                element_text = element.text.replace('\n', ' ').strip()

                # 3. Защита от спама: обрезаем текст длиннее 50 символов
                if len(element_text) > 50:
                    element_text = element_text[:47] + "..."

                self.logger.info(f"Клик по элементу <{tag_name}> с текстом: '{element_text}'")

        except WebDriverException:
            self.logger.info("Клик по элементу (текст недоступен)")

    def before_change_value_of(self, element, driver):
        self.logger.info("Ввод данных в поле формы...")

    def on_exception(self, exception, driver):
        if isinstance(exception, NoSuchElementException):
            return
        self.logger.error(f"ПЕРЕХВАТ ОШИБКИ WEBDRIVER: {exception}")