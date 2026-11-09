import logging

import allure
import pytest

from data.data_generator import SearchDataGenerator
from pages.results_page import ResultsPage
from pages.search_page import SearchPage
from utils.price_format import UI_PRICE_PATTERN, ui_price
from utils.search_helpers import RESULTS_PAGE_SIZE, require_city_fits_one_page

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.ui


@pytest.mark.smoke
@allure.epic("UI Testing")
@allure.feature("Search Page")
@allure.story("Search Cars Dynamic Flow")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-UI-SEARCH-01", "REQ-UI-SEARCH-04", "REQ-UI-SEARCH-05")
def test_search_form_dynamic(driver, auth_api, create_car):
    search_page = SearchPage(driver)
    results_page = ResultsPage(driver)

    city = SearchDataGenerator.SMALL_CITY
    start_date, end_date = SearchDataGenerator.get_safe_future_dates()
    allure.dynamic.parameter("Город", city)
    allure.dynamic.parameter("Даты", f"{start_date:%Y-%m-%d} — {end_date:%Y-%m-%d}")

    # Своя машина: проверяем, что находится именно она, а не «какая-нибудь» чужая
    car = create_car(city=city)
    require_city_fits_one_page(auth_api, city, start_date, end_date)

    search_page.open()
    search_page.fill_city(city)
    search_page.select_date_range(start_date, end_date)
    search_page.click(search_page.CITY_INPUT)

    assert search_page.is_submit_button_disabled() is False, "Кнопка Yalla! не разблокировалась!"

    search_page.click_submit_button()

    # 1. Ждем факта отправки поискового запроса (смена URL)
    results_page.wait_for_search_request_to_complete()
    # 2. Вся выдача города на одной странице (пагинация клиентская, size в URL)
    results_page.show_page_size(RESULTS_PAGE_SIZE)

    with allure.step(f"Проверка: в выдаче есть наша машина {car.reg_number}"):
        card = results_page.get_car_details(car.reg_number)
        assert card is not None, f"Созданная машина {car.reg_number} не найдена в выдаче по городу {city}"
        logger.info(f"Найдена машина: {card['serial_number']}, {card['title']} за ${card['price']}/день")

    with allure.step("Проверка рендера карточки: заголовок и цена (REQ-UI-SEARCH-05)"):
        assert card["title"].strip(), "Заголовок карточки пустой"
        assert UI_PRICE_PATTERN.match(card["price"]), (
            f"Цена на карточке не в формате с одним знаком после запятой: {card['price']!r}"
        )
        assert card["price"] == ui_price(car.price), (
            f"Цена на карточке {card['price']!r}, ожидали {ui_price(car.price)!r} (pricePerDay {car.price})"
        )


@pytest.mark.regression
@allure.epic("UI Testing")
@allure.feature("Search Page")
@allure.story("Negative Search - Empty City Validation")
@allure.severity(allure.severity_level.NORMAL)
def test_search_empty_city_validation(driver):
    search_page = SearchPage(driver)
    search_page.open()

    with allure.step("Кликаем в поле City и снимаем фокус для вызова валидации"):
        search_page.click(search_page.CITY_INPUT)
        search_page.remove_focus()  # Тот самый универсальный клик по body из BasePage!

    # Проверяем, что фронтенд отреагировал на пустое поле
    assert search_page.is_submit_button_disabled() is True, "Кнопка Y'alla! должна быть заблокирована при пустом городе"


@pytest.mark.regression
@pytest.mark.security
@allure.epic("UI Testing")
@allure.feature("Search Page")
@allure.story("Negative Search - Dates Manual Input Blocked")
@allure.severity(allure.severity_level.NORMAL)
def test_search_dates_readonly_protection(driver):
    search_page = SearchPage(driver)
    search_page.open()

    with allure.step("Проверка защиты от дурака: поле дат не должно принимать ручной ввод текста"):
        # Если поле readonly, пользователь не сможет вбить туда "Привет" вместо "12/12/2026"
        assert search_page.is_dates_input_readonly() is True, (
            "Критическая уязвимость UI: Поле дат доступно для ручного ввода текста!"
        )
