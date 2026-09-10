import os
import allure
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from pages.base_page import BasePage


class AddCarPage(BasePage):
    ENDPOINT = "/let-car-work"

    # --- ЛОКАТОРЫ ---
    CITY_INPUT = (By.ID, "city")
    MAKE_INPUT = (By.CSS_SELECTOR, "input[name='manufacture']")
    MODEL_INPUT = (By.CSS_SELECTOR, "input[name='model']")
    YEAR_INPUT = (By.CSS_SELECTOR, "input[name='year']")
    FUEL_SELECT = (By.CSS_SELECTOR, "select[name='fuel']")
    GEAR_SELECT = (By.CSS_SELECTOR, "select[name='gear']")
    WD_SELECT = (By.CSS_SELECTOR, "select[name='wheelsDrive']")
    DOORS_INPUT = (By.CSS_SELECTOR, "input[name='doors']")
    SEATS_INPUT = (By.CSS_SELECTOR, "input[name='seats']")
    CLASS_INPUT = (By.CSS_SELECTOR, "input[name='carClass']")
    REG_NUM_INPUT = (By.CSS_SELECTOR, "input[name='serialNumber']")
    PRICE_INPUT = (By.CSS_SELECTOR, "input[name='pricePerDay']")
    ABOUT_INPUT = (By.CSS_SELECTOR, "textarea[name='about']")
    PHOTO_INPUT = (By.ID, "photo-file")
    SUBMIT_BTN = (By.CSS_SELECTOR, "button[type='submit']")

    GLOBAL_MESSAGE = (By.CSS_SELECTOR, "h3")

    def open(self):
        self.open_url(self.ENDPOINT)

    @allure.step("Ввод города {city} с выбором из выпадающего списка")
    def fill_city(self, city):
        self.fill(self.CITY_INPUT, city)
        # Динамический локатор для опции в списке
        option_locator = (By.CSS_SELECTOR, f"[data-testid='city-option'][data-value='{city}']")
        self.click(option_locator)

    @allure.step("Заполнение текстовых полей автомобиля")
    def fill_text_fields(self, car):
        self.fill(self.MAKE_INPUT, car.make)
        self.fill(self.MODEL_INPUT, car.model)
        self.fill(self.YEAR_INPUT, car.year)
        self.fill(self.DOORS_INPUT, car.doors)
        self.fill(self.SEATS_INPUT, car.seats)
        self.fill(self.CLASS_INPUT, car.car_class)
        self.fill(self.REG_NUM_INPUT, car.reg_number)
        self.fill(self.PRICE_INPUT, car.price)
        self.fill(self.ABOUT_INPUT, car.about)

    @allure.step("Выбор опций в выпадающих списках")
    def fill_dropdowns(self, car):
        Select(self.find(self.FUEL_SELECT)).select_by_visible_text(car.fuel)
        Select(self.find(self.GEAR_SELECT)).select_by_visible_text(car.gear)
        Select(self.find(self.WD_SELECT)).select_by_visible_text(car.wd)

    @allure.step("Загрузка фотографии автомобиля")
    def upload_photo(self, file_path):
        if file_path:
            absolute_path = os.path.abspath(file_path)
            self.find(self.PHOTO_INPUT).send_keys(absolute_path)

    @allure.step("Отправка формы добавления автомобиля")
    def submit(self):
        self.click(self.SUBMIT_BTN)

    @allure.step("Получение текста из модального окна")
    def get_global_message_text(self):
        return self.get_text(self.GLOBAL_MESSAGE)

    @allure.step("Проверка наличия скрытых ошибок валидации на форме")
    def get_form_errors(self):
        # Ищем все элементы с классом error и возвращаем их текст
        errors = self.driver.find_elements(By.CSS_SELECTOR, ".error")
        return [err.text for err in errors if err.text != ""]