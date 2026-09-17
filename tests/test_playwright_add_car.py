import os
import allure
from playwright.sync_api import Page
from pages.pw_login_page import PwLoginPage
from pages.pw_add_car_page import PwAddCarPage
from data.data_generator import CarGenerator
from utils.logger import get_logger

VALID_EMAIL = os.getenv("USER_EMAIL")
VALID_PASSWORD = os.getenv("USER_PASSWORD")
logger = get_logger("TEST")

@allure.epic("Playwright Testing")
@allure.feature("Cars Management")
@allure.story("Real E2E Car Addition")
@allure.title("Реальное добавление машины (E2E Playwright)")
def test_real_add_car_success(page: Page):
    # Генерируем 100% случайную валидную машину (генератор сам позаботится об уникальности reg_number)
    car = CarGenerator.get_random_car()
    logger.info(f"Playwright будет создавать машину: {car}")

    with allure.step("Авторизация"):
        login_page = PwLoginPage(page)
        login_page.open()
        login_page.login(VALID_EMAIL, VALID_PASSWORD)
        login_page.click_ok_button()

    with allure.step("Переход на форму и отправка данных"):
        add_car_page = PwAddCarPage(page)
        add_car_page.open()
        add_car_page.fill_form(car) # Передаем весь объект-датакласс!
        add_car_page.submit()

    with allure.step("Проверка через ожидание очистки формы"):
        add_car_page.check_form_cleared()
        logger.info(f"Машина с номером {car.reg_number} успешно добавлена через Playwright!")