"""
Сессия в интерфейсе: REQ-UI-SESSION-01, REQ-UI-SESSION-02, REQ-SEC-06 и наблюдение OBS-05.

Ответ 401 подменяется (utils/network_faults.py): сценарий «сервер перестал принимать токен»
воспроизводится без порчи настоящей сессии, а запрос POST /v1/cars до бэкенда не доходит.

Пользователи — по правилу CLAUDE.md (меняется ли состояние пользователя на сервере):
  * тесты с подменённым 401 меняют только localStorage браузера — общий shared_user; вход —
    токеном в localStorage, без запроса входа (защита backend_write_guard оборвала бы его POST);
  * тесты выхода берут свежего temp_user: выход — состояние пользователя на сервере (REQ-SEC-06);
    появись серверный выход, токен общего пользователя перестал бы работать у соседних тестов.
"""

import re
from urllib.parse import urlsplit

import allure
import pytest
from playwright.sync_api import Page, expect

from api.car_api import IlCarroAPI
from data.data_generator import CarGenerator
from data.known_bugs import known_bug
from data.observations import observation
from pages.pw_add_car_page import PwAddCarPage
from pages.pw_login_page import PwLoginPage
from utils.network_faults import CARS, NetworkFaults, require_intercepted, send_and_settle
from utils.preconditions import require

pytestmark = [pytest.mark.ui, pytest.mark.regression]


@pytest.fixture
def session_after_401(page: Page, shared_user, shared_car_cleanup, backend_write_guard) -> PwAddCarPage:
    """Залогиненный пользователь отправил форму машины, а сервер ответил 401 (ответ подменён).

    Сценарий общий для REQ-UI-SESSION-01 и OBS-05, проверки — в разных тестах. Возвращает страницу
    формы в состоянии «ответ 401 получен и обработан перехватчиком фронта».
    """
    add_car_page = PwAddCarPage(page)
    add_car_page.restore_session(shared_user.api.token)
    add_car_page.open()
    PwLoginPage(page).logout_btn.wait_for(state="visible")
    require(add_car_page.local_storage_item("token") is not None, "Предусловие: после входа в localStorage нет token")

    car = CarGenerator.get_random_car()
    # Страховка: если перехват не сработает и машина создастся на бэкенде, очистка её удалит
    shared_car_cleanup.register(car.reg_number)
    add_car_page.fill_form(car)

    sent = NetworkFaults(page).respond(CARS, "POST", 401)
    with allure.step("Отправка формы: POST /v1/cars перехвачен, ответ подменён на 401"):
        send_and_settle(page, "POST", "/v1/cars", add_car_page.submit)
        # Без пойманного запроса реакцию фронта на 401 проверять нельзя: 401 он не получал
        require_intercepted(sent, "POST /v1/cars")
        require(
            bool(sent[0].headers.get("authorization")),
            "Предусловие: запрос ушёл без заголовка Authorization — сессии не было ещё до ответа 401",
        )
        # Фронт обработал ответ: форма показала ошибку отправки (Q-UI-13, Q-UI-17). Ждём состояние,
        # а не читаем localStorage сразу после ответа: обработчики страницы могли ещё не отработать
        add_car_page.submit_error_message.wait_for(state="visible")
    return add_car_page


@allure.epic("Playwright Testing")
@allure.feature("Session")
@allure.story("Response 401")
@allure.title("После 401 фронт удаляет token и запоминает postLoginRedirect")
@allure.tag("REQ-UI-SESSION-01")
def test_pw_401_clears_token_and_remembers_redirect(session_after_401):
    with allure.step("Проверка localStorage после ответа 401"):
        assert session_after_401.local_storage_item("token") is None, "После ответа 401 token остался в localStorage"
        redirect = session_after_401.local_storage_item("postLoginRedirect")
        assert redirect == session_after_401.endpoint, (
            f"После ответа 401 ожидали postLoginRedirect={session_after_401.endpoint!r}, в localStorage {redirect!r}"
        )


