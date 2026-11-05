import allure
from playwright.sync_api import Page

from config import settings

class PwBasePage:
    def __init__(self, page: Page):
        self.page = page
        self.base_url = settings.ui_url
        self.expect_timeout = settings.pw_timeout_ms

    @allure.step("Открытие URL: {path}")
    def open_url(self, path: str = ""):
        # Playwright сам дождется события 'load', нам не нужны неявные ожидания
        self.page.goto(f"{self.base_url}{path}")