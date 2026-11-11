"""
API регистрации и входа: REQ-AUTH-01 … REQ-AUTH-07 и расхождение DISC-03.

Пользователей API удалить не умеет, поэтому новый аккаунт здесь создаётся только там, где регистрация
и есть проверка. Фикстура registered_user регистрирует ОДНОГО пользователя на модуль и сохраняет ответ:
тест REQ-AUTH-01 проверяет этот ответ, остальные тесты (вход, повторная регистрация, регистр email)
берут того же пользователя и проверяют успешную регистрацию через require(). Негативные регистрации идут
со случайным email: при правильном поведении аккаунт не создаётся.
"""

import uuid
from dataclasses import dataclass

import allure
import pytest
import requests

from api.car_api import IlCarroAPI
from data.data_generator import UserGenerator
from data.known_bugs import known_bug
from models.user import User
from utils.preconditions import require

pytestmark = pytest.mark.api

REGISTRATION_URL = f"{IlCarroAPI.BASE_URL}/v1/user/registration/usernamepassword"
LOGIN_URL = f"{IlCarroAPI.BASE_URL}/v1/user/login/usernamepassword"

REGISTRATION_FIELDS = ("username", "password", "firstName", "lastName")


@dataclass
class RegisteredUser:
    """Пользователь, зарегистрированный фикстурой, и ответ на его регистрацию."""

    user: User
    response: requests.Response


@pytest.fixture(scope="module")
def registered_user() -> RegisteredUser:
    """Один пользователь на модуль; email с заглавными буквами — ради проверки DISC-03.

    Ответ не проверяется через require(): успешная регистрация — предмет теста REQ-AUTH-01.
    Тесты, которым пользователь нужен как предусловие, вызывают _require_registered().
    С xdist тесты модуля могут попасть на разные воркеры — тогда пользователь регистрируется
    на каждом из них.
    """
    email = f"User_{uuid.uuid4().hex[:10]}@Example.COM"
    user = UserGenerator.get_random_user(email=email)
    with allure.step(f"Setup Fixture: регистрация пользователя модуля {email}"):
        response = IlCarroAPI().register(user.email, user.password)
    return RegisteredUser(user=user, response=response)


def _require_registered(registered: RegisteredUser) -> None:
    require(
        registered.response.status_code == 200,
        f"Предусловие: пользователь модуля не зарегистрирован: {registered.response.status_code} "
        f"{registered.response.text}",
    )


def _access_token(response: requests.Response):
    """accessToken из тела ответа или None, если тело — не JSON-объект."""
    try:
        body = response.json()
    except ValueError:
        return None
    return body.get("accessToken") if isinstance(body, dict) else None


def _post(url: str, payload: dict) -> requests.Response:
    """«Сырой» запрос с телом не по контракту. Тело в шаг не пишется: в нём бывает пароль."""
    return requests.post(url, json=payload, timeout=60)


# ---------------------------------------------------------------- регистрация


@pytest.mark.smoke
@allure.epic("API Testing")
@allure.feature("Authentication")
@allure.story("Registration")
@allure.severity(allure.severity_level.BLOCKER)
@allure.tag("REQ-AUTH-01")
def test_api_registration_success(registered_user):
    response = registered_user.response

    with allure.step("Проверка: регистрация вернула 200 и accessToken"):
        assert response.status_code == 200, (
            f"Регистрация с корректными данными: ожидали 200, получили {response.status_code} {response.text}"
        )
        token = _access_token(response)
        assert isinstance(token, str), f"В ответе регистрации нет accessToken-строки: {response.text}"
        assert token, f"В ответе регистрации пустой accessToken: {response.text}"


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Authentication")
@allure.story("Registration")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-AUTH-04")
def test_api_registration_existing_user(registered_user):
    """Повторная регистрация того же username — 400.

    Текст «User already exists» отличает отказ из-за повтора от отказа валидации (тоже 400): иначе
    тест прошёл бы, даже если повтор приняли бы, а отклонили, например, пароль.
    """
    _require_registered(registered_user)
    user = registered_user.user

    with allure.step(f"Повторная регистрация {user.email}"):
        response = IlCarroAPI().register(user.email, user.password)

    with allure.step("Проверка: 400 и сообщение о том, что пользователь уже есть"):
        assert response.status_code == 400, (
            f"Повторная регистрация: ожидали 400, получили {response.status_code} {response.text}"
        )
        assert response.json().get("message") == "User already exists", (
            f"Отказ не из-за повтора username: {response.text}"
        )


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Authentication")
@allure.story("Registration")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-AUTH-02")
@pytest.mark.parametrize("mode", ["missing", "empty"])
@pytest.mark.parametrize("field", REGISTRATION_FIELDS)
def test_api_registration_required_fields(field, mode):
    payload = UserGenerator.get_random_user().to_api_payload()
    if mode == "missing":
        payload.pop(field)
    else:
        payload[field] = ""

    with allure.step(f"Регистрация: поле {field} — {'отсутствует' if mode == 'missing' else 'пустая строка'}"):
        response = _post(REGISTRATION_URL, payload)

    with allure.step("Проверка: 400"):
        assert response.status_code == 400, (
            f"Регистрация без {field} ({mode}): ожидали 400, получили {response.status_code} {response.text}"
        )


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Authentication")
@allure.story("Registration")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-AUTH-03")
@pytest.mark.parametrize(
    "invalid_value",
    [
        pytest.param("Ab1@xyz", id="7_chars"),
        pytest.param("Abcdefg@", id="no_digit"),
        pytest.param("abcdef1@", id="no_uppercase"),
        pytest.param("ABCDEF1@", id="no_lowercase"),
        pytest.param("Abcdefg1", id="no_special_char"),
    ],
)
def test_api_registration_password_pattern(invalid_value):
    """Пароль не по шаблону Swagger отклоняется. Значения — заведомо неверные, поэтому не маскируются."""
    payload = UserGenerator.get_random_user().to_api_payload() | {"password": invalid_value}

    with allure.step(f"Регистрация с паролем {invalid_value!r}"):
        response = _post(REGISTRATION_URL, payload)

    with allure.step("Проверка: 400"):
        assert response.status_code == 400, (
            f"Пароль {invalid_value!r} не по шаблону: ожидали 400, получили {response.status_code} {response.text}"
        )


