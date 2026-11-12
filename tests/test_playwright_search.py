"""
Поиск в интерфейсе: наблюдения OBS-01 (регистр города), OBS-04 (исход поиска не обозначен)
и OBS-08 (цена на карточке округлена).

Город — с малым числом машин (SearchDataGenerator.SMALL_CITY): ответ по крупному городу весит
десятки мегабайт (Q-API-02). Для пустой выдачи — город, который есть только во фронтенде (DISC-02):
машину в нём API не создаст, поэтому выдача по нему пуста всегда.
"""

from decimal import Decimal

import allure
import pytest
from playwright.sync_api import Page, expect

from data.data_generator import SearchDataGenerator
from data.observations import observation
from pages.pw_search_page import PwSearchPage
from utils.network_faults import SEARCH, NetworkFaults, api_response, require_intercepted, send_and_settle
from utils.preconditions import require
from utils.search_helpers import RESULTS_PAGE_SIZE

pytestmark = [pytest.mark.ui, pytest.mark.regression]

SEARCH_PATH = "/v1/cars/search"
# Город только из списка фронтенда: в API его нет, выдача по нему всегда пуста (DISC-02, Q-UI-12)
UI_ONLY_CITY = "Beersheba"


def _serials(response) -> set[str]:
    return {car.get("serialNumber") for car in response.json().get("cars", [])}


@allure.epic("Playwright Testing")
@allure.feature("Search")
@allure.story("City case")
@allure.title("Город в другом регистре находит те же машины")
@observation("SEARCH_CITY_CASE_SENSITIVE")
@allure.tag("OBS-01")
@pytest.mark.parametrize("typed_case", ["lower", "upper"])
def test_pw_search_city_case_insensitive(page: Page, typed_case):
    """Город, введённый вручную (REQ-UI-SEARCH-03), в другом регистре: машин должно быть столько же (Q-UI-23)."""
    city = SearchDataGenerator.SMALL_CITY
    typed = city.lower() if typed_case == "lower" else city.upper()
    search_page = PwSearchPage(page)

    with allure.step(f"Поиск «{city}» с выбором из подсказки"):
        search_page.open()
        with page.expect_response(api_response("POST", SEARCH_PATH)) as reference:
            search_page.search_today(city)
        require(reference.value.status == 200, f"Предусловие: поиск {city} ответил {reference.value.status}")
        expected = _serials(reference.value)
        require(bool(expected), f"Предусловие: в {city} нет машин — сравнивать нечего")

    with allure.step(f"Поиск «{typed}», введённого вручную"):
        search_page.open()
        with page.expect_response(api_response("POST", SEARCH_PATH)) as typed_search:
            search_page.search_today_typed(typed)
        sent_city = (typed_search.value.request.post_data_json or {}).get("city")
        require(sent_city == typed, f"Предусловие: фронт отправил city={sent_city!r}, а не введённое {typed!r}")
        require(typed_search.value.status == 200, f"Предусловие: поиск {typed} ответил {typed_search.value.status}")

    with allure.step(f"Проверка: «{typed}» находит те же машины, что «{city}»"):
        found = _serials(typed_search.value)
        assert found == expected, f"«{typed}» нашёл {len(found)} машин, «{city}» — {len(expected)}"


