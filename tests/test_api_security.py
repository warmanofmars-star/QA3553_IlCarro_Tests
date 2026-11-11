import base64

import allure
import pytest

from api.car_api import IlCarroAPI
from data.data_generator import CarGenerator, UserGenerator
from data.known_bugs import known_bug
from utils.car_state import my_cars
from utils.preconditions import require

pytestmark = [pytest.mark.api, pytest.mark.security]


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Security")
@allure.story("Authentication (Tokens)")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.parametrize(
    "auth_case, expected_status, scenario",
    [
        pytest.param(
            "empty",
            401,
            "Пустой токен (Отсутствует заголовок)",
            marks=[known_bug("NO_AUTH_403"), allure.tag("REQ-SEC-01")],
        ),
        pytest.param("invalid", 401, "Невалидный токен (Мусорная строка)", marks=allure.tag("REQ-SEC-02")),
        # Строка после Basic для сервера — тот же невалидный токен: он разбирает её как JWT (Q-API-09)
        pytest.param("wrong_scheme", 401, "Неверная схема (Basic вместо Bearer)", marks=allure.tag("REQ-SEC-02")),
    ],
)
def test_api_security_auth_tokens(auth_case, expected_status, scenario):
    """
    Проверка того, как сервер отбивает неавторизованные запросы
    с разными проблемами в заголовке Authorization.
    """
    # Сценарий "empty": клиент без заголовка Authorization — настраивать нечего
    api = IlCarroAPI()

    if auth_case == "invalid":
        api.session.headers.update({"Authorization": "Bearer fake_invalid_token_123"})
    elif auth_case == "wrong_scheme":
        temp_user = UserGenerator.get_random_user()
        res = api.register(temp_user.email, temp_user.password)
        require(res.status_code == 200, f"Не удалось зарегистрировать пользователя для сценария: {res.text}")
        valid_token = res.json().get("accessToken")
        api.session.headers.update({"Authorization": f"Basic {valid_token}"})

    with allure.step(f"Сценарий: {scenario} -> Попытка запросить список машин"):
        response = api.get_my_cars()

    with allure.step(f"Проверка: Сервер должен вернуть {expected_status} Unauthorized"):
        assert response.status_code == expected_status, (
            f"УЯЗВИМОСТЬ: Ожидался статус {expected_status}, получен {response.status_code}"
        )


# Признаки деталей реализации в тексте ошибки: имя технологии и тексты её парсера (Q-API-09)
IMPLEMENTATION_DETAILS = ("jwt", "malformed", "period characters", "exception", "io.jsonwebtoken")


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Security")
@allure.story("Error Messages Disclosure")
@allure.severity(allure.severity_level.NORMAL)
@known_bug("JWT_DETAILS_IN_ERROR")
@allure.tag("REQ-SEC-03")
@pytest.mark.parametrize(
    "auth_case, authorization",
    [
        pytest.param("garbage_bearer", "Bearer garbage.token.value", id="garbage_bearer"),
        # base64 строки без точек: для парсера JWT — «строка без двух точек» (Q-API-09)
        pytest.param("basic_scheme", f"Basic {base64.b64encode(b'probe:probe').decode()}", id="basic_scheme"),
    ],
)
def test_api_security_invalid_token_error_text(auth_case, authorization):
    """Текст ошибки на невалидный токен не раскрывает, чем и как сервер разбирает токен (OWASP API8:2023)."""
    api = IlCarroAPI()
    api.session.headers.update({"Authorization": authorization})

    with allure.step(f"Сценарий {auth_case}: запрос списка своих машин"):
        response = api.get_my_cars()

    with allure.step("Предусловие: сервер отклонил токен с 401"):
        # Код ответа — отдельное требование REQ-SEC-02; без отказа проверять текст ошибки нечего
        require(response.status_code == 401, f"Ожидался отказ 401, получен {response.status_code} {response.text}")

    with allure.step("Проверка: в тексте ошибки нет деталей реализации"):
        text = response.text.lower()
        found = [marker for marker in IMPLEMENTATION_DETAILS if marker in text]
        assert not found, f"Текст ошибки раскрывает детали реализации {found}: {response.text}"


