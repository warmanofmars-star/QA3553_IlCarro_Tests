import allure
import pytest

from data.data_generator import CarGenerator, SearchDataGenerator
from data.known_bugs import known_bug
from data.observations import observation
from utils.api_validators import assert_secure_error
from utils.car_state import my_cars
from utils.preconditions import require

pytestmark = [pytest.mark.api, pytest.mark.regression, pytest.mark.mutation]


@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Negative Payload Mutations (DDT)")
@allure.severity(allure.severity_level.CRITICAL)
# state_is_precondition: известный баг касается только кода ответа, а данные ведут себя правильно.
# Тогда проверка состояния — предусловие (require): её провал не должен спрятаться за xfail.
@pytest.mark.parametrize(
    "mutate_func, expected_status, scenario, state_is_precondition",
    [
        # 1. Удаление обязательного поля
        pytest.param(
            lambda p: p.pop("manufacture"),
            400,
            "Удаление обязательного поля (manufacture)",
            False,
            marks=allure.tag("REQ-CAR-02"),
        ),
        # 2. Пустые строки в обязательном поле
        pytest.param(
            lambda p: p.update({"model": ""}),
            400,
            "Пустая строка вместо значения (model)",
            False,
            marks=allure.tag("REQ-CAR-02"),
        ),
        # 3. Null вместо строки
        pytest.param(
            lambda p: p.update({"carClass": None}),
            400,
            "Null вместо строки (carClass)",
            False,
            marks=allure.tag("REQ-CAR-02"),
        ),
        # 4. Неверный тип данных: REQ-CAR-03 (500 вместо 400; машина при этом не создаётся)
        pytest.param(
            lambda p: p.update({"seats": "пять"}),
            400,
            "Строка вместо числа (seats)",
            True,
            marks=[known_bug("WRONG_TYPE_500"), allure.tag("REQ-CAR-03")],
        ),
        # 5. Бессмысленное значение: OBS-03 (требования нет, API сохраняет машину — это и есть наблюдение)
        pytest.param(
            lambda p: p.update({"pricePerDay": -100}),
            400,
            "Отрицательная цена",
            False,
            marks=[observation("NONSENSE_CAR_VALUES"), allure.tag("OBS-03")],
        ),
    ],
)
def test_api_car_mutations(
    shared_api, shared_car_cleanup, mutate_func, expected_status, scenario, state_is_precondition
):
    with allure.step(f"Сценарий мутации: {scenario}"):
        # 1. Генерируем 100% валидный словарь данных
        base_payload = CarGenerator.get_random_car().to_api_payload()
        serial_number = base_payload["serialNumber"]
        # Машина не должна создаться; если из-за дефекта создастся (цена -100), очистка её уберёт
        shared_car_cleanup.register(serial_number)

        # 2. Применяем лямбда-функцию, чтобы сломать словарь "на лету"
        mutate_func(base_payload)

        # 3. Отправляем мутировавший запрос
        response = shared_api.add_car(base_payload)

    with allure.step("Состояние: машины с этим serialNumber нет в /v1/cars/my"):
        is_saved = serial_number in my_cars(shared_api)
        message = f"Невалидная машина {serial_number} сохранилась. Ответ: {response.status_code} {response.text}"
        if state_is_precondition:
            require(not is_saved, message)
        else:
            assert not is_saved, message

    # 4. Прогоняем ответ через глобальный сканер безопасности
    assert_secure_error(response, expected_status)


# Обязательные поля CarDto (Swagger, CarDto.required) и их «пустое» значение: для строк — "",
# для чисел — null (пустой строки у числа не бывает, и это был бы уже неверный тип, REQ-CAR-03)
CAR_REQUIRED_FIELDS = {
    "serialNumber": "",
    "manufacture": "",
    "model": "",
    "year": "",
    "fuel": "",
    "seats": None,
    "carClass": "",
    "pricePerDay": None,
    "city": "",
}


@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Required fields")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-CAR-02")
@pytest.mark.parametrize("field", CAR_REQUIRED_FIELDS)
def test_api_car_required_field(shared_api, shared_car_cleanup, field):
    """Без обязательного поля или с пустым значением машина не создаётся, ответ — 400.

    Пользователь общий (shared_user): тесту нужен только токен. Проблемы обоих вариантов
    собираются и выводятся вместе.
    """
    problems = []
    empty_value = CAR_REQUIRED_FIELDS[field]
    for mode, mutate in (
        ("поле отсутствует", lambda payload: payload.pop(field)),
        (f"значение {empty_value!r}", lambda payload: payload.update({field: empty_value})),
    ):
        with allure.step(f"{field}: {mode}"):
            payload = CarGenerator.get_random_car().to_api_payload()
            serial_number = payload["serialNumber"]
            # Машина не должна создаться; если создастся — очистка её уберёт
            shared_car_cleanup.register(serial_number)
            mutate(payload)
            before = set(my_cars(shared_api))
            response = shared_api.add_car(payload)

            # Сравниваем список машин до и после запроса, а не ищем номер: машину без serialNumber
            # по номеру не найти. Тесты воркера идут последовательно — чужих изменений в списке нет
            saved = set(my_cars(shared_api)) - before
            if saved:
                problems.append(
                    f"{mode}: машина сохранилась {sorted(map(str, saved))} ({response.status_code} {response.text})"
                )
            elif response.status_code != 400:
                problems.append(f"{mode}: ожидали 400, получили {response.status_code} {response.text}")

    with allure.step("Проверка: оба варианта отклонены с 400, машина не сохранена"):
        assert not problems, f"Обязательное поле {field}:\n" + "\n".join(problems)


@pytest.mark.security
@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Mass Assignment: owner и bookedPeriods из тела запроса")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-CAR-04")
def test_api_car_mass_assignment(user_pair, shared_create_car):
    """
    Владелец определяется по токену; owner и bookedPeriods из тела запроса игнорируются
    (REQ-CAR-04, OWASP API3:2023). Сценарий — как в исследовании Q-API-04.
    Создатель — владелец пары, в подложный owner подставлен чужой; машина ищется по номеру.
    """
    owner, second_user = user_pair
    start_date, end_date = SearchDataGenerator.get_safe_future_dates()
    spoofed_period = {
        "email": second_user.user.email,
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
    }

    with allure.step("Создаем машину с чужим owner и подложными bookedPeriods"):
        car = shared_create_car(extra_fields={"owner": second_user.user.email, "bookedPeriods": [spoofed_period]})
        # Если подмена сработает, машина окажется у второго пользователя — пусть его очистка её уберёт
        second_user.cleanup.register(car.reg_number)

    with allure.step("Проверка: машина у создателя, owner — его email, bookedPeriods пуст"):
        owner_cars = my_cars(owner.api)
        assert car.reg_number in owner_cars, f"Машины {car.reg_number} нет в /v1/cars/my создателя"
        saved = owner_cars[car.reg_number]
        assert saved.get("owner") == owner.user.email, (
            f"owner подменён из тела запроса: ожидали {owner.user.email}, получили {saved.get('owner')}"
        )
        assert not saved.get("bookedPeriods"), f"bookedPeriods взят из тела запроса: {saved.get('bookedPeriods')}"

    with allure.step("Проверка: у пользователя из подложного owner этой машины нет"):
        assert car.reg_number not in my_cars(second_user.api), (
            f"Машина {car.reg_number} появилась в /v1/cars/my пользователя из подложного owner"
        )
