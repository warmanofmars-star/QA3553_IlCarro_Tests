from datetime import date

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
        self.city_dropdown = page.locator("[data-testid='city-dropdown']")
        self.rows_per_page = page.locator(".search-results select")
        # Сообщения формы и выдачи для пользователя: блоки role=status и role=alert
        self.messages = page.locator("main [role='status'], main [role='alert']")

    def open(self):
        self.open_url(self.endpoint)

    @allure.step("Поиск: город {city}, даты — сегодняшний день")
    def search_today(self, city: str):
        self.city_input.fill(city)
        self.page.locator(f"[data-testid='city-option'][data-value='{city}']").click()
        self._pick_today_and_submit()

    @allure.step("Поиск: город «{city}» введён вручную, даты — сегодняшний день")
    def search_today_typed(self, city: str):
        """Город остаётся таким, как введён: подсказка закрывается клавишей Tab, без выбора варианта."""
        self.city_input.fill(city)
        self.city_input.press("Tab")
        self.city_dropdown.wait_for(state="hidden")
        self._pick_today_and_submit()

    def _pick_today_and_submit(self):
        # Диапазон из одного дня: два клика по сегодняшней дате
        self.dates_input.click()
        self.today.click()
        self.today.click()
        self.submit_btn.click()

    @allure.step("Город {city}: выбор из подсказки")
    def choose_city(self, city: str):
        self.city_input.fill(city)
        self.page.locator(f"[data-testid='city-option'][data-value='{city}']").click()

    @allure.step("Даты: {start} — {end}")
    def pick_range(self, start: date, end: date):
        """Диапазон дат в календаре; календарь открывается на текущем месяце (как в пробах Q-UI-38)."""
        self.dates_input.click()
        shown = (date.today().year, date.today().month)
        for day in (start, end):
            if (day.year, day.month) != shown:
                self.page.locator(".rdrNextButton").click()
                shown = (day.year, day.month)
            # Точное совпадение числа: подстрока «1» нашла бы и 11, и 21
            day_number = self.page.get_by_text(str(day.day), exact=True)
            self.page.locator("button.rdrDay:not(.rdrDayPassive):not(.rdrDayDisabled)").filter(
                has=day_number
            ).first.click()
        # Клик вне календаря закрывает его (REQ-UI-SEARCH-06)
        self.page.locator("h1.title").click()

    @allure.step("Клик «Yalla!»")
    def submit(self):
        self.submit_btn.click()

    def card_links(self) -> list[str]:
        """Адреса карточек выдачи (/cars/{serialNumber}): сравнить наборы, не читая данных машин."""
        return self.cards.evaluate_all("els => els.map(e => e.getAttribute('href'))")

    def card(self, serial_number: str):
        """Карточка машины в выдаче: ссылка на /cars/{serialNumber} (FE: Search)."""
        return self.page.locator(f"a.car-container[href$='/cars/{serial_number}']")

    def card_price(self, serial_number: str):
        return self.card(serial_number).locator(".car-price-value")

    @allure.step("Rows per page: выбор {size}")
    def choose_page_size(self, size: int):
        self.rows_per_page.select_option(str(size))
