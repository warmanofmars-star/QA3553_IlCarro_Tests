import time
from pages.search_page import SearchPage


def test_search_form_basics(driver):
    search_page = SearchPage(driver)

    # Открываем нужную страницу
    search_page.open()

    # Проверяем, что кнопка Yalla! заблокирована до ввода данных
    assert search_page.is_submit_button_disabled() == True, "Кнопка Yalla! должна быть неактивна"

    # Вводим город
    search_page.fill_city("Haifa")
    time.sleep(1)  # Пауза для визуального контроля

    # Кликаем по датам для вызова календаря
    search_page.click_dates_input()
    time.sleep(2)  # Пауза для визуального контроля