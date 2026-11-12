"""
Страница машины и запросы фронта мимо контракта: REQ-UI-CARPAGE-01 и расхождение DISC-05.

Машин тесты не создают: открывается существующая машина из выдачи города с малым числом машин
(SearchDataGenerator.SMALL_CITY). Запросы чтения (GET) уходят на настоящий бэкенд — данных они
не меняют; PUT /v1/user/profile перехватывается и до бэкенда не доходит.
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
from utils.network_faults import PROFILE, NetworkFaults, api_response, require_intercepted, send_and_settle
from utils.preconditions import require
from utils.swagger_contract import documented_operations, is_documented

pytestmark = [pytest.mark.ui, pytest.mark.regression]

PROFILE_PATH = "/v1/user/profile"
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


@allure.epic("Playwright Testing")
@allure.feature("Profile Page")
@allure.story("Frontend requests vs Swagger")
@allure.title("Запрос сохранения профиля описан в Swagger")
@known_bug("FRONTEND_CALLS_UNDOCUMENTED_ENDPOINTS")
@allure.tag("DISC-05")
def test_pw_profile_save_request_is_documented(page: Page, shared_user, backend_write_guard):
    """
    «Сохранить» на странице профиля отправляет PUT /v1/user/profile, которого нет в Swagger (Q-UI-18).

    До кнопки не дойти без загруженного профиля, а GET /v1/user/profile на бэкенде не существует,
    поэтому его ответ подменён. Тело подмены придумано тестом — у приложения такого ответа нет;
    оно нужно только, чтобы фронт отправил PUT. Сам PUT перехвачен и до бэкенда не доходит.
    """
    invented_profile = {"firstName": "Test", "lastName": "User", "username": shared_user.user.email}
    faults = NetworkFaults(page)
    loaded = faults.respond(PROFILE, "GET", 200, invented_profile)
    saved = faults.respond(PROFILE, "PUT", 200, invented_profile)

    base_page = PwBasePage(page)
    base_page.restore_session(shared_user.api.token)

    with allure.step("Открытие /profile: ответ GET подменён"):
        send_and_settle(page, "GET", PROFILE_PATH, lambda: base_page.open_url("/profile"))
        require_intercepted(loaded, f"GET {PROFILE_PATH}")

    with allure.step("Клик «Сохранить»: PUT перехвачен"):
        save_btn = page.get_by_role("button", name="Сохранить")
        save_btn.wait_for(state="visible")
        send_and_settle(page, "PUT", PROFILE_PATH, save_btn.click)
        # Без пойманного PUT сверять со Swagger нечего
        require_intercepted(saved, f"PUT {PROFILE_PATH}")
    request = saved[0]

    with allure.step(f"Проверка: {request.method} {urlsplit(request.url).path} есть в Swagger"):
        assert is_documented(request.method, urlsplit(request.url).path), _undocumented_message(request)
