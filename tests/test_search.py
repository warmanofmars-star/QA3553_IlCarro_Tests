import logging

import allure
import pytest

from api.car_api import IlCarroAPI
from data.data_generator import SearchDataGenerator
from pages.results_page import ResultsPage
from pages.search_page import SearchPage
from utils.preconditions import require
from utils.price_format import UI_PRICE_PATTERN, ui_price
from utils.search_helpers import RESULTS_PAGE_SIZE, require_city_fits_one_page

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.ui

# Наибольшее число вариантов подсказки города (FE: CityAutocomplete, REQ-UI-SEARCH-03)
CITY_SUGGESTIONS_LIMIT = 8
# Размер страницы выдачи по умолчанию (FE: Search, size=10 в URL)
RESULTS_FIRST_PAGE = 10


# Гибридный: машина создаётся через API, поиск идёт в UI. Отдельный test_hybrid_car_search проверял
# то же самое без проверки кнопки и слит с этим тестом
@pytest.mark.smoke
@pytest.mark.hybrid
@allure.epic("UI Testing")
@allure.feature("Search Page")
@allure.story("Search Cars Dynamic Flow")
@allure.severity(allure.severity_level.CRITICAL)
# REQ-UI-SEARCH-04 здесь не тег: size в URL — способ показать всю выдачу, а не проверка пагинации
@allure.tag("REQ-UI-SEARCH-01", "REQ-UI-SEARCH-05")
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
@allure.tag("REQ-UI-SEARCH-01")
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
@allure.tag("REQ-UI-SEARCH-06")
def test_search_dates_readonly_protection(driver):
    search_page = SearchPage(driver)
    search_page.open()

    with allure.step("Проверка защиты от дурака: поле дат не должно принимать ручной ввод текста"):
        # Если поле readonly, пользователь не сможет вбить туда "Привет" вместо "12/12/2026"
        assert search_page.is_dates_input_readonly() is True, (
            "Критическая уязвимость UI: Поле дат доступно для ручного ввода текста!"
        )


def _city_suggestions_expected(text: str) -> list[str]:
    """Варианты подсказки по правилу фронтенда (FE: CityAutocomplete, REQ-UI-SEARCH-03).

    Города из списка фронтенда, в названии которых есть введённый текст без учёта регистра,
    в порядке списка; не больше 8. Пустое поле — первые 8 городов списка.
    """
    matches = [city for city in SearchDataGenerator.UI_CITIES if text.lower() in city.lower()]
    return matches[:CITY_SUGGESTIONS_LIMIT]


@pytest.mark.regression
@allure.epic("UI Testing")
@allure.feature("Search Page")
@allure.story("City Suggestions")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("REQ-UI-SEARCH-03")
@pytest.mark.parametrize(
    "typed, more_than_limit, scenario",
    [
        ("", True, "Пустое поле: первые 8 городов списка"),
        ("a", True, "Совпадений больше 8: показано 8"),
        ("Kiryat", False, "Совпадений меньше 8: показаны все"),
    ],
)
def test_search_city_suggestions(driver, typed, more_than_limit, scenario):
    search_page = SearchPage(driver)
    expected = _city_suggestions_expected(typed)
    allure.dynamic.parameter("Ожидаемые варианты", ", ".join(expected))
    # Сценарий задан числом совпадений в списке фронтенда: изменится список — сценарий потеряет смысл
    matches = [city for city in SearchDataGenerator.UI_CITIES if typed.lower() in city.lower()]
    require(
        (len(matches) > CITY_SUGGESTIONS_LIMIT) == more_than_limit,
        f"Предусловие: для {typed!r} совпадений {len(matches)} — сценарий «{scenario}» не воспроизводится",
    )

    with allure.step(f"Сценарий: {scenario}"):
        search_page.open()
        search_page.click(search_page.CITY_INPUT)
        if typed:
            search_page.type_city(typed)
        actual = search_page.wait_city_suggestions(expected)

    with allure.step(f"Проверка: варианты подсказки — {len(expected)} городов списка фронтенда"):
        assert actual == expected, f"Для {typed!r} ожидали варианты {expected}, на экране {actual}"


