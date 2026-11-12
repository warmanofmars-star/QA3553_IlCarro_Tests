import contextlib
from datetime import date, datetime

import allure
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait

from pages.base_page import BasePage


class SearchPage(BasePage):
    ENDPOINT = "/search?page=0&size=10"

    # --- СТАТИЧНЫЕ ЛОКАТОРЫ ---:
    CITY_INPUT = (By.ID, "city")
    DATES_INPUT = (By.ID, "dates")
    SUBMIT_BTN = (By.CSS_SELECTOR, "button[type='submit']")
    CALENDAR_POPOVER = (By.CSS_SELECTOR, ".daterange-popover")
    PREV_MONTH_BTN = (By.CSS_SELECTOR, ".rdrPprevButton")
    ACTIVE_MONTH_LABEL = (By.CSS_SELECTOR, ".rdrMonthPicker option:checked")
    ACTIVE_YEAR_LABEL = (By.CSS_SELECTOR, ".rdrYearPicker option:checked")
    # Дни показанного месяца; «пассивные» — хвосты соседних месяцев в сетке, их не берём
    MONTH_DAY_CELLS = (By.CSS_SELECTOR, "button.rdrDay:not(.rdrDayPassive)")
    TODAY_DAY_MARKER = (By.CSS_SELECTOR, ".rdrDayToday")

    # Кнопка переключения месяца вперед в календаре react-date-range
    NEXT_MONTH_BTN = (By.CSS_SELECTOR, ".rdrNextButton")

    # Подсказка города (FE: CityAutocomplete)
    CITY_DROPDOWN = (By.CSS_SELECTOR, "[data-testid='city-dropdown']")
    CITY_OPTIONS = (By.CSS_SELECTOR, "[data-testid='city-option']")

    # --- ДЕЙСТВИЯ ---:
    @staticmethod
    def get_day_locator(day):
        xpath = (
            "//button[contains(@class, 'rdrDay') and not(contains(@class, 'rdrDayPassive')) and "
            f"not(contains(@class, 'rdrDayDisabled')) and .//*[text()='{day}']]"
        )
        return By.XPATH, xpath

    def open(self):
        self.open_url(self.ENDPOINT)

    @allure.step("Ввод города {city_name} с выбором из динамического списка")
    def fill_city(self, city_name):
        self.fill(self.CITY_INPUT, city_name)
        # Ждем, пока React отфильтрует нужный город, и кликаем по нему
        option_locator = (By.CSS_SELECTOR, f"[data-testid='city-option'][data-value='{city_name}']")
        self.click(option_locator)

    @allure.step("Ввод города {text} вручную, без выбора из подсказки")
    def type_city(self, text: str):
        self.fill(self.CITY_INPUT, text)

    @allure.step("Закрытие подсказки города: фокус уходит клавишей Tab")
    def leave_city_input(self):
        # Tab, а не клик мимо: подсказка выбирает город по mousedown, клик мог бы попасть в вариант
        self.find(self.CITY_INPUT).send_keys(Keys.TAB)
        WebDriverWait(self.driver, self.DEFAULT_TIMEOUT).until(
            lambda d: not d.find_elements(*self.CITY_DROPDOWN), message="Подсказка города не закрылась"
        )

    @allure.step("Ожидание вариантов подсказки города")
    def wait_city_suggestions(self, expected: list[str], timeout: float = 5) -> list[str]:
        """Варианты подсказки, когда они совпали с expected, или последние прочитанные, если не совпали.

        Список перерисовывается на каждый символ ввода: ждём ожидаемого состояния, а сравнение
        оставляем тесту, чтобы сообщение о провале показало, что было на экране.
        """
        actual: list[str] = []

        def read(driver):
            nonlocal actual
            actual = [option.text for option in driver.find_elements(*self.CITY_OPTIONS)]
            return actual == expected

        # Несовпадение — не ошибка ожидания: его покажет сравнение в тесте
        with contextlib.suppress(TimeoutException):
            WebDriverWait(self.driver, timeout, ignored_exceptions=(StaleElementReferenceException,)).until(read)
        return actual

    def click_dates_input(self):
        self.click(self.DATES_INPUT)

    @allure.step("Клик по кнопке 'Следующий месяц' в календаре")
    def click_next_month(self):
        self.click(self.NEXT_MONTH_BTN)

    @allure.step("Клик по кнопке 'Предыдущий месяц' в календаре")
    def click_prev_month(self):
        self.click(self.PREV_MONTH_BTN)

    @allure.step("Получение текущего отображаемого месяца")
    def get_current_month(self):
        return self.get_text(self.ACTIVE_MONTH_LABEL)

    @allure.step("Выбор дат поездки: с {start_date} по {end_date}")
    def select_date_range(self, start_date, end_date):
        self.click_dates_input()

        now = datetime.now()

        # --- 1. ПЕРЕХОД К МЕСЯЦУ НАЧАЛА ПОЕЗДКИ (с учетом смены года Декабрь -> Январь) ---
        start_months_diff = (start_date.year - now.year) * 12 + (start_date.month - now.month)
        if start_months_diff > 0:
            for _ in range(start_months_diff):
                self.click_next_month()

        # Кликаем дату начала
        self.click(self.get_day_locator(start_date.day))

        # --- 2. ПЕРЕХОД К МЕСЯЦУ КОНЦА ПОЕЗДКИ (с учетом смены года) ---
        end_months_diff = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        if end_months_diff > 0:
            for _ in range(end_months_diff):
                self.click_next_month()

        # Теперь безопасно кликаем дату конца, так как нужный месяц 100% на экране
        self.click(self.get_day_locator(end_date.day))

    @allure.step("Листание календаря вперёд до месяца даты {target}")
    def go_to_month(self, target: date):
        """Кнопкой «следующий месяц» до месяца target, дожидаясь смены месяца после каждого клика."""
        today = date.today()
        for _ in range((target.year - today.year) * 12 + target.month - today.month):
            shown = self.get_current_month()
            self.click_next_month()
            self.wait_for_month_to_change(shown)

    @allure.step("Ожидание смены месяца (завершение анимации)")
    def wait_for_month_to_change(self, old_month):
        # Умный вейт: ждем максимум 3 секунды, пока текст месяца перестанет быть равен old_month
        WebDriverWait(self.driver, 3).until(
            lambda driver: self.get_current_month() != old_month,
            message=f"Месяц так и не изменился после клика! Ожидали, что он перестанет быть '{old_month}'",
        )

    @allure.step("Чтение доступности дней показанного месяца календаря")
    def get_displayed_days_availability(self) -> dict[date, bool]:
        """{дата: доступна ли для выбора} для всех дней месяца, который сейчас показан.

        Недоступный день react-date-range помечает классом rdrDayDisabled. Месяц и год читаем
        до и после дней: снимок принимается, только если за это время календарь не перерисовался.
        """

        def read_month(driver):
            month = driver.find_element(*self.ACTIVE_MONTH_LABEL).text
            year = driver.find_element(*self.ACTIVE_YEAR_LABEL).text
            return month, year

        def snapshot(driver):
            before = read_month(driver)
            cells = [
                (int(cell.text), "rdrDayDisabled" not in (cell.get_attribute("class") or ""))
                for cell in driver.find_elements(*self.MONTH_DAY_CELLS)
            ]
            if not cells or read_month(driver) != before:
                return False
            return before, cells

        (month_name, year), cells = WebDriverWait(
            self.driver, 5, ignored_exceptions=(StaleElementReferenceException, NoSuchElementException)
        ).until(
            snapshot, message="Не удалось прочитать дни календаря: он не отрисовался или постоянно перерисовывается"
        )

        month = datetime.strptime(month_name, "%B").month
        return {date(int(year), month, day): available for day, available in cells}

    @allure.step("Клик по кнопке Y'alla! (Submit)")
    def click_submit_button(self):
        self.click(self.SUBMIT_BTN)

    # --- ПРОВЕРКИ ---:
    def is_submit_button_disabled(self):
        return self.is_element_disabled(self.SUBMIT_BTN)

    def is_calendar_visible(self):
        return self.is_element_visible(self.CALENDAR_POPOVER)

    def is_calendar_invisible(self):
        return self.is_element_invisible(self.CALENDAR_POPOVER)

    @allure.step("Проверка: кнопка «предыдущий месяц» недоступна")
    def is_prev_month_disabled(self) -> bool:
        return not self.find(self.PREV_MONTH_BTN).is_enabled()

    @allure.step("Проверка наличия маркера сегодняшнего дня (голубая полоса)")
    def is_today_highlighted(self):
        return self.is_element_visible(self.TODAY_DAY_MARKER)

    @allure.step("Получение текста из поля дат")
    def get_selected_dates_value(self):
        # Используем get_attribute("value"), так как это тег <input>
        element = self.find(self.DATES_INPUT)
        return element.get_attribute("value")

    @allure.step("Проверка, что ручный ввод в поле дат заблокирован (readonly)")
    def is_dates_input_readonly(self):
        element = self.find(self.DATES_INPUT)
        # Если у инпута есть атрибут readonly, он вернет "true" или пустую строку, иначе None
        return element.get_attribute("readonly") is not None
