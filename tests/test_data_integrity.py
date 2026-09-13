import time
import pytest
from selenium.webdriver.common.by import By
import allure
from api.car_api import IlCarroAPI
from pages.search_page import SearchPage


@allure.epic("Data Integrity")
@allure.feature("Cities Dictionary")
@pytest.mark.xfail(reason="Критический баг UI: Захардкожено 8 городов вместо 37 из API")
@allure.title("Проверка синхронизации списка городов между API и UI")
def test_cities_sync_api_vs_ui(driver):
    api = IlCarroAPI()
    search_page = SearchPage(driver)

    with allure.step("1. Получаем эталонный список городов из API"):
        response = api.get_cities()
        assert response.status_code == 200, "API городов недоступно"

        # Собираем все названия в множество (set) для удобного сравнения
        api_cities = {city_obj["city"] for city_obj in response.json().get("cities", [])}
        print(f"\nГородов в API: {len(api_cities)}")

    with allure.step("2. Получаем список городов из выпадающего меню UI"):
        search_page.open()
        # Кликаем по пустому полю, чтобы React развернул список
        driver.find_element(By.ID, "city").click()

        # Даем слабенькому серверу GitHub (или локальному ПК) секунду на отрисовку списка.
        # Обычно мы используем WebDriverWait, но для скрипта-аудитора time.sleep() — это железобетонно.
        time.sleep(1)

        # Мы знаем из прошлых тестов, что города лежат в атрибуте data-testid='city-option'
        ui_elements = driver.find_elements(By.CSS_SELECTOR, "[data-testid='city-option']")
        ui_cities = {element.text for element in ui_elements if element.text}

        print(f"Городов в UI: {len(ui_cities)}")

    with allure.step("3. Сравниваем списки и выявляем баги"):
        # Находим города, которые есть в API, но отсутствуют в UI (или написаны иначе)
        missing_in_ui = api_cities - ui_cities

        # Находим города, которые есть в UI, но бэкенд о них не знает
        extra_in_ui = ui_cities - api_cities

        if missing_in_ui:
            print(f"\n[БАГ] В UI не хватает (или опечатка): {missing_in_ui}")

        if extra_in_ui:
            print(f"\n[БАГ] В UI лишние (или опечатка): {extra_in_ui}")

        # Тест должен упасть, если списки не идентичны
        assert api_cities == ui_cities, (
            f"Рассинхронизация словарей!\n"
            f"Потеряны в UI: {missing_in_ui}\n"
            f"Лишние в UI: {extra_in_ui}"
        )