import allure


def assert_secure_error(response, expected_status: int):
    """
    Глобальный валидатор для негативных API-тестов.
    Проверяет статус-код и сканирует тело ответа на предмет утечек чувствительных данных.
    """
    with allure.step(f"Проверка безопасности ответа (ожидаем статус {expected_status})"):
        # 1. Проверяем статус-код
        assert response.status_code == expected_status, \
            f"Ожидался статус {expected_status}, получен {response.status_code}. Ответ: {response.text}"

        # 2. Сканируем на утечки (Data Leaks)
        response_text = response.text.lower()

        # Список стоп-слов, которых категорически не должно быть в клиентском ответе
        data_leaks = [
            "stack trace",
            "traceback",
            "sqlexception",
            "syntax error",
            "password_hash",
            "secret=",
            "internal_id",
            "/var/www/"
        ]

        for leak in data_leaks:
            assert leak not in response_text, \
                f"КРИТИЧЕСКАЯ УЯЗВИМОСТЬ! В ответе с ошибкой найдена утечка данных: '{leak}'. Ответ: {response.text}"