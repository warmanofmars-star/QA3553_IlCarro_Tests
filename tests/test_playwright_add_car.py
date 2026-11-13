import logging

import allure
import pytest
from playwright.sync_api import Page

from data.data_generator import CarGenerator
from pages.pw_add_car_page import PwAddCarPage
from pages.pw_login_page import PwLoginPage

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.ui


def _open_car_form(page: Page, token: str) -> PwAddCarPage:
    """Форма машины, открытая залогиненным пользователем: вход токеном, без запроса входа к бэкенду."""
    add_car_page = PwAddCarPage(page)
    add_car_page.restore_session(token)
    add_car_page.open()
    # wait_for, а не expect: вход — предусловие, а не проверка
    PwLoginPage(page).logout_btn.wait_for(state="visible")
    return add_car_page


@pytest.mark.smoke
@allure.epic("Playwright Testing")
@allure.feature("Cars Management")
@allure.story("Real E2E Car Addition")
@allure.title("Реальное добавление машины (E2E Playwright)")
@allure.tag("REQ-UI-CAR-02")
def test_real_add_car_success(page: Page, shared_user, shared_car_cleanup):
    car = CarGenerator.get_random_car()
    # Машина создаётся через UI — номер регистрируем, чтобы очистка удалила её после теста
    shared_car_cleanup.register(car.reg_number)
    logger.info(f"Playwright будет создавать машину: {car}")

    with allure.step("Переход на форму и отправка данных"):
        add_car_page = _open_car_form(page, shared_user.api.token)
        add_car_page.fill_form(car)
        add_car_page.submit()

    with allure.step("Проверка через ожидание очистки формы"):
        add_car_page.check_form_cleared()
        logger.info(f"Машина с номером {car.reg_number} успешно добавлена через Playwright!")


@pytest.mark.hybrid
@pytest.mark.regression
@allure.epic("Hybrid Testing")
@allure.feature("Playwright: Cars Management")
@allure.story("API Setup -> UI Duplicate Check (Negative)")
@allure.title("Создание дубликата машины (Playwright + API)")
@allure.tag("REQ-UI-CAR-02")
def test_pw_add_car_duplicate(page: Page, shared_user, shared_create_car):
    with allure.step("API PRECONDITION: Создаем машину"):
        car = shared_create_car()

    with allure.step("UI SCENARIO: Пытаемся создать ту же машину через UI"):
        add_car_page = _open_car_form(page, shared_user.api.token)
        add_car_page.fill_form(car)
        add_car_page.submit()

    with allure.step("UI ASSERT: Проверка хитрой inline-ошибки"):
        add_car_page.check_submit_error("Failed to submit car")
        add_car_page.check_make_field_value(car.make)