@allure.epic("Playwright Testing")
@allure.feature("Search")
@allure.story("Search outcome")
@allure.title("Пустая выдача и сбой поиска обозначены сообщением")
@observation("SEARCH_OUTCOME_NOT_SHOWN")
@allure.tag("OBS-04")
@pytest.mark.parametrize("search_outcome", ["empty_result", "server_error_500", "network_error"])
def test_pw_search_outcome_announced(page: Page, request, search_outcome):
    """
    После поиска без карточек пользователь должен понять, что произошло: «ничего не найдено» или ошибка
    (OBS-04; Q-UI-12, Q-UI-24). Сообщение ищется как блок role=status или role=alert — так фронт
    показывает остальные сообщения (форма машины, вход); текст сообщения не задан, поэтому не сверяется.

    Сбой поиска подменяется (ответ 500 или обрыв); пустая выдача — настоящий ответ по городу,
    которого нет в API. Защита backend_write_guard — только в случаях с подменой: поиск — POST,
    и настоящий запрос пустой выдачи она бы оборвала.
    """
    search_page = PwSearchPage(page)
    search_page.open()

    if search_outcome == "empty_result":
        city = UI_ONLY_CITY
        with allure.step(f"Поиск {city}: настоящий ответ"):
            with page.expect_response(api_response("POST", SEARCH_PATH)) as response_info:
                search_page.search_today(city)
            response = response_info.value
            require(response.status == 200, f"Предусловие: поиск {city} ответил {response.status}")
            require(not response.json().get("cars"), f"Предусловие: выдача по {city} не пуста")
    else:
        city = SearchDataGenerator.SMALL_CITY
        # Защита — до подмены: маршрут, зарегистрированный раньше, проверяется позже (utils/network_faults.py)
        request.getfixturevalue("backend_write_guard")
        faults = NetworkFaults(page)
        if search_outcome == "network_error":
            sent = faults.abort(SEARCH, "POST")
        else:
            sent = faults.respond(SEARCH, "POST", 500)
        with allure.step(f"Поиск {city}: запрос перехвачен, сбой — {search_outcome}"):
            send_and_settle(page, "POST", SEARCH_PATH, lambda: search_page.search_today(city))
            require_intercepted(sent, f"POST {SEARCH_PATH}")

    # Поиск завершён: кнопка снова «Yalla!», а не «Loading...» (FE: Search)
    search_page.submit_btn.filter(has_text="Yalla!").wait_for()
    require(search_page.cards.count() == 0, "Предусловие: на экране есть карточки — выдача не пуста")

    with allure.step("Проверка: на экране есть сообщение об исходе поиска"):
        expect(search_page.messages.first, f"Поиск ({search_outcome}) закончился без сообщения").to_be_visible()


@allure.epic("Playwright Testing")
@allure.feature("Search")
@allure.story("Card price")
@allure.title("Цена на карточке совпадает с сохранённой")
@observation("CARD_PRICE_ROUNDED")
@allure.tag("OBS-08")
def test_pw_card_price_matches_saved(page: Page, shared_create_car):
    """
    Сумма на экране не должна отличаться от сохранённой (OBS-08). Фронт показывает цену с одним знаком
    после запятой (REQ-UI-SEARCH-05, проверяется в test_search_form_dynamic), и 1234.56 становится «1234.6» (Q-UI-12).
    """
    city = SearchDataGenerator.SMALL_CITY
    car = shared_create_car(city=city, price="1234.56")
    search_page = PwSearchPage(page)

    with allure.step(f"Поиск {city} в UI, вся выдача на одной странице"):
        search_page.open()
        with page.expect_response(api_response("POST", SEARCH_PATH)) as response_info:
            search_page.search_today(city)
        cars = {item.get("serialNumber"): item for item in response_info.value.json().get("cars", [])}
        require(car.reg_number in cars, f"Предусловие: машины {car.reg_number} нет в ответе поиска {city}")
        require(len(cars) <= RESULTS_PAGE_SIZE, f"Предусловие: в {city} {len(cars)} машин — больше одной страницы")
        saved = Decimal(str(cars[car.reg_number].get("pricePerDay")))
        require(saved == Decimal(car.price), f"Предусловие: сохранена цена {saved}, отправляли {car.price}")
        search_page.choose_page_size(RESULTS_PAGE_SIZE)
        price_cell = search_page.card_price(car.reg_number)
        price_cell.wait_for()
        shown = price_cell.inner_text().strip()

    with allure.step(f"Проверка: на карточке {saved}"):
        assert Decimal(shown) == saved, f"На карточке «{shown}», сохранено {saved}"
