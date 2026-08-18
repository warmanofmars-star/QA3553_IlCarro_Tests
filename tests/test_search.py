from pages.search_page import SearchPage

# Тестовые данные выносим в константы
VALID_CITY = "Haifa"


def test_search_form_basics(driver):
    search_page = SearchPage(driver)

    # 1. Открываем страницу поиска
    search_page.open()

    # 2. Убеждаемся, что кнопка заблокирована
    assert search_page.is_submit_button_disabled() == True, "Кнопка Yalla! должна быть неактивна в начале"

    # 3. Выполняем действия через новый комплексный метод
    search_page.search_cars(VALID_CITY)

    # 4. Проверяем, что календарь открылся (используется умное ожидание)
    assert search_page.is_calendar_visible() == True, "Календарь не открылся после клика по полю дат!"