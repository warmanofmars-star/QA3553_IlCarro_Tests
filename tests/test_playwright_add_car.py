import allure
import pytest
from playwright.sync_api import Page
from pages.pw_login_page import PwLoginPage
from pages.pw_add_car_page import PwAddCarPage
from data.data_generator import CarGenerator


@pytest.mark.smoke
@allure.epic("Playwright Testing")
@allure.feature("Cars Management")
@allure.story("Real E2E Car Addition")
@allure.title("Реальное добавление машины (E2E Playwright)")
def test_real_add_car_success(page: Page, temp_user, sys_logger): # <-- Добавили temp_user
    car = CarGenerator.get_random_car()
    sys_logger.info(f"Playwright будет создавать машину: {car}")
    user = temp_user["user"] # <-- Берем чистые креды

    with allure.step("Авторизация"):
        login_page = PwLoginPage(page)
        login_page.open()
        login_page.login(user.email, user.password) # <-- Логинимся в песочницу
        login_page.click_ok_button()

    with allure.step("Переход на форму и отправка данных"):
        add_car_page = PwAddCarPage(page)
        add_car_page.open()
        add_car_page.fill_form(car)
        add_car_page.submit()

    with allure.step("Проверка через ожидание очистки формы"):
        add_car_page.check_form_cleared()
        sys_logger.info(f"Машина с номером {car.reg_number} успешно добавлена через Playwright!")


@pytest.mark.hybrid
@pytest.mark.regression
@allure.epic("Hybrid Testing")
@allure.feature("Playwright: Cars Management")
@allure.story("API Setup -> UI Duplicate Check (Negative)")
@allure.title("Создание дубликата машины (Playwright + API)")
def test_pw_add_car_duplicate(page: Page, temp_user): # <-- Заменили auth_api на temp_user
    car = CarGenerator.get_random_car()
    api = temp_user["api"] # <-- Достаем API-клиента песочницы
    user = temp_user["user"] # <-- Достаем UI-креды песочницы

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
        api.add_car(car_payload)

    with allure.step("UI SCENARIO: Пытаемся создать ту же машину через UI"):
        login_page = PwLoginPage(page)
        login_page.open()
        login_page.login(user.email, user.password) # <-- Синхронизируем UI с тем же Sandbox-юзером
        login_page.click_ok_button()

        add_car_page = PwAddCarPage(page)
        add_car_page.open()
        add_car_page.fill_form(car)
        add_car_page.submit()

    with allure.step("UI ASSERT: Проверка хитрой inline-ошибки"):
        add_car_page.check_submit_error("Failed to submit car")
        add_car_page.check_make_field_value(car.make)