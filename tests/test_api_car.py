import datetime
import uuid

import allure
import pytest
from jsonschema import validate
from jsonschema.exceptions import ValidationError

from api.car_api import IlCarroAPI
from data.data_generator import CarGenerator, SearchDataGenerator
from data.known_bugs import known_bug
from models.car import Car
from schemas.car_schemas import GET_CARS_RESPONSE_SCHEMA, MESSAGE_RESPONSE_SCHEMA
from utils.car_state import my_cars
from utils.preconditions import require

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
        assert car_obj.reg_number in my_cars(auth_api), (
            f"Машина {car_obj.reg_number} не сохранилась: её нет в /v1/cars/my. Ответ создания: "
            f"{response.status_code} {response.text}"
        )

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


def _create_car_for(member, role: str) -> Car:
    """Машина пользователя из user_pair; номер регистрируется в его очистке до запроса."""
    car = CarGenerator.get_random_car()
    member.cleanup.register(car.reg_number)
    with allure.step(f"Setup: {role} создаёт машину {car.reg_number}"):
        response = member.api.add_car(car.to_api_payload())
        require(response.status_code == 200, f"Машина ({role}) не создана: {response.status_code} {response.text}")
    member.cleanup.mark_created(car.reg_number)
    return car


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Unique serialNumber")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-CAR-05")
def test_api_car_duplicate_serial(user_pair):
    """serialNumber уникален во всей системе: повтор другим пользователем отклоняется с 400,
    исходная машина не меняется, у второго пользователя машина не появляется."""
    owner, second_user = user_pair
    car = _create_car_for(owner, "владелец")
    # Если повтор примут, машина с этим номером окажется у второго пользователя — её уберёт его очистка
    second_user.cleanup.register(car.reg_number)
    duplicate = CarGenerator.get_random_car(reg_number=car.reg_number, model=f"Dup{car.model}")

    with allure.step(f"Второй пользователь создаёт машину с тем же serialNumber {car.reg_number}"):
        response = second_user.api.add_car(duplicate.to_api_payload())

    with allure.step("Состояние: машина владельца не изменилась, у второго пользователя её нет"):
        owner_cars = my_cars(owner.api)
        require(car.reg_number in owner_cars, f"Машина {car.reg_number} пропала у владельца")
        assert owner_cars[car.reg_number].get("model") == car.model, (
            f"Повтор serialNumber перезаписал машину владельца: model={owner_cars[car.reg_number].get('model')!r}"
        )
        assert car.reg_number not in my_cars(second_user.api), (
            f"Машина с повторным serialNumber {car.reg_number} создана у второго пользователя"
        )

    with allure.step("Проверка: повтор отклонён с 400"):
        assert response.status_code == 400, (
            f"Повтор serialNumber: ожидали 400, получили {response.status_code} {response.text}"
        )


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Supported cities")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-CAR-06")
def test_api_car_unsupported_city(shared_api, shared_car_cleanup):
    # Город есть в подсказке фронтенда, но не в /v1/cars/cities (Q-API-03)
    city = "Acre"
    response_cities = shared_api.get_cities()
    require(response_cities.status_code == 200, f"Список городов недоступен: {response_cities.text}")
    api_cities = {item.get("city") for item in response_cities.json().get("cities", [])}
    require(city not in api_cities, f"Город {city} появился в /v1/cars/cities: нужен другой город не из списка")

    car = CarGenerator.get_random_car(city=city)
    shared_car_cleanup.register(car.reg_number)

    with allure.step(f"Создаём машину в городе {city}"):
        response = shared_api.add_car(car.to_api_payload())

    with allure.step("Состояние: машина не создана"):
        assert car.reg_number not in my_cars(shared_api), (
            f"Машина в городе не из списка сохранилась. Ответ: {response.status_code} {response.text}"
        )

    with allure.step("Проверка: 400"):
        assert response.status_code == 400, (
            f"Город {city} не из списка: ожидали 400, получили {response.status_code} {response.text}"
        )


@pytest.mark.regression
@pytest.mark.security
@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Get User cars")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-CAR-07")
def test_api_my_cars_only_own(user_pair):
    """У двух пользователей по машине: /v1/cars/my каждого отдаёт только его машины."""
    owner, second_user = user_pair
    own_car = _create_car_for(owner, "первый пользователь")
    other_car = _create_car_for(second_user, "второй пользователь")

    for title, api, email, mine, foreign in (
        ("первого пользователя", owner.api, owner.user.email, own_car, other_car),
        ("второго пользователя", second_user.api, second_user.user.email, other_car, own_car),
    ):
        with allure.step(f"Проверка: /v1/cars/my {title} — только его машины"):
            cars = my_cars(api)
            require(mine.reg_number in cars, f"Своей машины {mine.reg_number} нет в /v1/cars/my {title}")
            assert foreign.reg_number not in cars, f"В /v1/cars/my {title} чужая машина {foreign.reg_number}"
            foreign_owners = {serial: car.get("owner") for serial, car in cars.items() if car.get("owner") != email}
            assert not foreign_owners, f"В /v1/cars/my {title} машины других владельцев: {foreign_owners}"


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
        assert response.status_code == 401, f"Ожидался статус 401, но получен {response.status_code}"


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
        require(
            response_book.status_code == 200,
            f"Бронирование не принято: {response_book.status_code} {response_book.text}",
        )

    with allure.step("3. Состояние: в bookedPeriods машины владельца есть период бронирующего"):
        cars = my_cars(auth_api)
        require(car.reg_number in cars, f"Машины {car.reg_number} нет в /v1/cars/my владельца")
        booked_periods = cars[car.reg_number].get("bookedPeriods") or []
        expected_period = {"email": booker.email, "startDate": start_date, "endDate": end_date}
        assert any({key: period.get(key) for key in expected_period} == expected_period for period in booked_periods), (
            f"Бронь не сохранилась: ожидали период {expected_period} в bookedPeriods, получили {booked_periods}"
        )


def _missing_serial() -> str:
    """Номер машины, которой нет: префикс, как у генератора, и случайный хвост."""
    return f"IL-NOSUCH-{uuid.uuid4().hex[:8].upper()}"


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Car Booking Flow")
@allure.story("Booking a nonexistent car")
@allure.severity(allure.severity_level.NORMAL)
@known_bug("BOOKING_UNKNOWN_CAR_200")
@allure.tag("REQ-BOOK-02")
def test_api_book_nonexistent_car(shared_api):
    start_date, end_date = SearchDataGenerator.get_safe_future_dates()

    response = shared_api.book_car(_missing_serial(), start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

    with allure.step("Проверка: 404"):
        assert response.status_code == 404, (
            f"Бронирование несуществующей машины: ожидали 404, получили {response.status_code} {response.text}"
        )


@pytest.mark.regression
@pytest.mark.security
@allure.epic("API Testing")
@allure.feature("Car Booking Flow")
@allure.story("Negative - Unauthorized Access")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-BOOK-03")
def test_api_book_without_token():
    """Бронирование без токена отклоняется. Какой именно код — отдельное требование REQ-SEC-01
    (известный баг NO_AUTH_403), поэтому здесь принимаются оба кода отказа в авторизации."""
    api = IlCarroAPI()  # клиент без заголовка Authorization
    start_date, end_date = SearchDataGenerator.get_safe_future_dates()

    response = api.book_car(_missing_serial(), start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

    with allure.step("Проверка: запрос без токена отклонён (401 или 403)"):
        assert response.status_code in (401, 403), (
            f"Бронирование без токена: ожидали отказ 401/403, получили {response.status_code} {response.text}"
        )
