from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


class SearchPage:
    # --- ЛОКАТОРЫ ---
    CITY_INPUT = (By.ID, "city")
    DATES_INPUT = (By.ID, "dates")
    SUBMIT_BTN = (By.CSS_SELECTOR, "button[type='submit']")

    # Новый локатор для всплывающего календаря
    CALENDAR_POPOVER = (By.CSS_SELECTOR, ".daterange-popover")

    def __init__(self, driver):
        self.driver = driver

    # --- ДЕЙСТВИЯ ---
    def open(self):
        self.driver.get("https://icarro-v1.netlify.app/search?page=0&size=10")

    def fill_city(self, city_name):
        city_field = self.driver.find_element(*self.CITY_INPUT)
        city_field.clear()
        city_field.send_keys(city_name)

    def click_dates_input(self):
        self.driver.find_element(*self.DATES_INPUT).click()

    # --- ПРОВЕРКИ ---
    def is_submit_button_disabled(self):
        submit_btn = self.driver.find_element(*self.SUBMIT_BTN)
        return not submit_btn.is_enabled()

    # Умное ожидание для календаря
    def is_calendar_visible(self):
        try:
            WebDriverWait(self.driver, timeout=5).until(
                EC.visibility_of_element_located(self.CALENDAR_POPOVER)
            )
            return True
        except TimeoutException:
            return False