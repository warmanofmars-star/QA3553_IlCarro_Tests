from pages.search_page import SearchPage


def test_search_form_basics(driver):
    search_page = SearchPage(driver)

    # 1. Открываем страницу
    search_page.open()

    # 2. Проверяем, что кнопка Yalla! заблокирована до ввода данных
    assert search_page.is_submit_button_disabled() == True, "Кнопка Yalla! должна быть неактивна в начале"

    # 3. Вводим город
    search_page.fill_city("Haifa")

    # 4. Кликаем по полю дат для вызова календаря
    search_page.click_dates_input()

    # 5. ФИНАЛЬНАЯ ПРОВЕРКА: ждем и убеждаемся, что календарь действительно появился
    assert search_page.is_calendar_visible() == True, "Календарь не открылся после клика по полю дат!"