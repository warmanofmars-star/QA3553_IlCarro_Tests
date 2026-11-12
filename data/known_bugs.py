"""
Реестр известных дефектов тестируемого приложения.

Приложение учебное и не поддерживается: найденные баги никто не исправит. Поэтому тесты, которые
на них натыкаются, помечаются как «ожидаемо падающие» (xfail) — но только через этот реестр:

    @known_bug("NO_AUTH_403")
    def test_api_add_car_unauthorized(...):

Что это даёт:
  * Весь список дефектов проекта — в одном файле.
  * У каждого бага есть ссылки refs на ID из docs/requirements/requirements.md: REQ-… (нарушение
    требования) или DISC-… (расхождение источников). Нет ссылки — это не баг, а наше ожидание
    (для него есть реестр наблюдений data/observations.py), и xfail ставить нельзя.
  * Ссылки проверяются при импорте модуля: опечатка в ID, ID не из requirements.md или префикс
    не REQ-/DISC- ломают сбор тестов с понятным сообщением.
  * Опечатка в ключе даёт KeyError сразу при сборе тестов, а не тихий пропуск.
  * Все xfail строгие (strict=True): если тест вдруг ПРОЙДЁТ, прогон упадёт с XPASS — поведение
    изменилось, баг надо убрать из реестра.
  * raises=AssertionError: в xfail уходят только провалы проверок. Сбой окружения (таймаут, сеть,
    PreconditionError из require()) остаётся обычным FAILED и за «известным багом» не прячется.

Правила:
  1. Ключ — UPPER_SNAKE_CASE, суть дефекта.
  2. refs — только REQ-… и DISC-… из requirements.md.
  3. description — что приложение делает на самом деле (факты — в docs/requirements/research-log.md).
"""

from dataclasses import dataclass

import pytest

from data.requirement_ids import requirement_ids


@dataclass(frozen=True)
class KnownBug:
    refs: tuple[str, ...]  # ID из requirements.md, на которых основана проверка
    description: str  # фактическое (неправильное) поведение приложения


