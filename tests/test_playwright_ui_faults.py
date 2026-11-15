"""
Сбои бэкенда в формах и поиске (шаг 7d): REQ-UI-REG-05 (ответ 401, 500 и обрыв на регистрации),
REQ-UI-CAR-02 (ошибка отправки машины — «Failed to submit car»), сторона UI расхождения DISC-11
(409 при повторе email) и наблюдения OBS-12 (сбой поиска не обозначен), OBS-13 (после сбоя поиска
остаётся прошлая выдача), OBS-14 (вход без предела ожидания ответа), OBS-15 (ответ 400 без message
на регистрацию).

Сбой внедряется в запрос, который экран действительно отправляет (Q-UI-27): статус из Swagger или 5xx
с пустым телом (respond_empty), обрыв (abort), страница посредника (respond_proxy_page), задержка с обрывом
(hold). Все тесты запрашивают backend_write_guard: POST мимо подмен обрывается. Настоящий ответ — только
через allow_real и только для одного запроса, одобренного предикатом теста: повтор email общего
пользователя (DISC-11) и поиск по SearchDataGenerator.SMALL_CITY (OBS-13).

Пользователи — по правилу CLAUDE.md: общий shared_user (форма машины — вход токеном; повтор его email),
новых пользователей тесты не заводят. Email регистрации со сбоем фальшивый (example.com): запрос перехвачен.
"""

from datetime import date, timedelta

import allure
import pytest
from playwright.sync_api import Page, Request, expect

from data.data_generator import CarGenerator, SearchDataGenerator, UserGenerator
from data.known_bugs import known_bug
from data.observations import observation
from pages.pw_add_car_page import PwAddCarPage
from pages.pw_login_page import PwLoginPage
from pages.pw_registration_page import PwRegistrationPage
from pages.pw_search_page import PwSearchPage
from utils.network_faults import (
    CARS,
    LOGIN,
    REGISTER_400_EMPTY_PASSWORD,
    REGISTRATION,
    SEARCH,
    NetworkFaults,
    api_request,
    require_intercepted,
    send_and_settle,
)
from utils.preconditions import require

pytestmark = [pytest.mark.ui, pytest.mark.regression]

LOGIN_PATH = "/v1/user/login/usernamepassword"
REGISTRATION_PATH = "/v1/user/registration/usernamepassword"
SEARCH_PATH = "/v1/cars/search"
CARS_PATH = "/v1/cars"

# Город сбойного поиска в OBS-13: есть в списке CityAutocomplete (как в пробе Q-UI-38). Запрос с ним
# до сервера не доходит: подменён, а мимо подмены его оборвёт allow_real — на общем бэкенде ищем только SMALL_CITY
OTHER_CITY = "Haifa"
# Через сколько секунд без ответа проверяется вход (OBS-14, Q-UI-35)
LOGIN_WAIT_SECONDS = 35


def _fault(faults: NetworkFaults, url: str, failure: str) -> list[Request]:
    """Сбой по имени параметра: <имя>_<статус> — статус с пустым телом, network_error — обрыв,
    proxy_page_502 — страница посредника."""
    if failure == "network_error":
        return faults.abort(url, "POST")
    status = int(failure.rsplit("_", 1)[1])
    if failure.startswith("proxy_page"):
        return faults.respond_proxy_page(url, "POST", status)
    return faults.respond_empty(url, "POST", status)


def _search_finished(search_page: PwSearchPage) -> None:
    """Фронт обработал ответ поиска: сообщений поиск не показывает (Q-UI-28), признак конца — кнопка
    снова «Yalla!» вместо «Loading...». wait_for, а не expect: это предусловие, а не проверка."""
    search_page.submit_btn.filter(has_text="Yalla!").wait_for(state="visible")


# ---------------------------------------------------------------- REQ-UI-REG-05: регистрация


