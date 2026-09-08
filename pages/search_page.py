from selenium.webdriver.common.by import By
from pages.base_page import BasePage


class SearchPage(BasePage):
    ENDPOINT = "/search?page=0&size=10"

    # --- ЛОКАТОРЫ ---
    CITY_INPUT = (By.ID, "city")
    DATES_INPUT = (By.ID, "dates")
    SUBMIT_BTN = (By.CSS_SELECTOR, "button[type='submit']")
    CALENDAR_POPOVER = (By.CSS_SELECTOR, ".daterange-popover")

    # --- ДЕЙСТВИЯ ---
    def open(self):
        self.open_url(self.ENDPOINT)

    def fill_city(self, city_name):
        self.fill(self.CITY_INPUT, city_name)

    def click_dates_input(self):
        self.click(self.DATES_INPUT)

    def search_cars(self, city_name):
        self.fill_city(city_name)
        self.click_dates_input()

    # --- ПРОВЕРКИ ---
    def is_submit_button_disabled(self):
        return self.is_element_disabled(self.SUBMIT_BTN)

    def is_calendar_visible(self):
        return self.is_element_visible(self.CALENDAR_POPOVER)