KNOWN_BUGS: dict[str, KnownBug] = {
    "NO_AUTH_403": KnownBug(
        refs=("REQ-SEC-01",),
        description="Без токена защищённые эндпоинты отвечают 403 с пустым телом вместо 401",
    ),
    "NOT_FOUND_400": KnownBug(
        refs=("REQ-CAR-10",),
        description="Удаление несуществующей, уже удалённой или чужой машины возвращает 400 вместо 404",
    ),
    "WRONG_TYPE_500": KnownBug(
        refs=("REQ-CAR-03",),
        description="Значение неверного типа в CarDto (например, seats строкой) вызывает 500 вместо 400",
    ),
    "WRONG_CONTENT_TYPE_500": KnownBug(
        refs=("REQ-SEC-04",),
        description="Content-Type text/plain при создании машины вызывает 500 вместо 415",
    ),
    "UNKNOWN_ROUTE_403": KnownBug(
        refs=("REQ-SEC-05",),
        description="Неподдерживаемый метод или неизвестный путь отвечают 403 с пустым телом вместо 405/404",
    ),
    "BOOKING_NOT_PERSISTED": KnownBug(
        refs=("REQ-BOOK-01",),
        description=(
            "Бронирование отвечает 200 «Car booked successfully!», но ничего не сохраняет: "
            "bookedPeriods машины остаётся пустым"
        ),
    ),
    "CITIES_MISMATCH": KnownBug(
        refs=("DISC-02",),
        description="Списки городов фронтенда (54) и API (37) расходятся: общих только 22",
    ),
    "PASSWORD_RULES_MISMATCH": KnownBug(
        refs=("DISC-01", "REQ-UI-REG-03"),
        description=(
            "Форма регистрации пропускает пароль, который API отклоняет (правила пароля фронтенда и API разные), "
            'а окно ошибки показывает "[object Object]"'
        ),
    ),
    "LOGIN_BODY_NOT_VALIDATED": KnownBug(
        refs=("REQ-AUTH-07",),
        description=(
            "Вход с телом не по контракту (пустой объект {}, пароль не по шаблону) отвечает 401 "
            '"Login or Password incorrect" вместо 400 (Q-API-07)'
        ),
    ),
    "LOGIN_EMAIL_CASE_SENSITIVE": KnownBug(
        refs=("DISC-03",),
        description=(
            "Регистрация приводит email к нижнему регистру, вход — нет: вход тем же email с заглавными "
            "буквами, с которым прошла регистрация, отвечает 401 (Q-API-06)"
        ),
    ),
    "JWT_DETAILS_IN_ERROR": KnownBug(
        refs=("REQ-SEC-03",),
        description=(
            'Ответ на невалидный токен раскрывает тексты парсера JWT: "Malformed JWT JSON…", '
            '"JWT strings must contain exactly 2 period characters" (Q-API-09)'
        ),
    ),
    "BOOKING_UNKNOWN_CAR_200": KnownBug(
        refs=("REQ-BOOK-02",),
        description='Бронирование несуществующей машины отвечает 200 "Car booked successfully!" вместо 404 (Q-API-01)',
    ),
    "SEARCH_PAGINATION_IGNORED": KnownBug(
        refs=("DISC-08",),
        description=(
            "Поиск игнорирует query-параметры page и size, которые передаёт фронт: при size=1 приходят все машины "
            "города (Q-API-02, Q-API-14)"
        ),
    ),
    "CAR_FORM_FIELDS_NOT_SENT": KnownBug(
        refs=("DISC-04",),
        description=(
            "Форма машины собирает Gear, WD и Doors, но в запрос POST /v1/cars они не попадают: введённое "
            "пользователем молча теряется (Q-UI-05, Q-UI-15)"
        ),
    ),
    "LOGIN_ERROR_TEXT_HARDCODED": KnownBug(
        refs=("REQ-UI-LOGIN-03",),
        description=(
            'При ответе 500, 400 и обрыве сети окно «Login failed» показывает "Login or Password incorrect" вместо '
            "«Login failed. Try again»: текст зашит в окно (Q-UI-10)"
        ),
    ),
    "LOGOUT_TOKEN_STILL_VALID": KnownBug(
        refs=("REQ-SEC-06",),
        description=(
            "Токен после «Log out» принимается API: GET /v1/cars/my отвечает 200. Выход только удаляет токен "
            "в браузере, серверного выхода нет (Q-UI-14)"
        ),
    ),
    "CAR_PAGE_NOT_LOADED": KnownBug(
        refs=("REQ-UI-CARPAGE-01",),
        description=(
            "Клик по карточке открывает /cars/{serial}, но вместо данных машины на странице «Не удалось "
            "загрузить машину» (Q-UI-01, Q-UI-19)"
        ),
    ),
    "FRONTEND_CALLS_UNDOCUMENTED_ENDPOINTS": KnownBug(
        refs=("DISC-05",),
        description=(
            "Фронт обращается к операциям, которых нет в Swagger и на бэкенде: GET /v1/cars/{id} (страница машины), "
            "GET и PUT /v1/user/profile (страница профиля) (Q-API-08, Q-UI-18, Q-UI-19)"
        ),
    ),
    "CAR_FORM_CITY_NOT_VALIDATED": KnownBug(
        refs=("REQ-UI-CAR-01",),
        description=(
            "City в форме машины отмечен «*», но в схеме валидации его нет: с пустым городом Submit доступна, "
            'форма уходит с city: "" и получает «Failed to submit car» (Q-UI-04, Q-UI-20)'
        ),
    ),
}

_ALLOWED_PREFIXES = ("REQ-", "DISC-")


def _validate_registry() -> None:
    """Сверяет refs всех записей с requirements.md. Вызывается один раз при импорте модуля."""
    known_ids = requirement_ids()
    for key, bug in KNOWN_BUGS.items():
        if not bug.refs:
            raise ValueError(f"Известный баг {key!r}: нет ссылок refs. Без требования это не баг, а наблюдение.")
        for ref in bug.refs:
            if not ref.startswith(_ALLOWED_PREFIXES):
                raise ValueError(
                    f"Известный баг {key!r}: ссылка {ref!r} должна начинаться с REQ- или DISC-. "
                    "Для OBS-… есть реестр data/observations.py."
                )
            if ref not in known_ids:
                raise ValueError(f"Известный баг {key!r}: ID {ref!r} нет в docs/requirements/requirements.md.")


_validate_registry()


def known_bug(key: str) -> pytest.MarkDecorator:
    """Маркер xfail для известного дефекта из реестра.

    Работает и как декоратор теста, и внутри pytest.param(..., marks=known_bug("...")).
    Тег @allure.tag с ID из refs ставится на тест отдельно.
    """
    if key not in KNOWN_BUGS:
        raise KeyError(f"Неизвестный баг {key!r}. Добавь его в data/known_bugs.py со ссылкой на требование.")
    bug = KNOWN_BUGS[key]
    return pytest.mark.xfail(
        strict=True,
        raises=AssertionError,
        reason=f"[{key}] {bug.description}. Требования: {', '.join(bug.refs)}",
    )