@allure.epic("Playwright Testing")
@allure.feature("Registration")
@allure.story("Backend failure")
@allure.title("Ответ 401, 500 или обрыв на регистрации: «Registration failed. Try again»")
@allure.tag("REQ-UI-REG-05")
@pytest.mark.parametrize("registration_failure", ["unauthorized_401", "server_error_500", "network_error"])
def test_pw_registration_failure_message(page: Page, backend_write_guard, registration_failure):
    """Ветка «любая другая ошибка» FE `Register` (Q-UI-31): не 400 с message и не 409. Тело пустое,
    запрос перехвачен и до бэкенда не доходит; email фальшивый — пользователь не создаётся."""
    registration_page = PwRegistrationPage(page)
    registration_page.open()
    sent = _fault(NetworkFaults(page), REGISTRATION, registration_failure)

    with allure.step(f"Регистрация: запрос перехвачен, сбой — {registration_failure}"):
        registration_page.fill_form(UserGenerator.get_random_user())
        send_and_settle(page, "POST", REGISTRATION_PATH, registration_page.submit)
        # Без пойманного запроса фронт получил бы ответ сервера, а не сбой
        require_intercepted(sent, f"POST {REGISTRATION_PATH}")

    with allure.step("Проверка: role=alert «Registration failed. Try again»"):
        expect(page.get_by_role("alert"), f"После сбоя {registration_failure} нет нужного сообщения").to_have_text(
            "Registration failed. Try again"
        )


# ---------------------------------------------------------------- OBS-15: 400 без message на регистрации


@allure.epic("Playwright Testing")
@allure.feature("Registration")
@allure.story("Backend failure")
@allure.title("Ответ 400 без message на регистрацию: в окне нет текста библиотеки")
@observation("REGISTER_ERROR_LIBRARY_TEXT")
@allure.tag("OBS-15")
def test_pw_registration_400_without_message(page: Page, backend_write_guard):
    """Тело — настоящий ответ сервера на пустой пароль (Q-API-16): поля message нет. Форма пустой пароль
    не отправляет, поэтому ответ подменён; email фальшивый, запрос до бэкенда не доходит. Факт: окно
    «Registration failed» с текстом axios «Request failed with status code 400» (Q-UI-31)."""
    registration_page = PwRegistrationPage(page)
    registration_page.open()
    sent = NetworkFaults(page).respond_recorded(
        REGISTRATION, "POST", 400, REGISTER_400_EMPTY_PASSWORD, source="Q-API-16"
    )

    with allure.step("Регистрация: запрос перехвачен, ответ 400 без message"):
        registration_page.fill_form(UserGenerator.get_random_user())
        send_and_settle(page, "POST", REGISTRATION_PATH, registration_page.submit)
        require_intercepted(sent, f"POST {REGISTRATION_PATH}")
        # Ветка 400 фронта показывает окно (Q-UI-31): без него проверять нечего
        registration_page.dialog.wait_for(state="visible")

    with allure.step("Проверка: в окне нет «Request failed with status code»"):
        expect(registration_page.dialog, "Окно регистрации показывает внутренний текст библиотеки").not_to_contain_text(
            "Request failed with status code"
        )


# ---------------------------------------------------------------- REQ-UI-CAR-02: форма машины


@allure.epic("Playwright Testing")
@allure.feature("Cars Management")
@allure.story("Backend failure")
@allure.title("Ответ 500 или обрыв на отправку машины: «Failed to submit car»")
@allure.tag("REQ-UI-CAR-02")
@pytest.mark.parametrize("car_failure", ["server_error_500", "network_error"])
def test_pw_car_form_failure_message(page: Page, shared_user, shared_car_cleanup, backend_write_guard, car_failure):
    """Ветка «ошибка» REQ-UI-CAR-02 при сбое сервера и сети (Q-UI-32). POST /v1/cars перехвачен,
    машина не создаётся; вход токеном общего пользователя, без запроса входа."""
    add_car_page = PwAddCarPage(page)
    add_car_page.restore_session(shared_user.api.token)
    add_car_page.open()
    PwLoginPage(page).logout_btn.wait_for(state="visible")
    car = CarGenerator.get_random_car()
    # Страховка: если перехват не сработает и машина создастся на бэкенде, очистка её удалит
    shared_car_cleanup.register(car.reg_number)
    add_car_page.fill_form(car)
    sent = _fault(NetworkFaults(page), CARS, car_failure)

    with allure.step(f"Отправка формы: POST /v1/cars перехвачен, сбой — {car_failure}"):
        send_and_settle(page, "POST", CARS_PATH, add_car_page.submit)
        require_intercepted(sent, f"POST {CARS_PATH}")

    with allure.step("Проверка: «Failed to submit car»"):
        expect(add_car_page.submit_error_message, f"После сбоя {car_failure} нет ошибки отправки").to_have_text(
            "Failed to submit car"
        )


