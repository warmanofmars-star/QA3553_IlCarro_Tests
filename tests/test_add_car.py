import logging

import allure
import pytest

from data.data_generator import CarGenerator
from pages.add_car_page import AddCarPage
from pages.login_page import LoginPage
from utils.preconditions import require

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.ui


def _open_car_form(driver) -> AddCarPage:
    """Форма машины в браузере, залогиненном токеном общего пользователя (shared_authenticated_driver)."""
    add_car_page = AddCarPage(driver)
    add_car_page.open()
    require(LoginPage(driver).is_logout_button_visible(), "Предусловие: вход токеном не сработал")
    return add_car_page


@pytest.mark.smoke
@allure.epic("UI Testing")
@allure.feature("Add Car Page (Let the car work)")
@allure.story("Positive Add Car")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-UI-CAR-02")
@pytest.mark.parametrize(
    "fuel_type, car_class, scenario",
    [
        ("Petrol", "Economy", "Добавление бензиновой машины эконом-класса"),
        ("Electric", "Premium", "Добавление премиального электрокара"),
    ],
)
def test_add_car_success(shared_authenticated_driver, shared_car_cleanup, fuel_type, car_class, scenario):
    with allure.step(f"Сценарий: {scenario}"):
        logger.info(f"--- ЗАПУСК ТЕСТА: {scenario} ---")

        # Генерируем машину, ПРИНУДИТЕЛЬНО задавая ей нужный тип топлива и класс!
        car = CarGenerator.get_random_car(fuel=fuel_type, car_class=car_class)

        # МАГИЯ ДАТАКЛАССОВ В ДЕЙСТВИИ:
        logger.info(f"Сгенерированные данные: {car}")
        # Машина создаётся через UI — номер регистрируем, чтобы фабрика удалила её после теста
        shared_car_cleanup.register(car.reg_number)

        add_car_page = _open_car_form(shared_authenticated_driver)

        # Пошагово заполняем форму, используя твои модульные методы из AddCarPage:
        add_car_page.fill_city(car.city)
        add_car_page.fill_text_fields(car)
        add_car_page.fill_dropdowns(car)

        # Нажимаем кнопку Y'alla!
        add_car_page.submit()

        # Проверка:
        assert add_car_page.is_form_cleared() is True, "Форма не очистилась! Машина не добавлена."

        logger.info("--- ТЕСТ УСПЕШНО ЗАВЕРШЕН ---")


@pytest.mark.regression
@pytest.mark.hybrid
@allure.epic("UI Testing")
@allure.feature("Add Car Page (Let the car work)")
@allure.story("Negative Add Car - Duplicate Serial Number")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-UI-CAR-02")
def test_add_car_duplicate(shared_authenticated_driver, shared_create_car):
    with allure.step("API PRECONDITION: Создаем машину через бэкенд"):
        car = shared_create_car()
        logger.info(f"API успешно создал машину с номером: {car.reg_number}")

    with allure.step("UI SCENARIO: Пытаемся добавить машину с тем же номером"):
        add_car_page = _open_car_form(shared_authenticated_driver)

        # Заполняем форму ТЕМИ ЖЕ сгенерированными данными (главное - тот же reg_number)
        add_car_page.fill_city(car.city)
        add_car_page.fill_text_fields(car)
        add_car_page.fill_dropdowns(car)

        add_car_page.submit()

    with allure.step("UI ASSERT: Проверка обработки дубликата фронтендом"):
        # 1. Проверяем появление правильного текста ошибки
        error_text = add_car_page.get_submit_error_text()
        logger.info(f"Фронтенд выдал ошибку: {error_text}")

        assert error_text == "Failed to submit car", (
            f"Ожидалась ошибка 'Failed to submit car', но получили '{error_text}'"
        )

        # 2. Проверяем, что форма НЕ очистилась (данные остались на месте)
        # Обращаемся к элементу правильно, чтобы PyCharm не ругался!
        current_make_value = add_car_page.find(add_car_page.MAKE_INPUT).get_attribute("value")
        assert current_make_value == car.make, "Форма неожиданно очистилась после ошибки сервера!"
