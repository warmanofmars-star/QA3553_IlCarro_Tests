import pytest
import allure
from data.data_generator import CarGenerator
from utils.api_validators import assert_secure_error

pytestmark = [pytest.mark.api, pytest.mark.regression]


@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Negative Payload Mutations (DDT)")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("mutate_func, expected_status, scenario", [
    # 1. Удаление обязательного поля
    (lambda p: p.pop("manufacture"), 400, "Удаление обязательного поля (manufacture)"),

    # 2. Пустые строки в обязательном поле
    (lambda p: p.update({"model": ""}), 400, "Пустая строка вместо значения (model)"),

    # 3. Null вместо строки
    (lambda p: p.update({"carClass": None}), 400, "Null вместо строки (carClass)"),

    # 4. Неверный тип данных (BUG 1: Сервер падает с 500 вместо 400)
    pytest.param(
        lambda p: p.update({"seats": "пять"}), 400, "Строка вместо числа (seats)",
        marks=pytest.mark.xfail(reason="BUG BACKEND: 500 Internal Server Error при неверном типе данных")
    ),

    # 5. Граничные и недопустимые значения (BUG 2: Сервер принимает отрицательные числа)
    pytest.param(
        lambda p: p.update({"pricePerDay": -100}), 400, "Отрицательная цена",
        marks=pytest.mark.xfail(reason="BUG BACKEND: Сервер сохраняет машину с отрицательной ценой (200 OK)")
    ),

    # 6. Незадокументированные поля (BUG 3: Уязвимость Mass Assignment)
    pytest.param(
        lambda p: p.update({"is_admin_mode": True}), 400, "Отправка незадокументированного поля (is_admin_mode)",
        marks=pytest.mark.xfail(reason="BUG BACKEND: Сервер игнорирует лишние поля и возвращает 200 OK вместо 400")
    )
])

def test_api_car_mutations(auth_api, mutate_func, expected_status, scenario):
    with allure.step(f"Сценарий мутации: {scenario}"):
        # 1. Генерируем 100% валидный словарь данных
        base_payload = CarGenerator.get_random_car().to_api_payload()

        # 2. Применяем лямбда-функцию, чтобы сломать словарь "на лету"
        mutate_func(base_payload)

        # 3. Отправляем мутировавший запрос
        response = auth_api.add_car(base_payload)

        # 4. Прогоняем ответ через глобальный сканер безопасности
        assert_secure_error(response, expected_status)