import allure
from playwright.sync_api import Page, expect
from pages.pw_base_page import PwBasePage


class PwAddCarPage(PwBasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.endpoint = "/let-car-work"

        # --- ЛОКАТОРЫ ---
        self.city_input = page.locator("id=city")
        self.city_option = page.locator("[data-testid='city-option']").first

        self.make_input = page.locator("input[name='manufacture']")
        self.model_input = page.locator("input[name='model']")
        self.year_input = page.locator("input[name='year']")
        self.doors_input = page.locator("input[name='doors']")
        self.seats_input = page.locator("input[name='seats']")
        self.class_input = page.locator("input[name='carClass']")

        self.fuel_select = page.locator("select[name='fuel']")
        self.gear_select = page.locator("select[name='gear']")
        self.wd_select = page.locator("select[name='wheelsDrive']")

        self.serial_input = page.locator("input[name='serialNumber']")
        self.price_input = page.locator("input[name='pricePerDay']")
        self.about_input = page.locator("textarea[name='about']")

        self.submit_btn = page.locator("button[type='submit']")

    # --- ДЕЙСТВИЯ ---
    @allure.step("Открытие страницы добавления машины")
    def open(self):
        self.open_url(self.endpoint)

    @allure.step("Заполнение формы добавления машины")
    def fill_form(self, car):
        self.city_input.fill(car.city)

        # В Playwright можно сделать динамический локатор прямо на лету:
        self.page.locator(f"[data-testid='city-option'][data-value='{car.city}']").click()

        self.make_input.fill(car.make)
        self.model_input.fill(car.model)
        self.year_input.fill(str(car.year))
        self.doors_input.fill(str(car.doors))
        self.seats_input.fill(str(car.seats))
        self.class_input.fill(car.car_class)

        self.fuel_select.select_option(car.fuel)
        self.gear_select.select_option(car.gear)
        self.wd_select.select_option(car.wd)

        self.serial_input.fill(car.reg_number)
        self.price_input.fill(str(car.price))
        self.about_input.fill(car.about)

    @allure.step("Отправка формы")
    def submit(self):
        self.submit_btn.click()

    # --- ПРОВЕРКИ ---
    @allure.step("Проверка сброса формы (успешное добавление в БД)")
    def check_form_cleared(self):
        # Если поле очистилось, значит React принял ответ 200 OK от реального сервера
        expect(self.make_input).to_be_empty(timeout=8000)