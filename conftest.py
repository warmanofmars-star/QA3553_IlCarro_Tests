import os
import pytest
import allure
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from dotenv import load_dotenv
from api.car_api import IlCarroAPI

# Загружаем переменные из .env
load_dotenv()


@pytest.fixture
def driver():
    is_headless = os.getenv('HEADLESS_MODE', 'false').lower() == 'true'
    is_ci = os.environ.get('CI') == 'true'

    if is_ci:
        # ПРОФЕССИОНАЛЬНЫЙ CI-ПОДХОД: Google Chrome для Linux-сервера
        options = ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        driver = webdriver.Chrome(options=options)

    else:
        # ЛОКАЛЬНАЯ РАЗРАБОТКА
        options = EdgeOptions()
        if is_headless:
            options.add_argument('--headless')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')

        driver = webdriver.Edge(options=options)
        if not is_headless:
            driver.maximize_window()

    driver.implicitly_wait(5)
    yield driver
    driver.quit()


# --- АВТОМАТИЧЕСКИЕ СКРИНШОТЫ ПРИ ПАДЕНИИ ---
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == 'call' and report.failed:
        driver = item.funcargs.get('driver')
        if driver:
            test_name = item.name.replace("/", "_").replace("::", "_")
            allure.attach(
                driver.get_screenshot_as_png(),
                name=f"Скриншот ошибки: {test_name}",
                attachment_type=allure.attachment_type.PNG
            )


from api.car_api import IlCarroAPI


@pytest.fixture
def auth_api():
    """Фикстура, которая автоматически создает API-клиента и логинится"""
    api = IlCarroAPI()
    email = os.getenv("USER_EMAIL")
    password = os.getenv("USER_PASSWORD")

    with allure.step("Setup Fixture: Автоматическая API-авторизация"):
        api.login(email, password)

    return api