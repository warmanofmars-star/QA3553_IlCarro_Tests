import pytest
from selenium import webdriver

@pytest.fixture
def driver():
    driver = webdriver.Edge()
    driver.maximize_window()
    driver.implicitly_wait(5) # Ждем появления элементов до 5 секунд


    yield driver
    driver.quit() # Закрываем браузер после теста