import allure
import datetime
import pytest
from api.car_api import IlCarroAPI
from data.known_bugs import known_bug
from utils.car_state import my_cars
from utils.preconditions import require
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
@allure.tag("REQ-CAR-01")
def test_api_add_car_success(auth_api, car_cleanup):
    with allure.step("1. Подготовка валидного JSON (CarDto)"):
        car_obj = CarGenerator.get_random_car()
        # Создание — предмет теста, поэтому не через фабрику; номер регистрируем для очистки
        car_cleanup.register(car_obj.reg_number)

    with allure.step("2. Отправка POST запроса на создание машины"):
        response = auth_api.add_car(car_obj.to_api_payload())

    with allure.step("3. Состояние: машина появилась в /v1/cars/my владельца"):
        assert car_obj.reg_number in my_cars(auth_api),             f"Машина {car_obj.reg_number} не сохранилась: её нет в /v1/cars/my. Ответ создания: {response.status_code} {response.text}"

    with allure.step("4. Проверка статус-кода и строгого контракта ответа"):
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
@allure.tag("REQ-CAR-01", "REQ-CAR-08")
def test_api_car_lifecycle(auth_api, car_cleanup):
    car_obj = CarGenerator.get_random_car()
    serial_number = car_obj.reg_number
    # Создание и удаление — предмет теста; регистрация страхует, если тест упадёт посередине
    car_cleanup.register(serial_number)

    with allure.step("1. Создаем машину"):
        response_add = auth_api.add_car(car_obj.to_api_payload())

    with allure.step("2. Проверяем, что машина появилась в списке 'My Cars'"):
        response_get = auth_api.get_my_cars()
        assert response_get.status_code == 200, "Ошибка получения списка машин"

        response_json = response_get.json()

        try:
            validate(instance=response_json, schema=GET_CARS_RESPONSE_SCHEMA)
        except ValidationError as e:
            pytest.fail(f"Бэкенд вернул невалидную структуру JSON!\nОшибка: {e.message}")

        serial_numbers_in_db = [car.get("serialNumber") for car in response_json.get("cars", [])]
        assert serial_number in serial_numbers_in_db, f"Машина с номером {serial_number} не найдена в базе!"
        # Для статистики очистки: машина точно была создана, дальше её удалит сам тест
        car_cleanup.mark_created(serial_number)
        assert response_add.status_code == 200, f"Машина сохранена, но ответ создания не 200: {response_add.text}"

    with allure.step("3. Удаляем созданную машину"):
        response_delete = auth_api.delete_car(serial_number)

    with allure.step("4. Убеждаемся, что машина исчезла из базы, и проверяем ответ удаления"):
        assert serial_number not in my_cars(auth_api), "Машина не удалилась из базы!"
        assert response_delete.status_code == 200, f"Машина удалена, но ответ не 200: {response_delete.text}"
        assert "Car deleted" in response_delete.json().get("message", ""), "Неверное сообщение при удалении"


@pytest.mark.regression
@pytest.mark.security
@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Negative - Unauthorized Access")
@allure.severity(allure.severity_level.CRITICAL)
@known_bug("NO_AUTH_403")
@allure.tag("REQ-SEC-01")
def test_api_add_car_unauthorized():
    api = IlCarroAPI()
    car_obj = CarGenerator.get_random_car()

    with allure.step("Попытка создать машину без токена авторизации"):
        response = api.add_car(car_obj.to_api_payload())

    with allure.step("Проверка: без токена сервер отвечает 401 Unauthorized"):
        assert response.status_code == 401, \
            f"Ожидался статус 401, но получен {response.status_code}"


@pytest.mark.smoke
@allure.epic("API Testing")
@allure.feature("Car Booking Flow")
@allure.story("Integration: Create -> Search -> Book -> Check bookedPeriods")
@allure.severity(allure.severity_level.BLOCKER)
@known_bug("BOOKING_NOT_PERSISTED")
@allure.tag("REQ-BOOK-01")
def test_api_car_booking_flow(auth_api, create_car, second_user):
    today = datetime.date.today()
    start_date = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    end_date = (today + datetime.timedelta(days=7)).strftime("%Y-%m-%d")

    # Машина — у temp_user (владелец), бронирует второй пользователь, как в исследовании Q-API-01
    car = create_car()
    booker = second_user.user

    # Всё, кроме сохранения брони, — предусловия: их сбой не должен прятаться за известным багом
    with allure.step(f"1. Ищем машины в городе {car.city} на заданные даты"):
        response_search = second_user.api.search_cars(car.city, start_date, end_date)
        require(response_search.status_code == 200, f"Ошибка поиска: {response_search.text}")
        serial_numbers_found = [found.get("serialNumber") for found in response_search.json().get("cars", [])]
        require(car.reg_number in serial_numbers_found, "Созданная машина не появилась в поиске!")

    with allure.step(f"2. Второй пользователь {booker.email} бронирует машину"):
        response_book = second_user.api.book_car(car.reg_number, start_date, end_date)
        require(response_book.status_code == 200, f"Бронирование не принято: {response_book.status_code} {response_book.text}")

    with allure.step("3. Состояние: в bookedPeriods машины владельца есть период бронирующего"):
        cars = my_cars(auth_api)
        require(car.reg_number in cars, f"Машины {car.reg_number} нет в /v1/cars/my владельца")
        booked_periods = cars[car.reg_number].get("bookedPeriods") or []
        expected_period = {"email": booker.email, "startDate": start_date, "endDate": end_date}
        assert any(
            {key: period.get(key) for key in expected_period} == expected_period for period in booked_periods
        ), f"Бронь не сохранилась: ожидали период {expected_period} в bookedPeriods, получили {booked_periods}"
