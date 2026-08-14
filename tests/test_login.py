import time
from pages.login_page import LoginPage


def test_login_form_basics(driver):
    login_page = LoginPage(driver)

    # Открываем нужную страницу
    login_page.open()

    # 1. Проверяем блокировку кнопки в начале
    assert login_page.is_submit_button_disabled() == True, "Кнопка Y'alla! должна быть неактивна в начале"

    # 2. Вводим данные
    login_page.fill_email("warman.of.mars@gmail.com")
    time.sleep(1)
    login_page.fill_password("z2I8A@U!Hl3T2&@h")
    time.sleep(1)

    # 3. Проверяем, что кнопка стала активной
    assert login_page.is_submit_button_disabled() == False, "Кнопка Y'alla! не разблокировалась"