@allure.epic("Playwright Testing")
@allure.feature("Session")
@allure.story("Response 401")
@allure.title("После 401 пользователь попадает на страницу входа")
@observation("STALE_SESSION_UI_AFTER_401")
@allure.tag("OBS-05")
def test_pw_401_redirects_to_login(page: Page, session_after_401):
    """Токен удалён, запрос отклонён — пользователю остаётся только войти заново (OBS-05)."""
    with allure.step("Проверка: открыта страница входа"):
        expect(page, "После ответа 401 пользователь остался на прежней странице").to_have_url(re.compile(r"/login$"))


@allure.epic("Playwright Testing")
@allure.feature("Session")
@allure.story("Response 401")
@allure.title("После 401 в навигации нет «Log out»")
@observation("STALE_SESSION_UI_AFTER_401")
@allure.tag("OBS-05")
def test_pw_401_hides_logout(page: Page, session_after_401):
    """Токена уже нет, а навигация показывает пользователя залогиненным (OBS-05)."""
    with allure.step("Проверка: кнопки «Log out» в навигации нет"):
        expect(
            PwLoginPage(page).logout_btn, "После ответа 401 токен удалён, но «Log out» остался в навигации"
        ).to_be_hidden()


@allure.epic("Playwright Testing")
@allure.feature("Session")
@allure.story("Log out")
@allure.title("«Log out» удаляет токен и переводит на /search")
@allure.tag("REQ-UI-SESSION-02")
def test_pw_logout_clears_token_and_opens_search(page: Page, temp_user):
    login_page = PwLoginPage(page)
    login_page.login_as(temp_user.user)
    require(login_page.local_storage_item("token") is not None, "Предусловие: после входа в localStorage нет token")

    login_page.click_logout()

    with allure.step("Проверка: открыт /search, token удалён"):
        expect(page, "«Log out» не перевёл на /search").to_have_url(re.compile(r"/search(\?.*)?$"))
        assert login_page.local_storage_item("token") is None, "После «Log out» token остался в localStorage"


@pytest.mark.security
@allure.epic("Playwright Testing")
@allure.feature("Session")
@allure.story("Log out")
@allure.title("Токен после «Log out» не принимается API")
@known_bug("LOGOUT_TOKEN_STILL_VALID")
@allure.tag("REQ-SEC-06")
def test_pw_token_rejected_after_logout(page: Page, temp_user):
    """
    Серверного выхода в API нет: «Log out» только удаляет токен в браузере, и тот, кто успел
    его скопировать, продолжает работать от имени пользователя (ASVS V3.3.1, Q-UI-14).
    """
    login_page = PwLoginPage(page)
    login_page.login_as(temp_user.user)

    # Токен этой сессии браузера: его и должен отозвать выход. В шаги и логи он не попадает
    session_token = login_page.local_storage_item("token")
    require(bool(session_token), "Предусловие: после входа в localStorage нет token")
    api = IlCarroAPI()
    api.session.headers.update({"Authorization": f"Bearer {session_token}"})

    with allure.step("Предусловие: до выхода токен сессии принимается API"):
        before = api.get_my_cars()
        require(before.status_code == 200, f"До выхода GET /v1/cars/my ответил {before.status_code}, проверять нечего")

    with allure.step("Выход через «Log out»"):
        login_page.click_logout()
        login_page.logout_btn.wait_for(state="hidden")
        require(login_page.local_storage_item("token") is None, "Предусловие: «Log out» не удалил token в браузере")
        require(urlsplit(page.url).path == "/search", f"Предусловие: после «Log out» открыт {page.url}, а не /search")

    with allure.step("Проверка: тот же токен после выхода — 401"):
        after = api.get_my_cars()
        assert after.status_code == 401, (
            f"Токен, с которым пользователь вышел, всё ещё принимается: GET /v1/cars/my ответил {after.status_code}"
        )
