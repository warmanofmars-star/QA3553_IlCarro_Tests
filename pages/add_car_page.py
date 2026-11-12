import os

import allure
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait

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

    SUBMIT_ERROR_MESSAGE = (By.CSS_SELECTOR, "div.error[role='alert']")
    PAGE_TITLE = (By.CSS_SELECTOR, "h1.title")

    # Поле формы по атрибуту name (имена — из формы LetCarWork: manufacture, model, year, fuel, seats, …)
    @staticmethod
    def field(name: str) -> tuple[str, str]:
        return By.NAME, name

    @staticmethod
    def field_error(name: str) -> tuple[str, str]:
        """Ошибка валидации поля: блок div.error сразу за полем (ErrorMessage Formik, FE: LetCarWork)."""
        return By.XPATH, f"//*[@name='{name}']/following-sibling::div[contains(@class, 'error')]"

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

    @allure.step("Заполнение всей формы допустимыми значениями (город — из подсказки)")
    def fill_valid_form(self, car):
        self.fill_city(car.city)
        self.fill_text_fields(car)
        self.fill_dropdowns(car)

    def replace_value(self, locator, value: str) -> None:
        """Замена значения поля через клавиатуру.

        WebElement.clear() меняет значение мимо обработчиков React: Formik не узнал бы, что поле
        опустело. Выделение всего текста и Backspace — обычный ввод, его React видит. CONTROL —
        для Windows и Linux (локальный запуск и узлы Grid).
        """
        with allure.step(f"Замена значения поля {locator} на {value!r}"):
            element = self.find(locator)
            element.send_keys(Keys.CONTROL, "a")
            element.send_keys(Keys.BACKSPACE)
            if value:
                element.send_keys(value)

    @allure.step("Выбор пустого варианта Fuel («Select fuel»)")
    def clear_fuel(self):
        Select(self.find(self.FUEL_SELECT)).select_by_value("")

    @allure.step("Снятие фокуса с поля: клик по заголовку страницы")
    def blur(self):
        # Клик по заголовку, а не по body: в середине длинной формы клик по body попал бы в другое поле
        self.click(self.PAGE_TITLE)

    @allure.step("Ожидание текста ошибки под полем {name}")
    def get_field_error_text(self, name: str) -> str | None:
        """Текст ошибки под полем или None, если ошибка не появилась (валидация Formik асинхронная)."""
        try:
            element = WebDriverWait(self.driver, self.DEFAULT_TIMEOUT).until(
                EC.visibility_of_element_located(self.field_error(name))
            )
        except TimeoutException:
            return None
        return element.text

    def _wait_submit_enabled(self, enabled: bool, timeout: float) -> bool:
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.find_element(*self.SUBMIT_BTN).is_enabled() == enabled
            )
            return True
        except TimeoutException:
            return False

    @allure.step("Ожидание: кнопка Submit доступна")
    def wait_submit_enabled(self) -> bool:
        return self._wait_submit_enabled(True, self.DEFAULT_TIMEOUT)

    @allure.step("Ожидание: кнопка Submit недоступна")
    def wait_submit_disabled(self, timeout: float = 5) -> bool:
        """True — кнопка стала недоступна за timeout; False — осталась доступной."""
        return self._wait_submit_enabled(False, timeout)

    @allure.step("Получение текста ошибки под формой")
    def get_submit_error_text(self):
        # Наш базовый get_text уже содержит умное ожидание,
        # так что он сам дождется, пока сервер ответит и React отрендерит эту надпись
        return self.get_text(self.SUBMIT_ERROR_MESSAGE)

    @allure.step("Проверка наличия скрытых ошибок валидации на форме")
    def get_form_errors(self):
        try:
            # Ждем до 3 секунд, пока в DOM не появится хотя бы один элемент с классом .error
            errors = WebDriverWait(self.driver, 3).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".error"))
            )
            return [err.text for err in errors if err.text != ""]
        except TimeoutException:
            # Если за 3 секунды ни одной ошибки не появилось — возвращаем пустой список
            return []

    @allure.step("Проверка сброса формы (ожидание успешного добавления)")
    def is_form_cleared(self) -> bool:
        # Просто просим базовый класс подождать, пока поле MAKE_INPUT станет пустым
        return self.is_input_cleared(self.MAKE_INPUT)
