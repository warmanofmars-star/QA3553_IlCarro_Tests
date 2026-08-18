from pages.login_page import LoginPage

# Наши тестовые данные
VALID_EMAIL = "warman.of.mars@gmail.com"
VALID_PASSWORD = "z2I8A@U!Hl3T2&@h"


def test_login_flow(driver):
    login_page = LoginPage(driver)

    # 1. Открываем страницу
    login_page.open()

    # 2. Проверяем блокировку кнопки
    assert login_page.is_submit_button_disabled() == True, "Кнопка Y'alla! должна быть неактивна в начале"

    # 3. Выполняем логин
    login_page.login(VALID_EMAIL, VALID_PASSWORD)

    # 4. Проверяем появление окна об успехе
    assert login_page.is_success_message_visible() == True, "Сообщение об успешном входе не появилось!"

    # 5. Закрываем всплывающее окно (чтобы не перекрывало страницу)
    login_page.click_ok_button()

    # 6. Проверяем, что кнопка Log out появилась в меню
    assert login_page.is_logout_button_visible() == True, "Кнопка 'Log out' не появилась в верхнем меню!"