# ---------------------------------------------------------------- DISC-11: повтор email, сторона UI


@allure.epic("Playwright Testing")
@allure.feature("Registration")
@allure.story("Frontend and API agreement")
@allure.title("Повтор занятого email: сообщение фронта о занятом email")
@known_bug("DUPLICATE_EMAIL_409_BRANCH_UNREACHABLE")
@allure.tag("DISC-11")
def test_pw_duplicate_email_message(page: Page, shared_user, backend_write_guard):
    """
    Сторона UI расхождения DISC-11. У фронта для занятого email своё сообщение — role=alert «User with that
    email already exists», но только на ответ 409; Swagger 409 не объявляет, и сервер на повтор отвечает 400
    (сторона сервера — test_api_registration_existing_user). Ответ настоящий: запрос пропускает allow_real,
    только если в нём email общего пользователя — отклонённая регистрация его не меняет и нового аккаунта
    не создаёт. Ответ 409 не подменяется. Факт: окно «Registration failed» с текстом сервера (Q-UI-08).
    """
    email = shared_user.user.email
    registration_page = PwRegistrationPage(page)
    registration_page.open()
    passed = NetworkFaults(page).allow_real(
        REGISTRATION, "POST", lambda request: (request.post_data_json or {}).get("username") == email
    )

    with allure.step(f"Регистрация с занятым email {email}: настоящий запрос"):
        # Пароль проходит правила и фронта, и API (DISC-01): отказ может быть только из-за занятого email
        registration_page.fill_form(UserGenerator.get_random_user(email=email))
        request = send_and_settle(page, "POST", REGISTRATION_PATH, registration_page.submit)
        require_intercepted(passed, f"POST {REGISTRATION_PATH} (пропуск на сервер)")
        require(request.response() is not None, f"Предусловие: ответа сервера нет, сбой {request.failure}")
        # Фронт обработал ответ: окно (400) или role=alert (409 и остальные, Q-UI-31)
        page.get_by_role("dialog").or_(page.get_by_role("alert")).first.wait_for(state="visible")

    with allure.step("Проверка: role=alert «User with that email already exists»"):
        expect(
            page.get_by_role("alert").filter(has_text="User with that email already exists"),
            "На повтор email фронт не показал своё сообщение о занятом email",
        ).to_be_visible()


# ---------------------------------------------------------------- OBS-12: сбой поиска


@allure.epic("Playwright Testing")
@allure.feature("Search")
@allure.story("Backend failure")
@allure.title("Сбой поиска обозначен сообщением")
@observation("SEARCH_FAILURE_NOT_SHOWN")
@allure.tag("OBS-12")
@pytest.mark.parametrize("search_failure", ["server_error_500", "network_error", "proxy_page_502"])
def test_pw_search_failure_announced(page: Page, backend_write_guard, search_failure):
    """Гость, поиск SMALL_CITY; ответ подменён (Q-UI-24, Q-UI-28) и до бэкенда не доходит. Критерий OBS-12 —
    блок role=status или role=alert, как у OBS-04; текст сообщения не задан, поэтому не сверяется."""
    search_page = PwSearchPage(page)
    search_page.open()
    sent = _fault(NetworkFaults(page), SEARCH, search_failure)

    with allure.step(f"Поиск {SearchDataGenerator.SMALL_CITY}: запрос перехвачен, сбой — {search_failure}"):
        send_and_settle(page, "POST", SEARCH_PATH, lambda: search_page.search_today(SearchDataGenerator.SMALL_CITY))
        require_intercepted(sent, f"POST {SEARCH_PATH}")
        _search_finished(search_page)

    with allure.step("Проверка: на экране есть сообщение о сбое"):
        expect(search_page.messages.first, f"Сбой поиска {search_failure} ничем не обозначен").to_be_visible()


# ---------------------------------------------------------------- OBS-13: прошлая выдача после сбоя


