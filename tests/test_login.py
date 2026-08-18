from pages.login_page import LoginPage

VALID_EMAIL = "warman.of.mars@gmail.com"
VALID_PASSWORD = "z2I8A@U!Hl3T2&@h"


def test_login_flow(driver):
    login_page = LoginPage(driver)

    login_page.open()

    assert login_page.is_submit_button_disabled() == True, "Кнопка Y'alla! должна быть неактивна в начале"

    login_page.login(VALID_EMAIL, VALID_PASSWORD)

    # ФИНАЛЬНАЯ ПРОВЕРКА с использованием умного ожидания
    assert login_page.is_success_message_visible() == True, "Сообщение об успешном входе не появилось на экране!"