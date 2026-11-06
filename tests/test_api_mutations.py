import pytest
import allure
from data.data_generator import CarGenerator
from data.known_bugs import known_bug
from data.observations import observation
from utils.api_validators import assert_secure_error

pytestmark = [pytest.mark.api, pytest.mark.regression, pytest.mark.mutation]


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

    # 4. Неверный тип данных: REQ-CAR-03 (500 вместо 400)
    pytest.param(
        lambda p: p.update({"seats": "пять"}), 400, "Строка вместо числа (seats)",
        marks=[known_bug("WRONG_TYPE_500"), allure.tag("REQ-CAR-03")]
    ),

    # 5. Бессмысленное значение: OBS-03 (требования нет, API сохраняет машину)
    pytest.param(
        lambda p: p.update({"pricePerDay": -100}), 400, "Отрицательная цена",
        marks=[observation("NONSENSE_CAR_VALUES"), allure.tag("OBS-03")]
    ),
])

def test_api_car_mutations(auth_api, mutate_func, expected_status, scenario):
    with allure.step(f"Сценарий мутации: {scenario}"):
        # 1. Генерируем 100% валидный словарь данных
        base_payload = CarGenerator.get_random_car().to_api_payload()
        serial_number = base_payload["serialNumber"]

        # 2. Применяем лямбда-функцию, чтобы сломать словарь "на лету"
        mutate_func(base_payload)

        # 3. Отправляем мутировавший запрос
        response = auth_api.add_car(base_payload)

        try:
            # 4. Прогоняем ответ через глобальный сканер безопасности
            assert_secure_error(response, expected_status)
        finally:
            # 5. CLEANUP: Если из-за бага бэкенд все-таки создал невалидную машину (200 OK),
            # удаляем её из БД, чтобы машина с ценой -100 не сломала UI-тесты поиска!
            if response.status_code == 200:
                auth_api.delete_car(serial_number)