@allure.epic("Playwright Testing")
@allure.feature("Search")
@allure.story("Backend failure")
@allure.title("После сбоя поиска по другому городу прошлая выдача не выдаётся за новую")
@observation("STALE_RESULTS_AFTER_FAILED_SEARCH")
@allure.tag("OBS-13")
def test_pw_failed_search_drops_stale_results(page: Page, backend_write_guard):
    """
    Настоящий поиск SMALL_CITY, затем другой город и даты — этот поиск 500 с пустым телом (Q-UI-38).
    На сервер уходит только первый поиск: allow_real пропускает один запрос и только по SMALL_CITY,
    любой другой поиск, дошедший до него мимо подмены, обрывается и роняет тест (backend_write_guard).
    Критерий OBS-13: карточек прошлой выдачи нет, или есть сообщение role=status / role=alert.
    """
    city = SearchDataGenerator.SMALL_CITY
    search_page = PwSearchPage(page)
    search_page.open()
    faults = NetworkFaults(page)
    real = faults.allow_real(SEARCH, "POST", lambda request: (request.post_data_json or {}).get("city") == city)

    with allure.step(f"Настоящий поиск {city}"):
        request = send_and_settle(page, "POST", SEARCH_PATH, lambda: search_page.search_today(city))
        require_intercepted(real, f"POST {SEARCH_PATH} {city} (пропуск на сервер)")
        response = request.response()
        require(response is not None and response.status == 200, f"Предусловие: поиск {city} не ответил 200")
        _search_finished(search_page)
        search_page.cards.first.wait_for(state="visible")
        before = set(search_page.card_links())
        require(bool(before), f"Предусловие: в выдаче {city} нет карточек — проверять нечего")

    today = date.today()
    search_page.choose_city(OTHER_CITY)
    search_page.pick_range(today + timedelta(days=2), today + timedelta(days=3))
    sent = faults.respond_empty(SEARCH, "POST", 500)

    with allure.step(f"Поиск {OTHER_CITY} на другие даты: ответ подменён на 500"):
        send_and_settle(page, "POST", SEARCH_PATH, search_page.submit)
        require_intercepted(sent, f"POST {SEARCH_PATH} {OTHER_CITY}")
        sent_city = (sent[0].post_data_json or {}).get("city")
        require(sent_city == OTHER_CITY, f"Предусловие: сбойный поиск ушёл с city={sent_city!r}, а не {OTHER_CITY}")
        _search_finished(search_page)

    with allure.step("Проверка: карточек прошлой выдачи нет или есть сообщение о сбое"):
        stale = before & set(search_page.card_links())
        messages = search_page.messages.count()
        assert not stale or messages, (
            f"После сбоя поиска {OTHER_CITY} на экране {len(stale)} карточек прошлого поиска {city}, сообщения нет"
        )


# ---------------------------------------------------------------- OBS-14: вход без предела ожидания


@allure.epic("Playwright Testing")
@allure.feature("Login")
@allure.story("Backend failure")
@allure.title("Вход без ответа 35 с: ожидание обозначено или прервано")
@observation("LOGIN_WAIT_UNBOUNDED")
@allure.tag("OBS-14")
def test_pw_login_wait_bounded(page: Page, backend_write_guard):
    """
    Запрос входа удерживается (Q-UI-35) и через 35 с обрывается; проверка — через 35 с, пока он ещё висит.
    Пользователь не регистрируется, запрос до бэкенда не доходит. Критерий OBS-14: кнопка не «Loading...»,
    или есть сообщение (role=status / role=alert / role=dialog), или фронт сам прервал запрос.
    Тест длится не меньше LOGIN_WAIT_SECONDS.
    """
    user = UserGenerator.get_random_user()
    login_page = PwLoginPage(page)
    login_page.open()
    held = NetworkFaults(page).hold(LOGIN, "POST", LOGIN_WAIT_SECONDS)
    # Прерывание фронтом — сетевая ошибка запроса до того, как его оборвёт удержание
    failed: list[Request] = []
    is_login = api_request("POST", LOGIN_PATH)
    page.on("requestfailed", lambda request: failed.append(request) if is_login(request) else None)

    try:
        with allure.step(f"Вход: запрос удерживается {LOGIN_WAIT_SECONDS} с"):
            with page.expect_request(is_login):
                login_page.login(user.email, user.password)
            held.wait()

        with allure.step(f"Проверка через {LOGIN_WAIT_SECONDS} с: ожидание обозначено или прервано"):
            button = login_page.submit_btn.inner_text()
            messages = page.locator("[role=status], [role=alert], [role=dialog]").all_inner_texts()
            assert button != "Loading..." or messages or failed, (
                f"Через {LOGIN_WAIT_SECONDS} с без ответа кнопка «{button}», сообщений нет, запрос не прерван"
            )
    finally:
        held.finish()
