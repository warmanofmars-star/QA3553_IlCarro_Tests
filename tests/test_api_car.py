import allure
import datetime
import pytest
from api.car_api import IlCarroAPI
from data.data_generator import CarGenerator
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from schemas.car_schemas import GET_CARS_RESPONSE_SCHEMA, MESSAGE_RESPONSE_SCHEMA

pytestmark = pytest.mark.api


@pytest.mark.smoke
@pytest.mark.contract
@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Create Car successfully")
@allure.severity(allure.severity_level.BLOCKER)
def test_api_add_car_success(auth_api):
    with allure.step("1. Подготовка валидного JSON (CarDto)"):
        car_obj = CarGenerator.get_random_car()

    with allure.step("2. Отправка POST запроса на создание машины"):
        response = auth_api.add_car(car_obj.to_api_payload())

    with allure.step("3. Проверка статус-кода и строгого контракта ответа"):
        assert response.status_code == 200, f"Бэкенд вернул ошибку: {response.status_code} - {response.text}"

        try:
            validate(instance=response.json(), schema=MESSAGE_RESPONSE_SCHEMA)
        except ValidationError as e:
            pytest.fail(f"Бэкенд нарушил контракт (лишние поля или неверный тип)!\nОшибка: {e.message}")

        assert "Car added" in response.json().get("message", ""), "Неверное сообщение от сервера"


@pytest.mark.smoke
@pytest.mark.contract
@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Full Lifecycle (Create -> Read -> Delete)")
@allure.severity(allure.severity_level.CRITICAL)
def test_api_car_lifecycle(auth_api):
    car_obj = CarGenerator.get_random_car()
    serial_number = car_obj.reg_number

    with allure.step("1. Создаем машину"):
        response_add = auth_api.add_car(car_obj.to_api_payload())
        assert response_add.status_code == 200, f"Не удалось создать машину! Ответ сервера: {response_add.text}"

    with allure.step("2. Проверяем, что машина появилась в списке 'My Cars'"):
        response_get = auth_api.get_my_cars()
        assert response_get.status_code == 200, "Ошибка получения списка машин"

        response_json = response_get.json()

        try:
            validate(instance=response_json, schema=GET_CARS_RESPONSE_SCHEMA)
        except ValidationError as e:
            pytest.fail(f"Бэкенд вернул невалидную структуру JSON!\nОшибка: {e.message}")

        cars_list = response_get.json().get("cars", [])
        serial_numbers_in_db = [car.get("serialNumber") for car in cars_list]
        assert serial_number in serial_numbers_in_db, f"Машина с номером {serial_number} не найдена в базе!"

    with allure.step("3. Удаляем созданную машину"):
        response_delete = auth_api.delete_car(serial_number)
        assert response_delete.status_code == 200, "Ошибка при удалении машины"
        assert "Car deleted" in response_delete.json().get("message", ""), "Неверное сообщение при удалении"

    with allure.step("4. Убеждаемся, что машина исчезла из базы"):
        response_get_after = auth_api.get_my_cars()
        cars_list_after = response_get_after.json().get("cars", [])
        serial_numbers_after = [car.get("serialNumber") for car in cars_list_after]
        assert serial_number not in serial_numbers_after, "Машина не удалилась из базы!"


@pytest.mark.regression
@pytest.mark.security
@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Negative - Unauthorized Access")
@allure.severity(allure.severity_level.CRITICAL)
def test_api_add_car_unauthorized():
    api = IlCarroAPI()
    car_obj = CarGenerator.get_random_car()

    with allure.step("Попытка создать машину без токена авторизации"):
        response = api.add_car(car_obj.to_api_payload())

    with allure.step("Проверка статуса 403 Forbidden (или 401)"):
        assert response.status_code in [401, 403], \
            f"Ожидался статус блокировки (401/403), но получен {response.status_code}"


@pytest.mark.smoke
@allure.epic("API Testing")
@allure.feature("Car Booking Flow")
@allure.story("Integration: Create -> Search -> Book -> Delete")
@allure.severity(allure.severity_level.BLOCKER)
def test_api_car_booking_flow(auth_api):
    today = datetime.date.today()
    start_date = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    end_date = (today + datetime.timedelta(days=7)).strftime("%Y-%m-%d")

    car_obj = CarGenerator.get_random_car()
    serial_number = car_obj.reg_number
    target_city = car_obj.city

    with allure.step("1. Создаем машину для бронирования"):
        response_add = auth_api.add_car(car_obj.to_api_payload())
        assert response_add.status_code == 200, f"Не удалось создать машину: {response_add.text}"

    with allure.step(f"2. Ищем машины в городе {target_city} на заданные даты"):
        response_search = auth_api.search_cars(target_city, start_date, end_date)
        assert response_search.status_code == 200, f"Ошибка поиска: {response_search.text}"
        cars_found = response_search.json().get("cars", [])
        serial_numbers_found = [car.get("serialNumber") for car in cars_found]
        assert serial_number in serial_numbers_found, "Созданная машина не появилась в поиске!"

    with allure.step("3. Бронируем найденную машину"):
        response_book = auth_api.book_car(serial_number, start_date, end_date)
        assert response_book.status_code == 200, f"Ошибка бронирования: {response_book.text}"
        assert "successful" in response_book.json().get("message", "").lower(), "Сообщение о бронировании не содержит подтверждения"

    with allure.step("4. Убираем за собой (удаляем машину)"):
        auth_api.delete_car(serial_number)