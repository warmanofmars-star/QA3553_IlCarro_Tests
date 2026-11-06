import logging
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import allure
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from pages.base_page import BasePage

logger = logging.getLogger(__name__)

class ResultsPage(BasePage):
    # --- ЛОКАТОРЫ ---
    CAR_CARD_LINK = (By.CSS_SELECTOR, "a.car-container")
    CAR_IMAGE = (By.CSS_SELECTOR, ".car-img-container")
    CAR_TITLE = (By.CSS_SELECTOR, ".details-card > div > div:first-child")
    CAR_PRICE = (By.CSS_SELECTOR, ".car-price-value")

    # --- ПРОВЕРКИ И ОЖИДАНИЯ ---
    @allure.step("Ожидание завершения поиска (смена URL)")
    def wait_for_search_request_to_complete(self):
        logger.info("Ждем обновления URL с параметрами поиска...")
        WebDriverWait(self.driver, 10).until(
            lambda d: "city=" in d.current_url and "from=" in d.current_url,
            message="Поисковый запрос не выполнился: URL не обновился!"
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
