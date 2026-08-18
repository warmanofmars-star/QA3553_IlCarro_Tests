from pages.login_page import LoginPage

VALID_EMAIL = "warman.of.mars@gmail.com"
VALID_PASSWORD = "z2I8A@U!Hl3T2&@h"


def test_login_flow(driver):
    login_page = LoginPage(driver)

    # 1. Открываем страницу
    login_page.open()

    # 2. Убеждаемся, что кнопка заблокирована на пустой форме
    assert login_page.is_submit_button_disabled() == True, "Кнопка Y'alla! должна быть неактивна в начале"

    # 3. Выполняем логин
    login_page.login(VALID_EMAIL, VALID_PASSWORD)

    # 4. ФИНАЛЬНАЯ ПРОВЕРКА: ждем появления окна и проверяем его текст
    actual_text = login_page.get_success_message_text()
    assert actual_text == "You are logged in success", f"Ожидали текст успеха, а получили: {actual_text}"