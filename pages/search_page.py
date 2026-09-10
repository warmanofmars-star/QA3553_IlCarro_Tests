import allure
from selenium.webdriver.support.wait import WebDriverWait
from datetime import datetime
from selenium.webdriver.common.by import By
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
    TODAY_DAY_MARKER = (By.CSS_SELECTOR, ".rdrDayToday")

    # Кнопка переключения месяца вперед в календаре react-date-range
    NEXT_MONTH_BTN = (By.CSS_SELECTOR, ".rdrNextButton")


    # --- ДЕЙСТВИЯ ---:
    @staticmethod
    def get_day_locator(day):
        xpath = f"//button[contains(@class, 'rdrDay') and not(contains(@class, 'rdrDayPassive')) and not(contains(@class, 'rdrDayDisabled')) and .//*[text()='{day}']]"
        return (By.XPATH, xpath)

    def open(self):
        self.open_url(self.ENDPOINT)

    def fill_city(self, city_name):
        self.fill(self.CITY_INPUT, city_name)

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

        # Умная логика: если месяц начала поездки больше текущего, перелистываем календарь
        current_month = datetime.now().month
        target_month = start_date.month

        # Вычисляем, сколько раз нужно нажать "вперед"
        months_diff = target_month - current_month
        if months_diff > 0:
            for _ in range(months_diff):
                self.click_next_month()

        # Кликаем по дням
        self.click(self.get_day_locator(start_date.day))
        self.click(self.get_day_locator(end_date.day))

    @allure.step("Ожидание смены месяца (завершение анимации)")
    def wait_for_month_to_change(self, old_month):
        # Умный вейт: ждем максимум 3 секунды, пока текст месяца перестанет быть равен old_month
        WebDriverWait(self.driver, 3).until(
            lambda driver: self.get_current_month() != old_month,
            message=f"Месяц так и не изменился после клика! Ожидали, что он перестанет быть '{old_month}'"
        )

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