@pytest.mark.smoke
@allure.epic("API Testing")
@allure.feature("Security")
@allure.story("BOLA (Broken Object Level Authorization)")
@allure.severity(allure.severity_level.BLOCKER)
@allure.tag("REQ-CAR-09")
def test_api_security_bola_delete(auth_api, create_car, second_user):
    """
    Проверка на уязвимость BOLA (OWASP API1:2023).
    Владелец (temp_user) создает машину, второй пользователь пытается её удалить.
    Проверяем данные, а не код ответа: машина должна остаться у владельца (REQ-CAR-09).
    Код ответа проверяет test_api_security_bola_delete_status.
    """
    car = create_car()
    # Если из-за уязвимости машина «переедет» к второму пользователю, её уберёт его очистка
    second_user.cleanup.register(car.reg_number)

    with allure.step("Уязвимость BOLA: второй пользователь пытается удалить машину владельца"):
        response = second_user.api.delete_car(car.reg_number)

    with allure.step("Проверка: машина осталась в /v1/cars/my владельца"):
        assert car.reg_number in my_cars(auth_api), (
            "КРИТИЧЕСКАЯ УЯЗВИМОСТЬ BOLA! Второй пользователь удалил чужую машину. Ответ: "
            f"{response.status_code} {response.text}"
        )


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Security")
@allure.story("BOLA (Broken Object Level Authorization)")
@allure.severity(allure.severity_level.NORMAL)
@known_bug("NOT_FOUND_400")
@allure.tag("REQ-CAR-10")
def test_api_security_bola_delete_status(auth_api, create_car, second_user):
    """
    Код ответа на удаление чужой машины: 404, чтобы не раскрывать факт её существования
    (REQ-CAR-10, RFC 9110 §15.5.5).
    """
    car = create_car()
    second_user.cleanup.register(car.reg_number)

    with allure.step("Второй пользователь пытается удалить машину владельца"):
        response = second_user.api.delete_car(car.reg_number)

    with allure.step("Предусловие: машина осталась у владельца (иначе это BOLA, а не код ответа)"):
        # Сохранность машины — другое требование (REQ-CAR-09): его нарушение не должно уйти в xfail
        require(car.reg_number in my_cars(auth_api), "Машина пропала у владельца после удаления вторым пользователем")

    with allure.step("Проверка: сервер ответил 404 Not Found"):
        assert response.status_code == 404, (
            f"Ожидался 404 для чужой машины, сервер вернул {response.status_code}. Ответ: {response.text}"
        )


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Idempotency (DELETE)")
@allure.severity(allure.severity_level.NORMAL)
@known_bug("NOT_FOUND_400")
@allure.tag("REQ-CAR-10")
def test_api_idempotency_delete(auth_api, create_car):
    """
    Повторное удаление уже удалённой машины: ожидаем 404 (REQ-CAR-10, RFC 9110 §15.5.5).
    """
    serial_number = create_car().reg_number

    with allure.step("Шаг 1: Удаляем машину (Первый запрос)"):
        res_first = auth_api.delete_car(serial_number)
        # Первое удаление — предусловие: баг REQ-CAR-10 касается только повторного удаления
        require(res_first.status_code == 200, f"Первое удаление провалилось: {res_first.text}")

        require(serial_number not in my_cars(auth_api), "После первого удаления машина осталась в /v1/cars/my")

    with allure.step("Шаг 2: Удаляем ту же машину (Повторный запрос)"):
        res_second = auth_api.delete_car(serial_number)

    with allure.step("Проверка: Сервер корректно обработал дублирующий DELETE-запрос"):
        assert res_second.status_code == 404, (
            f"Ожидался 404 для несуществующей машины, сервер вернул {res_second.status_code}. Ответ: {res_second.text}"
        )


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Security")
@allure.story("HTTP Methods Restrictions (405)")
@allure.severity(allure.severity_level.NORMAL)
@known_bug("UNKNOWN_ROUTE_403")
@allure.tag("REQ-SEC-05")
def test_api_security_method_not_allowed(auth_api, car_cleanup):
    """
    Проверка 16 из статьи: Сервер должен блокировать неподдерживаемые HTTP-методы.
    Пытаемся обновить машину через неподдерживаемый метод PUT.
    """
    car = CarGenerator.get_random_car()
    # Машина не должна создаться; если всё же создастся, очистка её уберёт
    car_cleanup.register(car.reg_number)

    with allure.step("Отправляем PUT-запрос вместо POST на эндпоинт создания машины"):
        url = f"{auth_api.BASE_URL}/v1/cars"
        response = auth_api.session.put(url, json=car.to_api_payload())

    with allure.step("Проверка: Ожидаем 405 Method Not Allowed"):
        assert response.status_code == 405, (
            f"БАГ БЭКЕНДА: Ожидался статус 405, получен {response.status_code}. Ответ: {response.text}"
        )


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Security")
@allure.story("Content-Type Validation (415)")
@allure.severity(allure.severity_level.NORMAL)
@known_bug("WRONG_CONTENT_TYPE_500")
@allure.tag("REQ-SEC-04")
def test_api_security_unsupported_media_type(auth_api):
    """
    Проверка 8 из статьи: Валидация заголовков.
    Сервер не должен пытаться парсить простой текст, если жестко ожидает JSON.
    """
    url = f"{auth_api.BASE_URL}/v1/cars"

    with allure.step("Отправляем обычный текст с заголовком text/plain вместо application/json"):
        headers = {"Content-Type": "text/plain"}
        response = auth_api.session.post(url, data="Just some malicious plain text here", headers=headers)

    with allure.step("Проверка: Ожидаем 415 Unsupported Media Type"):
        assert response.status_code == 415, (
            f"БАГ БЭКЕНДА: Ожидался статус 415, получен {response.status_code}. Ответ: {response.text}"
        )
