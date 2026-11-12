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

    def restore_session(self, token: str):
        """Вход без формы: токен кладётся в localStorage, как его хранит сам фронтенд.

        Для тестов, которым залогиненный браузер нужен только как предусловие: запроса входа
        к общему бэкенду нет. Токен не аргумент шага Allure, поэтому в отчёт не попадает.
        Фронтенд читает localStorage при загрузке страницы — после вызова страницу надо открыть заново.
        """
        with allure.step("Вход: токен пользователя кладётся в localStorage"):
            self.open_url("/login")
            self.page.evaluate(
                "(token) => { localStorage.setItem('token', token); localStorage.setItem('tokenType', 'Bearer'); }",
                token,
            )

    def local_storage_item(self, key: str) -> str | None:
        """Значение ключа localStorage или None, если ключа нет."""
        return self.page.evaluate("(key) => localStorage.getItem(key)", key)
