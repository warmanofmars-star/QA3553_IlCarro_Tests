import logging
import re
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import allure
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class ResultsPage(BasePage):
    # --- ЛОКАТОРЫ ---
    CAR_CARD_LINK = (By.CSS_SELECTOR, "a.car-container")
    CAR_IMAGE = (By.CSS_SELECTOR, ".car-img-container")
    CAR_TITLE = (By.CSS_SELECTOR, ".details-card > div > div:first-child")
    CAR_PRICE = (By.CSS_SELECTOR, ".car-price-value")
    # Пагинация под выдачей (FE: Search): «Rows per page», подпись «1-10 of 14», кнопка Next
    ROWS_PER_PAGE_SELECT = (By.CSS_SELECTOR, ".search-results select")
    NEXT_PAGE_BTN = (By.CSS_SELECTOR, ".search-results button[title='Next']")
    RANGE_LABEL = (By.XPATH, "//div[contains(@class, 'search-results')]//span[contains(., ' of ')]")
    RANGE_PATTERN = re.compile(r"(\d+)-(\d+) of (\d+)")

    # --- ПРОВЕРКИ И ОЖИДАНИЯ ---
    @allure.step("Ожидание завершения поиска (смена URL)")
    def wait_for_search_request_to_complete(self):
        logger.info("Ждем обновления URL с параметрами поиска...")
        WebDriverWait(self.driver, 10).until(
            lambda d: "city=" in d.current_url and "from=" in d.current_url,
            message="Поисковый запрос не выполнился: URL не обновился!",
        )

    # --- ДЕЙСТВИЯ ---
    @allure.step("Показать выдачу по {size} карточек на странице")
    def show_page_size(self, size: int):
        """Пагинация клиентская, её параметры — в URL (REQ-UI-SEARCH-04): меняем size и открываем первую страницу."""
        parts = urlsplit(self.driver.current_url)
        query = {key: values[0] for key, values in parse_qs(parts.query).items()}
        query.update({"page": "0", "size": str(size)})
        self.driver.get(urlunsplit(parts._replace(query=urlencode(query))))

    @allure.step("Поиск карточки машины {serial_number} в выдаче")
    def get_car_details(self, serial_number: str, timeout: int = 15) -> dict | None:
        """Данные карточки нашей машины или None, если её нет в выдаче.

        Карточка — ссылка на страницу машины /cars/{serialNumber} (FE: Search), по ней и ищем.
        """
        card_locator = (By.CSS_SELECTOR, f"a.car-container[href$='/cars/{serial_number}']")
        try:
            card = WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located(card_locator))
        except TimeoutException:
            return None

        img_element = card.find_element(*self.CAR_IMAGE)
        return {
            "serial_number": serial_number,
            "title": card.find_element(*self.CAR_TITLE).text,
            "price": card.find_element(*self.CAR_PRICE).text,
            "has_image": "url" in (img_element.get_attribute("style") or ""),
        }

    # --- ПАГИНАЦИЯ ---
    def url_query(self) -> dict[str, str]:
        return {key: values[0] for key, values in parse_qs(urlsplit(self.driver.current_url).query).items()}

    @allure.step("Ожидание параметров {expected} в URL")
    def wait_for_url_query(self, expected: dict[str, str]) -> dict[str, str]:
        """Параметры URL, когда они совпали с expected, или последние прочитанные, если не совпали."""
        try:
            WebDriverWait(self.driver, self.DEFAULT_TIMEOUT).until(
                lambda d: all(self.url_query().get(key) == value for key, value in expected.items())
            )
        except TimeoutException:
            logger.warning(f"Параметры URL не стали {expected}: {self.url_query()}")
        return self.url_query()

    @allure.step("Ожидание {expected} карточек на странице выдачи")
    def wait_for_cards_count(self, expected: int) -> int:
        """Число карточек, когда оно стало expected, или последнее прочитанное, если не стало."""
        try:
            WebDriverWait(self.driver, self.DEFAULT_TIMEOUT).until(
                lambda d: len(d.find_elements(*self.CAR_CARD_LINK)) == expected
            )
        except TimeoutException:
            logger.warning(f"Карточек на странице не стало {expected}")
        return len(self.driver.find_elements(*self.CAR_CARD_LINK))

    @allure.step("Чтение числа машин в выдаче из подписи пагинации")
    def get_results_total(self) -> int:
        label = self.get_text(self.RANGE_LABEL)
        match = self.RANGE_PATTERN.search(label)
        if not match:
            raise ValueError(f"Подпись пагинации не в формате «1-10 of N»: {label!r}")
        return int(match.group(3))

    def get_page_size_options(self) -> list[str]:
        return [option.text for option in Select(self.find(self.ROWS_PER_PAGE_SELECT)).options]

    @allure.step("Rows per page: выбор {size}")
    def choose_page_size(self, size: int):
        Select(self.find(self.ROWS_PER_PAGE_SELECT)).select_by_value(str(size))

    @allure.step("Клик Next: следующая страница выдачи")
    def click_next_page(self):
        self.click(self.NEXT_PAGE_BTN)
