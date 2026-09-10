import os
import allure
import datetime

import pytest

from api.car_api import IlCarroAPI
from data.data_generator import CarGenerator

VALID_EMAIL = os.getenv("USER_EMAIL")
VALID_PASSWORD = os.getenv("USER_PASSWORD")


@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Create Car successfully")
@allure.severity(allure.severity_level.BLOCKER)
def test_api_add_car_success():
    api = IlCarroAPI()

    with allure.step("1. Логин и получение токена"):
        login_response = api.login(VALID_EMAIL, VALID_PASSWORD)
        assert login_response.status_code == 200, f"Ошибка логина: {login_response.text}"
        assert api.token is not None, "Токен не сохранился!"

    with allure.step("2. Подготовка валидного JSON (CarDto)"):
        car_obj = CarGenerator.get_random_car()

        # Строго по Swagger! Преобразуем типы, чтобы бэкенд не выдал 400 Bad Request
        car_payload = {
            "serialNumber": car_obj.reg_number,
            "manufacture": car_obj.make,
            "model": car_obj.model,
            "year": str(car_obj.year),
            "fuel": car_obj.fuel,
            "seats": int(car_obj.seats),
            "carClass": car_obj.car_class,
            "pricePerDay": float(car_obj.price),
            "about": car_obj.about,
            "city": car_obj.city
        }

    with allure.step("3. Отправка POST запроса на создание машины"):
        response = api.add_car(car_payload)

    with allure.step("4. Проверка статус-кода и сообщения"):
        # Если бэкенд падает из-за бага, мы увидим статус 500 и сообщение прямо в консоли!
        assert response.status_code == 200, f"Бэкенд вернул ошибку: {response.status_code} - {response.text}"
        assert "Car added" in response.json().get("message", ""), "Неверное сообщение от сервера"


@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Full Lifecycle (Create -> Read -> Delete)")
@allure.severity(allure.severity_level.CRITICAL)
def test_api_car_lifecycle():
    api = IlCarroAPI()
    api.login(VALID_EMAIL, VALID_PASSWORD)

    # 1. Генерируем и создаем машину
    car_obj = CarGenerator.get_random_car()
    serial_number = car_obj.reg_number

    car_payload = {
        "serialNumber": serial_number,
        "manufacture": car_obj.make,
        "model": car_obj.model,
        "year": str(car_obj.year),
        "fuel": car_obj.fuel,
        "seats": int(car_obj.seats),
        "carClass": car_obj.car_class,
        "pricePerDay": float(car_obj.price),
        "about": car_obj.about,
        "city": car_obj.city
    }

    with allure.step("1. Создаем машину"):
        response_add = api.add_car(car_payload)
        # Теперь, если сервер откажет, мы точно увидим причину!
        assert response_add.status_code == 200, f"Не удалось создать машину! Ответ сервера: {response_add.text}"

    with allure.step("2. Проверяем, что машина появилась в списке 'My Cars'"):
        response_get = api.get_my_cars()
        assert response_get.status_code == 200, "Ошибка получения списка машин"

        # Парсим JSON и вытаскиваем список всех серийных номеров
        cars_list = response_get.json().get("cars", [])
        serial_numbers_in_db = [car.get("serialNumber") for car in cars_list]

        assert serial_number in serial_numbers_in_db, f"Машина с номером {serial_number} не найдена в базе!"

    with allure.step("3. Удаляем созданную машину"):
        response_delete = api.delete_car(serial_number)
        assert response_delete.status_code == 200, "Ошибка при удалении машины"
        assert "Car deleted" in response_delete.json().get("message", ""), "Неверное сообщение при удалении"

    with allure.step("4. Убеждаемся, что машина исчезла из базы"):
        response_get_after = api.get_my_cars()
        cars_list_after = response_get_after.json().get("cars", [])
        serial_numbers_after = [car.get("serialNumber") for car in cars_list_after]

        assert serial_number not in serial_numbers_after, "Машина не удалилась из базы!"


@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Negative - Unauthorized Access")
@allure.severity(allure.severity_level.CRITICAL)
def test_api_add_car_unauthorized():
    # Создаем клиента, НО НЕ ВЫЗЫВАЕМ api.login()
    api = IlCarroAPI()

    car_obj = CarGenerator.get_random_car()
    car_payload = {
        "serialNumber": car_obj.reg_number,
        "manufacture": car_obj.make,
        "model": car_obj.model,
        "year": str(car_obj.year),
        "fuel": car_obj.fuel,
        "seats": int(car_obj.seats),
        "carClass": car_obj.car_class,
        "pricePerDay": float(car_obj.price),
        "city": car_obj.city
    }

    with allure.step("Попытка создать машину без токена авторизации"):
        response = api.add_car(car_payload)

    with allure.step("Проверка статуса 401 Unauthorized"):
        assert response.status_code == 401, f"Ожидался статус 401, но получен {response.status_code}"


