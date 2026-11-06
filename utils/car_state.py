"""
Чтение состояния данных на бэкенде: какие машины лежат у пользователя.

Тесты сначала проверяют состояние (что реально сохранено), а потом ответ сервера: ответ 200
ещё не значит, что данные изменились, а ответ с ошибкой не значит, что не изменились.
Сам запрос списка здесь — предусловие: если /v1/cars/my недоступен, проверить состояние нельзя,
и это сбой окружения (require), а не найденный дефект.
"""

import allure

from utils.preconditions import require


def my_cars(api) -> dict[str, dict]:
    """Машины пользователя из /v1/cars/my: {serialNumber: данные машины}."""
    with allure.step("Состояние: машины пользователя в /v1/cars/my"):
        response = api.get_my_cars()
        require(
            response.status_code == 200,
            f"Не удалось получить /v1/cars/my: {response.status_code} {response.text}",
        )
        return {car.get("serialNumber"): car for car in response.json().get("cars", [])}