@pytest.mark.regression
@allure.epic("UI Testing")
@allure.feature("Search Page")
@allure.story("City Suggestions")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("REQ-UI-SEARCH-03")
def test_search_city_typed_manually(driver):
    """Город, введённый вручную без выбора из подсказки, принимается поиском (Q-UI-12)."""
    search_page = SearchPage(driver)
    results_page = ResultsPage(driver)
    city = SearchDataGenerator.SMALL_CITY
    start_date, end_date = SearchDataGenerator.get_safe_future_dates()
    response = IlCarroAPI().search_cars(city, f"{start_date:%Y-%m-%d}", f"{end_date:%Y-%m-%d}")
    require(response.status_code == 200, f"Поиск через API недоступен: {response.status_code}")
    require(response.json().get("cars"), f"Предусловие: в {city} нет машин — по выдаче не понять, прошёл ли поиск")

    with allure.step(f"Ввод «{city}» вручную, подсказка закрыта без выбора"):
        search_page.open()
        search_page.type_city(city)
        search_page.leave_city_input()
        search_page.select_date_range(start_date, end_date)
        require(search_page.is_calendar_invisible(), "Предусловие: календарь не закрылся после выбора дат")

    with allure.step("Проверка: введённый город остался в поле, поиск выполняется"):
        value = search_page.find(search_page.CITY_INPUT).get_attribute("value")
        assert value == city, f"Введённый вручную город заменён: в поле {value!r}"
        assert search_page.is_submit_button_disabled() is False, "С городом, введённым вручную, «Yalla!» недоступна"
        search_page.click_submit_button()
        assert results_page.wait_for_cards_count(min(len(response.json()["cars"]), RESULTS_FIRST_PAGE)) > 0, (
            f"Поиск по введённому вручную «{city}» не показал ни одной карточки"
        )


@pytest.mark.regression
@allure.epic("UI Testing")
@allure.feature("Search Page")
@allure.story("Pagination")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("REQ-UI-SEARCH-04")
def test_search_client_pagination(driver):
    """Пагинация на клиенте: page и size в URL, 10, 20 или 50 карточек на странице (FE: Search, Q-UI-22)."""
    search_page = SearchPage(driver)
    results_page = ResultsPage(driver)
    city = SearchDataGenerator.SMALL_CITY
    start_date, end_date = SearchDataGenerator.get_safe_future_dates()

    with allure.step(f"Поиск {city} в UI"):
        search_page.open()
        search_page.fill_city(city)
        search_page.select_date_range(start_date, end_date)
        require(search_page.is_calendar_invisible(), "Предусловие: календарь не закрылся после выбора дат")
        search_page.click_submit_button()
        results_page.find(results_page.RANGE_LABEL)
        # Сколько машин получил фронт: число из его же подписи. Читать его из отдельного запроса к API
        # нельзя: соседние тесты создают машины в том же городе, и числа разошлись бы
        total = results_page.get_results_total()
        require(
            RESULTS_FIRST_PAGE < total <= RESULTS_PAGE_SIZE,
            f"Предусловие: в {city} {total} машин; нужно больше {RESULTS_FIRST_PAGE} (вторая страница) "
            f"и не больше {RESULTS_PAGE_SIZE}",
        )

    with allure.step("Проверка: первая страница — page=0, size=10 в URL, 10 карточек"):
        query = results_page.wait_for_url_query({"page": "0", "size": "10"})
        assert (query.get("page"), query.get("size")) == ("0", "10"), f"Параметры пагинации в URL: {query}"
        assert results_page.wait_for_cards_count(RESULTS_FIRST_PAGE) == RESULTS_FIRST_PAGE, (
            f"На первой странице не {RESULTS_FIRST_PAGE} карточек"
        )

    with allure.step("Проверка: варианты размера страницы — 10, 20, 50"):
        options = results_page.get_page_size_options()
        assert options == ["10", "20", "50"], f"Варианты «Rows per page»: {options}"

    with allure.step("Проверка: Next — page=1 в URL, на странице остаток выдачи"):
        results_page.click_next_page()
        query = results_page.wait_for_url_query({"page": "1"})
        assert query.get("page") == "1", f"После Next в URL page={query.get('page')!r}"
        rest = min(RESULTS_FIRST_PAGE, total - RESULTS_FIRST_PAGE)
        cards = results_page.wait_for_cards_count(rest)
        assert cards == rest, f"На второй странице {cards} карточек, ожидали {rest} из {total}"

    for size in (20, 50):
        with allure.step(f"Проверка: Rows per page = {size} — size={size}, page=0 в URL, {min(size, total)} карточек"):
            results_page.choose_page_size(size)
            query = results_page.wait_for_url_query({"page": "0", "size": str(size)})
            assert (query.get("page"), query.get("size")) == ("0", str(size)), f"Параметры пагинации в URL: {query}"
            cards = results_page.wait_for_cards_count(min(size, total))
            assert cards == min(size, total), f"При size={size} на странице {cards} карточек из {total}"
