import logging
import allure
import pytest

from pages.search_page import SearchPage
from data.data_generator import SearchDataGenerator
from pages.results_page import ResultsPage

logger = logging.getLogger(__name__)

@allure.epic("UI Testing")
@allure.feature("Search Page")
@allure.story("Search Cars Dynamic Flow")
@allure.severity(allure.severity_level.CRITICAL)
def test_search_form_dynamic(driver):
    search_page = SearchPage(driver)
    results_page = ResultsPage(driver)

    city = SearchDataGenerator.get_random_city()
    start_date, end_date = SearchDataGenerator.get_safe_future_dates()
    expected_dates_str = f"{start_date.month}/{start_date.day}/{start_date.year} - {end_date.month}/{end_date.day}/{end_date.year}"

    with allure.step(f"Параметры: Город - {city}, Даты: {expected_dates_str}"):
        pass

    search_page.open()
    search_page.fill_city(city)
    search_page.select_date_range(start_date, end_date)
    search_page.click(search_page.CITY_INPUT)

    assert search_page.is_submit_button_disabled() == False, "Кнопка Yalla! не разблокировалась!"

    search_page.click_submit_button()

    # 1. Ждем факта отправки поискового запроса (смена URL)
    results_page.wait_for_search_request_to_complete()

    # 2. Ветвление: машины найдены или пустая выдача
    if not results_page.has_cars():
        logger.info(f"В городе '{city}' на выбранные даты нет доступных машин. Отработало пустое состояние.")
        with allure.step(f"В городе '{city}' машин нет — пустое состояние отработало штатно"):
            pass
    else:
        first_car = results_page.get_first_car_details()
        logger.info(f"Найдена машина: ID {first_car['id']}, {first_car['title']} за ${first_car['price']}/день")

        with allure.step("Проверка рендера карточки автомобиля"):
            assert "title" in first_car, "Не удалось спарсить название!"
            assert "price" in first_car, "Не удалось спарсить цену!"

            try:
                parsed_price = float(first_car['price'])
                assert parsed_price >= 0, f"Цена не может быть отрицательной: {parsed_price}"
            except ValueError:
                pytest.fail(f"Фронтенд вывел некорректный формат цены: {first_car['price']}")