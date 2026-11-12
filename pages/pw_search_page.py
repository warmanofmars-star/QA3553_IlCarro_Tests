import allure
from playwright.sync_api import Page

from pages.pw_base_page import PwBasePage


class PwSearchPage(PwBasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.endpoint = "/search"

        self.city_input = page.locator("#city")
        self.dates_input = page.locator("#dates")
        self.today = page.locator(".rdrDayToday")
        self.submit_btn = page.locator("button[type='submit']")
        self.cards = page.locator("a.car-container")  # карточка — ссылка на /cars/{serialNumber}

    def open(self):
        self.open_url(self.endpoint)

    @allure.step("Поиск: город {city}, даты — сегодняшний день")
    def search_today(self, city: str):
        self.city_input.fill(city)
        self.page.locator(f"[data-testid='city-option'][data-value='{city}']").click()
        # Диапазон из одного дня: два клика по сегодняшней дате
        self.dates_input.click()
        self.today.click()
        self.today.click()
        self.submit_btn.click()
