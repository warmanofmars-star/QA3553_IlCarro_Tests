import allure
from pages.search_page import SearchPage


@allure.epic("UI Testing")
@allure.feature("Calendar Component")
@allure.story("Calendar UI and Dismissal")
@allure.severity(allure.severity_level.NORMAL)
def test_calendar_ui_and_close(driver):
    search_page = SearchPage(driver)
    search_page.open()

    search_page.click_dates_input()
    # СИНХРОНИЗАЦИЯ: ждем открытия попапа
    assert search_page.is_calendar_visible() == True, "Календарь не открылся!"

    assert search_page.is_today_highlighted() == True, "Сегодняшний день не выделен!"
    search_page.click(search_page.CITY_INPUT)
    assert search_page.is_calendar_invisible() == True, "Календарь не закрылся!"


@allure.epic("UI Testing")
@allure.feature("Calendar Component")
@allure.story("Negative Calendar UI - Past Dates Blocked")
@allure.severity(allure.severity_level.CRITICAL)
def test_calendar_past_navigation_blocked(driver):
    search_page = SearchPage(driver)
    search_page.open()
    search_page.click_dates_input()

    assert search_page.is_calendar_visible() == True, "Календарь не открылся!"

    # 1. Запоминаем текущий месяц
    initial_month = search_page.get_current_month()

    # 2. ПЫТАЕМСЯ кликнуть "Назад" (в прошлое)
    search_page.click_prev_month()

    # 3. Проверяем, что месяц никуда не переключился и мы остались в настоящем
    current_month = search_page.get_current_month()
    assert initial_month == current_month, f"Баг безопасности! Мы смогли уйти в прошлое: из {initial_month} в {current_month}"


@allure.epic("UI Testing")
@allure.feature("Calendar Component")
@allure.story("Calendar Navigation")
@allure.severity(allure.severity_level.NORMAL)
def test_calendar_month_navigation(driver):
    search_page = SearchPage(driver)
    search_page.open()
    search_page.click_dates_input()

    assert search_page.is_calendar_visible() == True, "Календарь не открылся!"

    initial_month = search_page.get_current_month()

    # 1. Листаем вперед
    search_page.click_next_month()
    # ПРОФЕССИОНАЛЬНОЕ ОЖИДАНИЕ: тест пойдет дальше сразу, как только сменится текст
    search_page.wait_for_month_to_change(initial_month)

    next_month = search_page.get_current_month()
    assert initial_month != next_month, f"Месяц не изменился! Остался: {initial_month}"

    # 2. Листаем назад
    search_page.click_prev_month()
    search_page.wait_for_month_to_change(next_month)

    returned_month = search_page.get_current_month()
    assert initial_month == returned_month, f"Не вернулись! Ожидали {initial_month}, получили {returned_month}"