# ---------------------------------------------------------------- вход


@pytest.mark.smoke
@allure.epic("API Testing")
@allure.feature("Authentication")
@allure.story("Login")
@allure.severity(allure.severity_level.BLOCKER)
@allure.tag("REQ-AUTH-05")
def test_api_login_success(registered_user):
    """Вход с верными данными. Email — в нижнем регистре: так его хранит регистрация (Q-API-06).
    Вход тем же email с заглавными буквами — отдельное расхождение DISC-03 (test_api_login_email_case)."""
    _require_registered(registered_user)
    user = registered_user.user

    response = IlCarroAPI().login(user.email.lower(), user.password)

    with allure.step("Проверка: 200 и accessToken"):
        assert response.status_code == 200, f"Вход: ожидали 200, получили {response.status_code} {response.text}"
        token = _access_token(response)
        assert isinstance(token, str), f"В ответе входа нет accessToken-строки: {response.text}"
        assert token, f"В ответе входа пустой accessToken: {response.text}"


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Authentication")
@allure.story("Login")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("REQ-AUTH-06")
@pytest.mark.parametrize("auth_case", ["wrong_password", "unknown_user"])
def test_api_login_rejected(registered_user, auth_case):
    user = registered_user.user
    if auth_case == "wrong_password":
        _require_registered(registered_user)
        username = user.email.lower()
        # Пароль по шаблону Swagger: отказ должен быть из-за неверного пароля, а не из-за формата
        password = UserGenerator.generate_valid_password()
        require(password != user.password, "Сгенерированный «неверный» пароль совпал с настоящим")
    else:
        username = UserGenerator.generate_valid_email()
        password = UserGenerator.generate_valid_password()

    response = IlCarroAPI().login(username, password)

    with allure.step("Проверка: 401"):
        assert response.status_code == 401, (
            f"Вход ({auth_case}): ожидали 401, получили {response.status_code} {response.text}"
        )


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Authentication")
@allure.story("Login")
@allure.severity(allure.severity_level.NORMAL)
@known_bug("LOGIN_BODY_NOT_VALIDATED")
@allure.tag("REQ-AUTH-07")
@pytest.mark.parametrize("login_case", ["empty_body", "password_not_by_pattern"])
def test_api_login_body_not_by_contract(registered_user, login_case):
    if login_case == "empty_body":
        payload = {}
    else:
        _require_registered(registered_user)
        # Заведомо неверный пароль: не по шаблону AuthenticationBodyDto.password (Q-API-07)
        payload = {"username": registered_user.user.email.lower(), "password": "abc123"}

    with allure.step(f"Вход с телом не по контракту: {login_case}"):
        response = _post(LOGIN_URL, payload)

    with allure.step("Проверка: 400"):
        assert response.status_code == 400, (
            f"Тело входа не по контракту ({login_case}): ожидали 400, получили {response.status_code} {response.text}"
        )


@pytest.mark.regression
@allure.epic("API Testing")
@allure.feature("Authentication")
@allure.story("Login")
@allure.severity(allure.severity_level.NORMAL)
@known_bug("LOGIN_EMAIL_CASE_SENSITIVE")
@allure.tag("DISC-03")
def test_api_login_email_case(registered_user):
    """Вход тем же email с заглавными буквами, с которым прошла регистрация."""
    _require_registered(registered_user)
    user = registered_user.user
    require(user.email != user.email.lower(), "Email пользователя модуля должен содержать заглавные буквы")

    response = IlCarroAPI().login(user.email, user.password)

    with allure.step("Проверка: вход тем же email, что при регистрации, — 200"):
        assert response.status_code == 200, (
            f"Вход email {user.email} (как при регистрации): ожидали 200, получили {response.status_code} "
            f"{response.text}"
        )
