import allure
from pages.search_page import SearchPage
from data.data_generator import SearchDataGenerator


@allure.epic("UI Testing")
@allure.feature("Search Page")
@allure.story("Search Cars Dynamic Flow")
@allure.severity(allure.severity_level.CRITICAL)
def test_search_form_dynamic(driver):
    search_page = SearchPage(driver)

    city = SearchDataGenerator.get_random_city()
    start_date, end_date = SearchDataGenerator.get_safe_future_dates()

    # Формируем ожидаемую строку в формате M/D/YYYY - M/D/YYYY (как в UI)
    expected_dates_str = f"{start_date.month}/{start_date.day}/{start_date.year} - {end_date.month}/{end_date.day}/{end_date.year}"

    with allure.step(f"Тест с параметрами: Город - {city}, Ожидаемые даты в поле: {expected_dates_str}"):
        pass

    search_page.open()

    assert search_page.is_submit_button_disabled() == True, "Кнопка Yalla! должна быть неактивна в начале"

    search_page.fill_city(city)
    search_page.select_date_range(start_date, end_date)

    search_page.click(search_page.CITY_INPUT)  # закрываем календарь

    # --- НОВАЯ ПРОВЕРКА ФОРМАТА ДАТ ---
    actual_dates_str = search_page.get_selected_dates_value()
    assert actual_dates_str == expected_dates_str, f"Ошибка в поле дат! Ожидали '{expected_dates_str}', а получили '{actual_dates_str}'"

    assert search_page.is_submit_button_disabled() == False, "Кнопка Yalla! не разблокировалась после ввода данных!"