"""
Наблюдения об интерфейсе: OBS-06 (форма машины гостю), OBS-07 (причина ошибки отправки машины),
OBS-09 (URL после регистрации), OBS-11 (русские тексты в английском интерфейсе).

Пишущие запросы (POST /v1/cars, POST регистрации) перехвачены и получают подменённый ответ: машин
и пользователей тесты не создают. Тела ответов — в формате настоящих (Q-UI-03, Q-UI-04, Q-API-06),
значения, которых у приложения нет (токен регистрации), придуманы тестом.
"""

import re
from urllib.parse import urlsplit

import allure
import pytest
from playwright.sync_api import Page, expect

from api.car_api import IlCarroAPI
from data.data_generator import CarGenerator, SearchDataGenerator, UserGenerator
from data.observations import observation
from pages.pw_add_car_page import PwAddCarPage
from pages.pw_base_page import PwBasePage
from pages.pw_login_page import PwLoginPage
from pages.pw_registration_page import PwRegistrationPage
from utils.network_faults import CARS, REGISTRATION, NetworkFaults, require_intercepted, send_and_settle
from utils.preconditions import require

pytestmark = [pytest.mark.ui, pytest.mark.regression]

CYRILLIC = re.compile(r"[А-Яа-яЁё]+(?:\s+[А-Яа-яЁё.]+)*")
REGISTRATION_PATH = "/v1/user/registration/usernamepassword"


@allure.epic("Playwright Testing")
@allure.feature("Cars Management")
@allure.story("Guest access")
@allure.title("Гостю форма добавления машины не открывается: переход на вход")
@observation("GUEST_OPENS_CAR_FORM")
@allure.tag("OBS-06")
def test_pw_guest_redirected_from_car_form(page: Page):
    """
    Отправить форму гость всё равно не сможет («Failed to submit car», Q-UI-13), поэтому его должно
    перевести на вход — как с /profile, где фронт это уже делает (OBS-06).
    """
    add_car_page = PwAddCarPage(page)
    add_car_page.open()
    require(add_car_page.local_storage_item("token") is None, "Предусловие: в браузере гостя есть token")

    with allure.step("Проверка: гостя перевели на страницу входа"):
        expect(page, "Гость остался на форме добавления машины").to_have_url(re.compile(r"/login$"))


@allure.epic("Playwright Testing")
@allure.feature("Cars Management")
@allure.story("Submit error text")
@allure.title("Текст ошибки отправки машины называет причину")
@observation("CAR_SUBMIT_ERROR_WITHOUT_CAUSE")
@allure.tag("OBS-07")
@pytest.mark.parametrize(
    "server_message, causes",
    [
        pytest.param("City Beersheba is not supported", ["City Beersheba is not supported"], id="unsupported_city"),
        pytest.param({"city": "must not be blank"}, ["city", "must not be blank"], id="blank_city"),
    ],
)
def test_pw_car_submit_error_names_cause(
    page: Page, shared_user, shared_car_cleanup, backend_write_guard, server_message, causes
):
    """
    Сервер объясняет отказ (Q-UI-03, Q-UI-04), а пользователь видит один текст «Failed to submit car»
    (OBS-07). Ответ подменён: тело — в формате настоящего ответа 400.
    """
    add_car_page = PwAddCarPage(page)
    add_car_page.restore_session(shared_user.api.token)
    add_car_page.open()
    PwLoginPage(page).logout_btn.wait_for(state="visible")

    car = CarGenerator.get_random_car()
    # Страховка: если перехват не сработает и машина создастся на бэкенде, очистка её удалит
    shared_car_cleanup.register(car.reg_number)
    add_car_page.fill_form(car)
    sent = NetworkFaults(page).respond(
        CARS, "POST", 400, {"status": 400, "error": "Bad Request", "message": server_message, "path": "/v1/cars"}
    )

    with allure.step("Отправка формы: POST /v1/cars перехвачен, ответ подменён на 400"):
        send_and_settle(page, "POST", "/v1/cars", add_car_page.submit)
        require_intercepted(sent, "POST /v1/cars")
        # wait_for, а не expect: появление ошибки — предусловие, проверка — её текст
        add_car_page.submit_error_message.wait_for(state="visible")
        shown = add_car_page.submit_error_message.inner_text()

    with allure.step(f"Проверка: в тексте ошибки есть причина {causes}"):
        missing = [cause for cause in causes if cause not in shown]
        assert not missing, f"Ошибка отправки «{shown}» не называет причину: нет {missing}"


