import logging
import allure
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
        # Убеждаемся, что форма отправилась и параметры появились в URL
        WebDriverWait(self.driver, 10).until(
            lambda d: "city=" in d.current_url and "from=" in d.current_url,
            message="Поисковый запрос не выполнился: URL не обновился!"
        )

    @allure.step("Проверка, есть ли найденные машины")
    def has_cars(self):
        # Быстрый опрос DOM без долгого таймаута
        cars = self.driver.find_elements(*self.CAR_CARD_LINK)
        return len(cars) > 0

    # --- ДЕЙСТВИЯ ---
    @allure.step("Получение данных первой машины из списка")
    def get_first_car_details(self):
        cars = self.driver.find_elements(*self.CAR_CARD_LINK)
        if not cars:
            return None

        first_car = cars[0]
        title = first_car.find_element(*self.CAR_TITLE).text
        price = first_car.find_element(*self.CAR_PRICE).text

        href = first_car.get_attribute("href")
        car_id = href.split("/")[-1] if href else None

        img_element = first_car.find_element(*self.CAR_IMAGE)
        bg_image_style = img_element.get_attribute("style")

        return {
            "id": car_id,
            "title": title,
            "price": price,
            "has_image": "url" in bg_image_style
        }