@allure.epic("API Testing")
@allure.feature("Car Booking Flow")
@allure.story("Integration: Create -> Search -> Book -> Delete")
@allure.severity(allure.severity_level.BLOCKER)
def test_api_car_booking_flow():
    api = IlCarroAPI()
    api.login(VALID_EMAIL, VALID_PASSWORD)

    # Подготовка дат (завтра и через 7 дней)
    today = datetime.date.today()
    start_date = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    end_date = (today + datetime.timedelta(days=7)).strftime("%Y-%m-%d")

    # Генерируем данные для новой машины
    car_obj = CarGenerator.get_random_car()
    serial_number = car_obj.reg_number
    target_city = car_obj.city

    car_payload = {
        "serialNumber": serial_number,
        "manufacture": car_obj.make,
        "model": car_obj.model,
        "year": str(car_obj.year),
        "fuel": car_obj.fuel,
        "seats": int(car_obj.seats),
        "carClass": car_obj.car_class,
        "pricePerDay": float(car_obj.price),
        "about": car_obj.about,
        "city": target_city
    }

    with allure.step("1. Создаем машину для бронирования"):
        response_add = api.add_car(car_payload)
        assert response_add.status_code == 200, f"Не удалось создать машину: {response_add.text}"

    with allure.step(f"2. Ищем машины в городе {target_city} на заданные даты"):
        response_search = api.search_cars(target_city, start_date, end_date)
        assert response_search.status_code == 200, f"Ошибка поиска: {response_search.text}"

        # Убеждаемся, что наша машина попала в поисковую выдачу
        cars_found = response_search.json().get("cars", [])
        serial_numbers_found = [car.get("serialNumber") for car in cars_found]
        assert serial_number in serial_numbers_found, "Созданная машина не появилась в поиске!"

    with allure.step("3. Бронируем найденную машину"):
        response_book = api.book_car(serial_number, start_date, end_date)
        assert response_book.status_code == 200, f"Ошибка бронирования: {response_book.text}"
        # Проверяем успешное сообщение, которое обычно возвращает сервер
        assert "successful" in response_book.json().get("message",
                                                        "").lower(), "Сообщение о бронировании не содержит подтверждения"

    with allure.step("4. Убираем за собой (удаляем машину)"):
        # Удаляем машину, чтобы не засорять базу
        api.delete_car(serial_number)


@allure.epic("API Testing")
@allure.feature("Maintenance")
@allure.story("Clean up all cars")
def test_clear_my_garage():
    api = IlCarroAPI()
    api.login(VALID_EMAIL, VALID_PASSWORD)

    response = api.get_my_cars()
    cars = response.json().get("cars", [])

    if not cars:
        print("\nГараж уже пуст!")
        return

    for car in cars:
        serial = car.get("serialNumber")
        api.delete_car(serial)
        print(f"\nУдалена машина: {serial}")

    # Проверяем, что всё удалилось
    assert len(api.get_my_cars().json().get("cars", [])) == 0, "Не удалось удалить все машины!"


@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Bug #404: Spelling mismatch for Beer Sheva")
@pytest.mark.xfail(reason="Баг интеграции: UI отправляет 'Beersheba', а бэкенд ждет 'Beer Sheva'")
def test_api_add_car_beersheba_bug():
    api = IlCarroAPI()
    api.login(VALID_EMAIL, VALID_PASSWORD)

    # Жестко задаем проблемный город
    car_obj = CarGenerator.get_random_car(city="Beersheba")
    car_payload = {
        "serialNumber": car_obj.reg_number,
        "manufacture": car_obj.make,
        "model": car_obj.model,
        "year": str(car_obj.year),
        "fuel": car_obj.fuel,
        "seats": int(car_obj.seats),
        "carClass": car_obj.car_class,
        "pricePerDay": float(car_obj.price),
        "about": car_obj.about,
        "city": car_obj.city
    }

    response = api.add_car(car_payload)
    # Ожидаем, что когда баг починят, сервер вернет 200
    assert response.status_code == 200, f"Баг всё еще актуален: {response.text}"