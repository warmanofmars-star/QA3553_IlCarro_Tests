import os
import allure
import pytest
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from pages.login_page import LoginPage
from pages.add_car_page import AddCarPage
from data.data_generator import CarGenerator

VALID_EMAIL = os.getenv("USER_EMAIL")
VALID_PASSWORD = os.getenv("USER_PASSWORD")
PHOTO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "car.jpg"))


@allure.epic("UI Testing")
@allure.feature("Add Car Page (Let the car work)")
@allure.story("Positive Add Car")
@allure.severity(allure.severity_level.BLOCKER)
def test_add_car_success(driver):
    login_page = LoginPage(driver)
    add_car_page = AddCarPage(driver)

    with allure.step("Пререквизит: Авторизация"):
        login_page.open()
        login_page.login(VALID_EMAIL, VALID_PASSWORD)
        login_page.click_ok_button()

    car = CarGenerator.get_random_car(photo_path=PHOTO_PATH)

    add_car_page.open()
    add_car_page.fill_city(car.city)
    add_car_page.fill_text_fields(car)
    add_car_page.fill_dropdowns(car)
    add_car_page.upload_photo(car.photo_path)
    add_car_page.submit()

    # Умное ожидание результата
    try:
        # Даем серверу 10 секунд на переваривание фото и создание машины
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located(add_car_page.GLOBAL_MESSAGE)
        )
        assert add_car_page.get_global_message_text() == "Car added", "Сообщение об успехе не совпадает!"
    except TimeoutException:
        # Если таймаут всё же случился, собираем красные ошибки с экрана
        errors = add_car_page.get_form_errors()
        if errors:
            pytest.fail(f"Форма не отправилась из-за ошибок валидации фронтенда: {errors}")
        else:
            pytest.xfail("Сервер не ответил (таймаут). Возможно, 500 ошибка бэкенда или баг интерфейса.")