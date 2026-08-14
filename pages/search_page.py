from selenium.webdriver.common.by import By

class SearchPage:
    CITY_INPUT = (By.ID, "city")
    DATES_INPUT = (By.ID, "dates")
    SUBMIT_BTN = (By.CSS_SELECTOR, "button[type='submit']")

    def __init__(self, driver):
        self.driver = driver

    # Метод для открытия конкретно страницы Search
    def open(self):
        self.driver.get("https://icarro-v1.netlify.app/search?page=0&size=10")

    def fill_city(self, city_name):
        city_field = self.driver.find_element(*self.CITY_INPUT)
        city_field.clear()
        city_field.send_keys(city_name)

    def click_dates_input(self):
        # Поле readonly, поэтому просто кликаем по нему
        self.driver.find_element(*self.DATES_INPUT).click()

    def is_submit_button_disabled(self):
        submit_btn = self.driver.find_element(*self.SUBMIT_BTN)
        return not submit_btn.is_enabled()