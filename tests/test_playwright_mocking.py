import allure
import pytest
import os
from playwright.sync_api import Page, Route, expect

pytestmark = pytest.mark.regression

UI_BASE_URL = os.getenv("UI_BASE_URL", "https://icarro-v1.netlify.app")


@allure.epic("Playwright Testing")
@allure.feature("Network Interception")
@allure.story("Mocking Search Results")
@allure.title("Изоляция UI: Подмена выдачи автомобилей (Batmobile)")
def test_mock_search_results(page: Page):
    # 1. Готовим фейковый ответ (Бэтмобиль)
    fake_response = {
        "cars": [
            {
                "serialNumber": "BAT-001",
                "manufacture": "Wayne Enterprises",
                "model": "Batmobile",
                "year": "2026",
                "fuel": "Electric",
                "seats": 2,
                "carClass": "Premium",
                "pricePerDay": 9999.99,
                "about": "Does it come in black?",
                "city": "Tel Aviv",
                "image": None
            }
        ]
    }

    # 2. ПЕРЕХВАТ СЕТИ: Ловим POST-запросы к /v1/cars/search
    def handle_route(route: Route):
        if route.request.method == "POST":
            route.fulfill(json=fake_response, status=200)
        else:
            route.continue_()

    # Включаем прослушку сети ДО того, как фронтенд отправит форму
    page.route("**/v1/cars/search", handle_route)

    with allure.step("Открытие главной страницы поиска"):
        page.goto(f"{UI_BASE_URL}/search")

    with allure.step("Заполнение формы реальным городом (для обхода фронтенд-валидации)"):
        city_input = page.locator("#city")
        city_input.fill("Tel Aviv")
        page.locator("[data-testid='city-option']", has_text="Tel Aviv").click()

    with allure.step("Выбор дат и отправка формы"):
        # Кликаем по инпуту дат и дважды по сегодняшнему дню, чтобы выбрать диапазон
        page.locator("#dates").click()
        page.locator(".rdrDayToday").click()
        page.locator(".rdrDayToday").click()

        page.locator("button[type='submit']").click()

    with allure.step("Проверка рендера подмененной машины (Mock)"):
        # Фронтенд должен радостно отрендерить Бэтмобиль, думая, что он пришел из БД!
        expect(page.locator("text=Wayne Enterprises")).to_be_visible()
        expect(page.locator("text=Batmobile")).to_be_visible()
        expect(page.locator("text=10000.0")).to_be_visible()