@allure.epic("Playwright Testing")
@allure.feature("Registration")
@allure.story("After registration")
@allure.title("После регистрации URL меняется с /register")
@observation("REGISTER_URL_UNCHANGED")
@allure.tag("OBS-09")
def test_pw_registration_leaves_register_url(page: Page, backend_write_guard):
    """
    Пользователь зарегистрирован и залогинен, а адрес остаётся адресом формы регистрации (OBS-09;
    Q-UI-09, Q-UI-25). Запрос регистрации перехвачен: ответ 200 в формате настоящего ({"accessToken": …},
    Q-API-06), значение токена придумано тестом. Пользователь на бэкенде не создаётся.
    """
    registration_page = PwRegistrationPage(page)
    registration_page.open()
    sent = NetworkFaults(page).respond(REGISTRATION, "POST", 200, {"accessToken": "substituted-by-test"})

    with allure.step("Регистрация: запрос перехвачен, ответ подменён на 200"):
        registration_page.fill_form(UserGenerator.get_random_user())
        send_and_settle(page, "POST", REGISTRATION_PATH, registration_page.submit)
        require_intercepted(sent, f"POST {REGISTRATION_PATH}")

    with allure.step("Окно «Registered» закрыто кнопкой OK"):
        registration_page.dialog_title.filter(has_text="Registered").wait_for()
        registration_page.dialog_ok_btn.click()
        registration_page.dialog.wait_for(state="hidden")

    with allure.step("Проверка: открыта не форма регистрации"):
        expect(page, "После регистрации пользователь остался на /register").not_to_have_url(re.compile(r"/register$"))


def _first_listed_serial() -> str:
    """serialNumber существующей машины малого города: страница машины открывается без создания машины."""
    city = SearchDataGenerator.SMALL_CITY
    start_date, end_date = SearchDataGenerator.get_safe_future_dates()
    response = IlCarroAPI().search_cars(city, f"{start_date:%Y-%m-%d}", f"{end_date:%Y-%m-%d}")
    require(response.status_code == 200, f"Предусловие: поиск {city} ответил {response.status_code}")
    cars = response.json().get("cars") or []
    require(bool(cars), f"Предусловие: в {city} нет машин")
    return cars[0]["serialNumber"]


@allure.epic("Playwright Testing")
@allure.feature("Interface language")
@allure.story("Car and profile pages")
@allure.title("Тексты страниц машины и профиля — на английском")
@observation("RUSSIAN_TEXTS_IN_ENGLISH_UI")
@allure.tag("OBS-11")
@pytest.mark.parametrize("ui_page", ["car_page", "profile_page"])
def test_pw_page_texts_in_english(page: Page, shared_user, ui_page):
    """
    Весь интерфейс на английском, а страницы машины и профиля пишут по-русски (OBS-11;
    Q-UI-01, Q-UI-18). Страница проверяется после того, как её запрос к API завершился.
    """
    base_page = PwBasePage(page)
    if ui_page == "car_page":
        serial = _first_listed_serial()
        path, api_path = f"/cars/{serial}", f"/v1/cars/{serial}"
    else:
        base_page.restore_session(shared_user.api.token)
        path, api_path = "/profile", "/v1/user/profile"

    with allure.step(f"Открытие {path}: ждём исход запроса GET {api_path}"):
        with page.expect_request(
            lambda request: request.method == "GET" and urlsplit(request.url).path == api_path
        ) as request_info:
            base_page.open_url(path)
        request_info.value.response()  # ответ или None, если запрос оборван
        # Страница показала итог загрузки: «Загрузка...» сменилась данными или ошибкой.
        # wait_for_function, а не expect: ожидание — предусловие, под xfail остаётся только проверка языка
        page.wait_for_function(
            "() => { const t = (document.querySelector('main')?.innerText || '').trim();"
            " return t !== '' && t !== 'Загрузка...' && t !== 'Loading…'; }"
        )
        text = page.locator("main").inner_text()

    with allure.step("Проверка: на странице нет русского текста"):
        russian = CYRILLIC.findall(text)
        assert not russian, f"На странице {path} русский текст: {russian}"
