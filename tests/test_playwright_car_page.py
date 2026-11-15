"""
Страница машины и запросы фронта мимо контракта: REQ-UI-CARPAGE-01 и расхождение DISC-05.

Машин тесты не создают: открывается существующая машина из выдачи города с малым числом машин
(SearchDataGenerator.SMALL_CITY). Запросы чтения (GET) уходят на настоящий бэкенд — данных они
не меняют. Ответы не подменяются: эндпоинты вне Swagger в тестах не подменяются ничем (CLAUDE.md),
поэтому PUT /v1/user/profile, который уходит только после загруженного профиля, не проверяется (DISC-10).
"""

from dataclasses import dataclass
from urllib.parse import urlsplit

import allure
import pytest
from playwright.sync_api import Page, Request, expect

from config import settings
from data.data_generator import SearchDataGenerator
from data.known_bugs import known_bug
from pages.pw_base_page import PwBasePage
from pages.pw_search_page import PwSearchPage
from utils.network_faults import api_response
from utils.preconditions import require
from utils.swagger_contract import documented_operations, is_documented

pytestmark = [pytest.mark.ui, pytest.mark.regression]

# Модель короче трёх символов могла бы найтись на странице случайно — такую машину не берём
MIN_MODEL_LENGTH = 3


@dataclass
class OpenedCar:
    """Машина из выдачи, по карточке которой кликнул тест, и запрос, который фронт отправил после клика."""

    car: dict  # CarDto из ответа поиска
    request: Request


def _is_api_request(request: Request) -> bool:
    return request.url.startswith(settings.api_url)


def _undocumented_message(request: Request) -> str:
    operations = ", ".join(f"{method} {path}" for method, path in documented_operations())
    return (
        f"Фронт отправил {request.method} {urlsplit(request.url).path} — такой операции нет в Swagger. "
        f"Описаны: {operations}"
    )


@pytest.fixture
def opened_car(page: Page) -> OpenedCar:
    """Гость ищет машины в малом городе и кликает по карточке существующей машины."""
    city = SearchDataGenerator.SMALL_CITY
    search_page = PwSearchPage(page)
    search_page.open()

    with page.expect_response(api_response("POST", "/v1/cars/search")) as search:
        search_page.search_today(city)
    require(search.value.status == 200, f"Предусловие: поиск по {city} ответил {search.value.status}")
    found = {car.get("serialNumber"): car for car in search.value.json().get("cars", [])}

    search_page.cards.first.wait_for(state="visible")
    card, car = None, None
    for candidate in search_page.cards.all():
        listed = found.get((candidate.get_attribute("href") or "").rsplit("/", 1)[-1])
        if listed and len(str(listed.get("model") or "").strip()) >= MIN_MODEL_LENGTH:
            card, car = candidate, listed
            break
    require(card is not None, f"Предусловие: в выдаче {city} нет карточки машины с моделью, пригодной для проверки")

    with allure.step(f"Клик по карточке машины {car['serialNumber']}"):
        # Любой запрос к API после клика: какой именно — проверяет тест DISC-05. Запроса нет — TimeoutError
        with page.expect_request(_is_api_request) as request_info:
            card.click()
        # Адрес страницы — первая половина требования; под known_bug остаётся проверка данных
        page.wait_for_url(f"**/cars/{car['serialNumber']}")
        # Ждём исход запроса: ответ или сетевую ошибку (тогда response() вернёт None)
        request_info.value.response()
    return OpenedCar(car=car, request=request_info.value)


@allure.epic("Playwright Testing")
@allure.feature("Car Page")
@allure.story("Open a car from search results")
@allure.title("Клик по карточке открывает страницу с данными машины")
@known_bug("CAR_PAGE_NOT_LOADED")
@allure.tag("REQ-UI-CARPAGE-01")
def test_pw_car_card_opens_car_page(page: Page, opened_car):
    """Страница /cars/{serial} открывается, но вместо машины — «Не удалось загрузить машину» (Q-UI-01, Q-UI-19)."""
    model = str(opened_car.car["model"]).strip()

    with allure.step(f"Проверка: на странице есть модель машины «{model}»"):
        expect(page.locator("main"), "На странице машины нет её данных").to_contain_text(model)


@allure.epic("Playwright Testing")
@allure.feature("Car Page")
@allure.story("Frontend requests vs Swagger")
@allure.title("Запрос страницы машины описан в Swagger")
@known_bug("FRONTEND_CALLS_UNDOCUMENTED_ENDPOINTS")
@allure.tag("DISC-05")
def test_pw_car_page_request_is_documented(opened_car):
    """Страница машины запрашивает GET /v1/cars/{id}; в Swagger у этого пути только DELETE (Q-UI-01, Q-UI-19)."""
    request = opened_car.request

    with allure.step(f"Проверка: {request.method} {urlsplit(request.url).path} есть в Swagger"):
        assert is_documented(request.method, urlsplit(request.url).path), _undocumented_message(request)


@allure.epic("Playwright Testing")
@allure.feature("Profile Page")
@allure.story("Frontend requests vs Swagger")
@allure.title("Запрос страницы профиля описан в Swagger")
@known_bug("FRONTEND_CALLS_UNDOCUMENTED_ENDPOINTS")
@allure.tag("DISC-05")
def test_pw_profile_page_request_is_documented(page: Page, shared_user):
    """Страница профиля запрашивает GET /v1/user/profile, которого нет в Swagger (Q-UI-18)."""
    base_page = PwBasePage(page)
    base_page.restore_session(shared_user.api.token)

    # Запроса к API нет — TimeoutError: проверять было бы нечего
    with (
        allure.step("Открытие /profile залогиненным пользователем"),
        page.expect_request(_is_api_request) as request_info,
    ):
        base_page.open_url("/profile")
    request = request_info.value

    with allure.step(f"Проверка: {request.method} {urlsplit(request.url).path} есть в Swagger"):
        assert is_documented(request.method, urlsplit(request.url).path), _undocumented_message(request)
