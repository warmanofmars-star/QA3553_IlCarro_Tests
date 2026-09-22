import os
import allure
from playwright.sync_api import Page

class PwBasePage:
    def __init__(self, page: Page):
        self.page = page
        self.base_url = os.getenv("UI_BASE_URL", "https://icarro-v1.netlify.app")
        # Читаем таймаут из .env (по умолчанию 10000 мс, если переменной нет)
        pw_timeout = os.getenv("PW_TIMEOUT", "10000")
        self.expect_timeout = int(pw_timeout)

    @allure.step("Открытие URL: {path}")
    def open_url(self, path: str = ""):
        # Playwright сам дождется события 'load', нам не нужны неявные ожидания
        self.page.goto(f"{self.base_url}{path}")