from datetime import date

import allure
import pytest

from pages.search_page import SearchPage
from utils.preconditions import require

pytestmark = [pytest.mark.ui, pytest.mark.regression]


@allure.epic("UI Testing")
@allure.feature("Calendar Component")
@allure.story("Calendar UI and Dismissal")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("REQ-UI-SEARCH-06")
def test_calendar_ui_and_close(driver):
    search_page = SearchPage(driver)
    search_page.open()

    search_page.click_dates_input()
    # СИНХРОНИЗАЦИЯ: ждем открытия попапа
    assert search_page.is_calendar_visible() is True, "Календарь не открылся!"

    assert search_page.is_today_highlighted() is True, "Сегодняшний день не выделен!"
    search_page.click(search_page.CITY_INPUT)
    assert search_page.is_calendar_invisible() is True, "Календарь не закрылся!"


@allure.epic("UI Testing")
@allure.feature("Calendar Component")
@allure.story("Negative Calendar UI - Past Dates Blocked")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-UI-SEARCH-02")
def test_calendar_past_navigation_blocked(driver):
    """
    Прошедшие дни выбрать нельзя (REQ-UI-SEARCH-02: minDate = сегодня).

    Проверяем состояние календаря, а не то, сменился ли месяц после клика «назад»: какой бы
    месяц ни был показан после попытки уйти в прошлое, каждый его день раньше сегодняшнего
    должен быть недоступен, а сегодняшний и последующие — доступны. Последнее делает проверку
    содержательной и 1-го числа, когда прошедших дней в текущем месяце нет.
    То, что кнопка «назад» ничего не делает, — отдельное наблюдение OBS-10, здесь не проверяется.
    """
    search_page = SearchPage(driver)
    search_page.open()
    search_page.click_dates_input()

    require(search_page.is_calendar_visible(), "Календарь не открылся!")

    with allure.step("Пытаемся уйти в прошлое кнопкой «предыдущий месяц»"):
        search_page.click_prev_month()

    today = date.today()
    days = search_page.get_displayed_days_availability()
    month_shown = min(days).strftime("%B %Y")

    with allure.step(f"Проверка: в показанном месяце ({month_shown}) дни раньше сегодняшнего недоступны"):
        past_available = sorted(str(day) for day, available in days.items() if day < today and available)
        assert not past_available, f"В календаре можно выбрать прошедшие дни: {past_available}"

    with allure.step("Проверка: сегодняшний и последующие дни месяца доступны"):
        # Верхняя граница (сегодня + 365 дней, REQ-UI-SEARCH-02) в показанном месяце не достижима
        future_blocked = sorted(str(day) for day, available in days.items() if day >= today and not available)
        assert not future_blocked, f"Недоступны дни, которые должны быть доступны: {future_blocked}"


@allure.epic("UI Testing")
@allure.feature("Calendar Component")
@allure.story("Calendar Navigation")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("REQ-UI-SEARCH-07")
def test_calendar_month_navigation(driver):
    search_page = SearchPage(driver)
    search_page.open()
    search_page.click_dates_input()

    require(search_page.is_calendar_visible(), "Календарь не открылся!")

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
