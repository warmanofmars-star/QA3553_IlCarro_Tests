import os
import allure
import pytest

from api.car_api import IlCarroAPI
from data.data_generator import CarGenerator, SearchDataGenerator
from pages.search_page import SearchPage
from pages.results_page import ResultsPage

VALID_EMAIL = os.getenv("USER_EMAIL")
VALID_PASSWORD = os.getenv("USER_PASSWORD")


@allure.epic("Hybrid Testing")
@allure.feature("Search functionality")
@allure.story("API Setup -> UI Search -> API Teardown")
@allure.severity(allure.severity_level.BLOCKER)
def test_hybrid_car_search(driver):
    # Инициализируем API клиент и логинимся для получения токена
    api = IlCarroAPI()
    api.login(VALID_EMAIL, VALID_PASSWORD)

    # --- ШАГ 1: API (Подготовка данных) ---
    with allure.step("API: Подготовка тестовых данных (создание машины)"):
        target_city = SearchDataGenerator.get_random_city()
        car_obj = CarGenerator.get_random_car(city=target_city)
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

        response = api.add_car(car_payload)
        assert response.status_code == 200, f"Ошибка пререквизита: API не смог создать машину. Ответ: {response.text}"

    # Оборачиваем UI-логику в try..finally, чтобы машина удалилась даже если Селениум упадет
    try:
        # --- ШАГ 2: UI (Поиск через браузер) ---
        search_page = SearchPage(driver)
        results_page = ResultsPage(driver)

        with allure.step(f"UI: Поиск машины в городе {target_city}"):
            search_page.open()
            search_page.fill_city(target_city)

            # Используем генератор для безопасных дат
            start_date, end_date = SearchDataGenerator.get_safe_future_dates()
            search_page.select_date_range(start_date, end_date)

            # Снимаем фокус с календаря, как в test_search_form_dynamic
            search_page.click(search_page.CITY_INPUT)
            search_page.click_submit_button()

        # --- ШАГ 3: UI (Проверка результатов) ---
        with allure.step("UI: Проверка отображения результатов поиска"):
            results_page.wait_for_search_request_to_complete()

            assert results_page.has_cars() == True, f"Машины в городе {target_city} не найдены, хотя API успешно создал авто!"

            # Дополнительно считываем детали первой машины, чтобы убедиться, что рендер карточек не сломан
            first_car = results_page.get_first_car_details()
            assert "title" in first_car, "Не удалось получить заголовок карточки автомобиля"
            assert "price" in first_car, "Не удалось получить цену автомобиля"

    finally:
        # --- ШАГ 4: API (Очистка базы данных) ---
        with allure.step(f"API (Teardown): Удаление тестовой машины {serial_number}"):
            api.delete_car(serial_number)