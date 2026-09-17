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


@allure.epic("Playwright Testing")
@allure.feature("Cars Management")
@allure.story("Negative Add Car - Duplicate")
@allure.title("Создание дубликата машины (Playwright + API)")
def test_pw_add_car_duplicate(page: Page, auth_api):
    car = CarGenerator.get_random_car()

    with allure.step("API PRECONDITION: Создаем машину"):
        car_payload = {
            "serialNumber": car.reg_number,
            "manufacture": car.make,
            "model": car.model,
            "year": str(car.year),
            "fuel": car.fuel,
            "seats": int(car.seats),
            "carClass": car.car_class,
            "pricePerDay": float(car.price),
            "about": car.about,
            "city": car.city
        }
        auth_api.add_car(car_payload)

    with allure.step("UI SCENARIO: Пытаемся создать ту же машину через UI"):
        login_page = PwLoginPage(page)
        login_page.open()
        login_page.login(VALID_EMAIL, VALID_PASSWORD)
        login_page.click_ok_button()

        add_car_page = PwAddCarPage(page)
        add_car_page.open()
        add_car_page.fill_form(car)
        add_car_page.submit()

    with allure.step("UI ASSERT: Проверка хитрой inline-ошибки"):
        # Проверяем, что появилась та самая маленькая строчка
        add_car_page.check_submit_error("Failed to submit car")

        # Проверяем, что форма зависла и не очистилась
        add_car_page.check_make_field_value(car.make)