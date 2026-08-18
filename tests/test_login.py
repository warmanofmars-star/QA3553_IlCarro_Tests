import time
from pages.login_page import LoginPage

# Выносим реальные тестовые данные в константы
VALID_EMAIL = "warman.of.mars@gmail.com"
VALID_PASSWORD = "z2I8A@U!Hl3T2&@h"


def test_login_flow(driver):
    login_page = LoginPage(driver)

    # 1. Открываем страницу
    login_page.open()

    # 2. Убеждаемся, что кнопка заблокирована на пустой форме
    assert login_page.is_submit_button_disabled() == True, "Кнопка Y'alla! должна быть неактивна в начале"

    # 3. Выполняем логин с нашими реальными данными через метод-помощник
    login_page.login(VALID_EMAIL, VALID_PASSWORD)

    # Пауза, чтобы успеть визуально проконтролировать ввод данных и клик
    time.sleep(2)

    # В будущем добавим проверку, что мы оказались внутри