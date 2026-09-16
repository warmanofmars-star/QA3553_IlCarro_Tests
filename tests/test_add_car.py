import allure
import pytest
from pages.add_car_page import AddCarPage
from data.data_generator import CarGenerator
from utils.logger import get_logger

logger = get_logger("TEST")


@allure.epic("UI Testing")
@allure.feature("Add Car Page (Let the car work)")
@allure.story("Positive Add Car")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.xfail(reason="Баг окружения: Сервер отваливается по таймауту при создании машины через UI")
@pytest.mark.parametrize("fuel_type, car_class, scenario", [
    ("Petrol", "Economy", "Добавление бензиновой машины эконом-класса"),
    ("Electric", "Premium", "Добавление премиального электрокара")
])
def test_add_car_success(authenticated_driver, fuel_type, car_class, scenario):
    with allure.step(f"Сценарий: {scenario}"):
        logger.info(f"--- ЗАПУСК ТЕСТА: {scenario} ---")
        add_car_page = AddCarPage(authenticated_driver)

        # Генерируем машину, ПРИНУДИТЕЛЬНО задавая ей нужный тип топлива и класс!
        car = CarGenerator.get_random_car(fuel=fuel_type, car_class=car_class)

        # МАГИЯ ДАТАКЛАССОВ В ДЕЙСТВИИ:
        logger.info(f"Сгенерированные данные: {car}")

        add_car_page.open()

        # Пошагово заполняем форму, используя твои модульные методы из AddCarPage:
        add_car_page.fill_city(car.city)
        add_car_page.fill_text_fields(car)
        add_car_page.fill_dropdowns(car)

        # Нажимаем кнопку Y'alla!
        add_car_page.submit()

        # Проверка: читаем текст из модального окна H3
        actual_message = add_car_page.get_global_message_text()
        assert "Car added" in actual_message, f"Машина не добавилась! Текст ошибки: {actual_message}"

        logger.info("--- ТЕСТ УСПЕШНО ЗАВЕРШЕН ---")