import allure
import pytest
from data.data_generator import SearchDataGenerator
from pages.search_page import SearchPage
from pages.results_page import ResultsPage
from utils.price_format import UI_PRICE_PATTERN, ui_price
from utils.search_helpers import RESULTS_PAGE_SIZE, require_city_fits_one_page

pytestmark = pytest.mark.ui

@pytest.mark.hybrid
@pytest.mark.smoke
@allure.epic("Hybrid Testing")
@allure.feature("Search functionality")
@allure.story("API Setup -> UI Search -> API Teardown")
@allure.severity(allure.severity_level.BLOCKER)
@allure.tag("REQ-UI-SEARCH-04", "REQ-UI-SEARCH-05")
def test_hybrid_car_search(driver, auth_api, create_car):
    target_city = SearchDataGenerator.SMALL_CITY
    start_date, end_date = SearchDataGenerator.get_safe_future_dates()

    with allure.step("API: Подготовка тестовых данных (создание машины)"):
        # Удаление машины после теста — забота фабрики create_car
        car = create_car(city=target_city)
        require_city_fits_one_page(auth_api, target_city, start_date, end_date)

    # --- ШАГ 2: UI (Поиск через браузер) ---
    search_page = SearchPage(driver)
    results_page = ResultsPage(driver)

    with allure.step(f"UI: Поиск машины в городе {target_city}"):
        search_page.open()
        search_page.fill_city(target_city)
        search_page.select_date_range(start_date, end_date)

        # Снимаем фокус с календаря, как в test_search_form_dynamic
        search_page.click(search_page.CITY_INPUT)
        search_page.click_submit_button()

    # --- ШАГ 3: UI (Проверка результатов) ---
    with allure.step(f"UI: В выдаче есть именно созданная машина {car.reg_number}"):
        results_page.wait_for_search_request_to_complete()
        results_page.show_page_size(RESULTS_PAGE_SIZE)

        card = results_page.get_car_details(car.reg_number)
        assert card is not None, \
            f"Машина {car.reg_number} не найдена в выдаче по городу {target_city}, хотя API успешно её создал!"

    with allure.step("UI: Карточка отрисована: заголовок не пустой, цена по правилу отображения"):
        assert card["title"].strip(), "Заголовок карточки пустой"
        assert UI_PRICE_PATTERN.match(card["price"]), \
            f"Цена на карточке не в формате с одним знаком после запятой: {card['price']!r}"
        assert card["price"] == ui_price(car.price), \
            f"Цена на карточке {card['price']!r}, ожидали {ui_price(car.price)!r} (pricePerDay {car.price})"
