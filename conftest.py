import os
import pytest
import allure
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

@pytest.fixture
def driver():
    options = Options()
    is_headless = os.getenv('HEADLESS_MODE', 'false').lower() == 'true'

    if os.environ.get('CI') == 'true' or is_headless:
        options.add_argument('--headless')
        options.add_argument('--window-size=1920,1080')

    driver = webdriver.Edge(options=options)

    if not (os.environ.get('CI') == 'true' or is_headless):
        driver.maximize_window()

    driver.implicitly_wait(5)
    yield driver
    driver.quit()

# --- НОВЫЙ БЛОК: АВТОМАТИЧЕСКИЕ СКРИНШОТЫ ---
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Хук, который вызывается после каждой фазы теста.
    Если тест падает, делает скриншот и крепит его в Allure.
    """
    outcome = yield
    report = outcome.get_result()

    # Проверяем, что тест упал именно на этапе выполнения (call)
    if report.when == 'call' and report.failed:
        # Достаем веб-драйвер из фикстуры
        driver = item.funcargs.get('driver')

        if driver:
            test_name = item.name.replace("/", "_").replace("::", "_")
            allure.attach(
                driver.get_screenshot_as_png(),
                name=f"Скриншот ошибки: {test_name}",
                attachment_type=allure.attachment_type.PNG
            )