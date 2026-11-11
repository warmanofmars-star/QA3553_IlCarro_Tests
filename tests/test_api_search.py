"""
API поиска: REQ-SEARCH-01, REQ-SEARCH-02 и пагинация DISC-08.

Поиск — только по городу с малым числом машин (SearchDataGenerator.SMALL_CITY): ответ по крупному
городу весит десятки мегабайт (Tel Aviv — около 18 МБ, Q-API-02), а size API игнорирует (DISC-08),
так что ограничить выдачу нечем.
"""

import allure
import pytest

from api.car_api import IlCarroAPI
from data.data_generator import SearchDataGenerator
from data.known_bugs import known_bug
from utils.preconditions import require

pytestmark = pytest.mark.api

CITY = SearchDataGenerator.SMALL_CITY


def _dates() -> tuple[str, str]:
    start_date, end_date = SearchDataGenerator.get_safe_future_dates()
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def _found_cars(response) -> list[dict]:
    require(response.status_code == 200, f"Поиск недоступен: {response.status_code} {response.text}")
    return response.json().get("cars", [])


@pytest.mark.smoke
@allure.epic("API Testing")
@allure.feature("Search")
@allure.story("Search without authorization")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-SEARCH-01")
def test_api_search_without_token():
    api = IlCarroAPI()  # клиент без заголовка Authorization
    require("Authorization" not in api.session.headers, "У клиента без входа оказался заголовок Authorization")

    response = api.search_cars(CITY, *_dates())

    with allure.step("Проверка: поиск без токена — 200"):
        assert response.status_code == 200, (
            f"Поиск без токена: ожидали 200, получили {response.status_code} {response.text}"
        )


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Search")
@allure.story("Search by city")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-SEARCH-02")
def test_api_search_only_requested_city(shared_create_car):
    # Своя машина в городе: без неё пустая выдача прошла бы проверку «все машины из города» впустую
    car = shared_create_car(city=CITY)

    cars = _found_cars(IlCarroAPI().search_cars(CITY, *_dates()))
    require(car.reg_number in {found.get("serialNumber") for found in cars}, "Созданная машина не найдена поиском")

    with allure.step(f"Проверка: у всех {len(cars)} машин выдачи city = {CITY}"):
        foreign = {found.get("serialNumber"): found.get("city") for found in cars if found.get("city") != CITY}
        assert not foreign, f"Поиск по {CITY} вернул машины других городов: {foreign}"


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Search")
@allure.story("Pagination")
@allure.severity(allure.severity_level.NORMAL)
@known_bug("SEARCH_PAGINATION_IGNORED")
@allure.tag("DISC-08")
def test_api_search_page_size(shared_create_car):
    """Фронт передаёт в поиск page и size; с size=1 в ответе должна быть одна машина."""
    # Две свои машины: в выдаче города гарантированно больше одной машины
    own = {shared_create_car(city=CITY).reg_number, shared_create_car(city=CITY).reg_number}
    start_date, end_date = _dates()
    api = IlCarroAPI()

    all_cars = _found_cars(api.search_cars(CITY, start_date, end_date))
    require(own <= {found.get("serialNumber") for found in all_cars}, "Созданные машины не найдены поиском")

    page_cars = _found_cars(api.search_cars(CITY, start_date, end_date, params={"page": 0, "size": 1}))

    with allure.step("Проверка: при size=1 в ответе одна машина"):
        assert len(page_cars) == 1, f"Поиск с page=0&size=1: ожидали 1 машину, получили {len(page_cars)}"
