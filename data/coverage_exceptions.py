"""
Реестр исключений покрытия: пункты requirements.md без автотеста или с неполным покрытием.

Матрица трассируемости (docs/requirements/traceability.md, scripts/coverage_matrix.py) собирается
из тегов тестов. Пункт без единого теста обязан быть записан здесь — с категорией и причиной:
«теста нет» должно быть решением, а не забытой строкой.

Категории пунктов БЕЗ теста:
  * harms_shared_env — проверка вредит общему внешнему бэкенду (объём данных, нагрузка);
  * blocked          — проверку блокирует другой дефект; в blocked_by — его ID;
  * unreachable      — функциональность недостижима: до неё не добраться ни через UI, ни через API;
  * planned          — тест будет написан; в pr — шаг плана: «6.2» (API), «6.3a» (UI: перехват запросов
                       и сессия) или «6.3b» (UI: остальное и наблюдения).
Первые три — исключения: теста не будет, пока не изменится приложение. planned — долг: запись
убирается тем же PR, который добавляет тест.

Категория пункта С тестом — одна:
  * partial          — тест есть, но его assert проверяет не весь пункт; в reason — что НЕ покрыто,
                       в pr — шаг плана, который доберёт остальное.

Английские тексты — для матрицы на английском (docs/requirements/traceability.en.md):
  * reason_en       — обязательно у любой записи, как reason: его перевод;
  * revisit_when_en — обязательно там же, где revisit_when: его перевод.
  Русский текст — оригинал: правка reason или revisit_when — в том же изменении правка перевода.
  Проверка при импорте: в переводе те же опорные элементы, что в оригинале (_TRANSLATION_ANCHORS:
  ссылки Q-…, ID пунктов, имена тестов, ключи реестров, пути /v1/…, русские тексты интерфейса в «…»).

Поля исключений (harms_shared_env, blocked, unreachable):
  * revisit_when — обязательно: когда пересмотреть исключение, одной-двумя фразами. Без него запись
                   жила бы вечно: дефект починят, а пункт так и останется без теста;
  * blocked_by   — только для blocked: ID дефектов, которые мешают проверке;
  * basis        — только для unreachable: ID дефектов, из-за которых функциональность недостижима.
                   Пусто, если недостижимость держится не на зарегистрированном дефекте — тогда
                   revisit_when говорит, почему условие не отслеживается автоматически.
  harms_shared_env основан на общем бэкенде, а не на дефекте: basis и blocked_by у него нет.

Проверка оснований — в `coverage_matrix.py --check` (там загружены все реестры; здесь импорт
known_bugs.py не нужен): каждый ID из blocked_by и basis должен быть среди refs записей data/known_bugs.py.
Цепочка: дефект починили → его строгий xfail даёт XPASS → запись убирают из реестра багов → проверка
называет исключения, которые держались на этом дефекте, и их пересматривают.

Проверка `coverage_matrix.py --check` падает, если у ID нет ни теста, ни записи; если у ID есть тест
и запись любой категории, кроме partial (запись надо убрать); если partial записан на ID без теста.

После шага 6.3b матрица закрыта: записи planned и partial — ошибка проверки (scripts/coverage_matrix.py,
CLOSED_CATEGORIES). Категории остаются в реестре, чтобы проверка назвала такую запись по имени,
а не упала на неизвестной категории.

ID сверяются с requirements.md при импорте модуля, как в реестрах known_bugs.py и observations.py.
"""

import re
from collections import Counter
from dataclasses import dataclass

from data.requirement_ids import requirement_ids

HARMS_SHARED_ENV = "harms_shared_env"
BLOCKED = "blocked"
UNREACHABLE = "unreachable"
PLANNED = "planned"
PARTIAL = "partial"

# Категория -> как она называется в матрице
CATEGORY_TITLES: dict[str, str] = {
    HARMS_SHARED_ENV: "вредит общему бэкенду",
    BLOCKED: "заблокировано другим дефектом",
    UNREACHABLE: "функциональность недостижима",
    PLANNED: "запланировано",
    PARTIAL: "покрыто частично",
}

# Исключения: теста не будет, пока не изменится приложение; у каждого — условие пересмотра
EXCEPTION_CATEGORIES = frozenset({HARMS_SHARED_ENV, BLOCKED, UNREACHABLE})

# Категории, у которых указывается шаг плана (pr)
CATEGORIES_WITH_PR = frozenset({PLANNED, PARTIAL})

# Шаги плана, в которых пишутся запланированные тесты
PLANNED_PRS: dict[str, str] = {
    "6.2": "API",
    "6.3a": "UI: перехват запросов и сессия",
    "6.3b": "UI: остальное и наблюдения",
}


@dataclass(frozen=True)
class CoverageException:
    category: str  # одна из CATEGORY_TITLES
    # почему теста нет; для planned — что проверит будущий тест; для partial — что из пункта НЕ покрыто
    reason: str
    revisit_when: str = ""  # обязательно для EXCEPTION_CATEGORIES: когда пересмотреть исключение
    blocked_by: tuple[str, ...] = ()  # только для blocked: ID дефектов, которые мешают проверке
    basis: tuple[str, ...] = ()  # только для unreachable: ID дефектов, из-за которых функциональность недостижима
    pr: str | None = None  # только для planned и partial: шаг плана из PLANNED_PRS
    reason_en: str = ""  # обязательно: перевод reason для английской матрицы
    revisit_when_en: str = ""  # обязательно там же, где revisit_when: его перевод


def _planned(pr: str, reason: str, reason_en: str) -> CoverageException:
    return CoverageException(category=PLANNED, reason=reason, reason_en=reason_en, pr=pr)


def _partial(pr: str, not_covered: str, not_covered_en: str) -> CoverageException:
    return CoverageException(category=PARTIAL, reason=not_covered, reason_en=not_covered_en, pr=pr)


COVERAGE_EXCEPTIONS: dict[str, CoverageException] = {
    # ---------- Исключения: теста не будет, пока не изменится приложение ----------
    "REQ-SEC-07": CoverageException(
        category=HARMS_SHARED_ENV,
        reason=(
            "Проверка ограничения размера — это загрузка больших данных на общий бэкенд и выкачивание "
            "выдачи крупного города (Tel Aviv — около 18 МБ). Факт зафиксирован исследованием: Q-UI-06, Q-API-02"
        ),
        revisit_when=(
            "Появится свой стенд вместо общего бэкенда: на нём загрузку больших данных и крупную выдачу проверять можно"
        ),
        reason_en=(
            "Checking the size limit means uploading large data to the shared backend and downloading the search "
            "results of a large city (Tel Aviv — about 18 MB). The fact is recorded by the research: Q-UI-06, Q-API-02"
        ),
        revisit_when_en=(
            "A dedicated test environment replaces the shared backend: there large uploads and large search results "
            "can be checked"
        ),
    ),
    "REQ-SEARCH-03": CoverageException(
        category=BLOCKED,
        blocked_by=("REQ-BOOK-01",),
        reason=(
            "Бронирование не сохраняется, bookedPeriods пуст у всех машин системы (Q-API-12): "
            "занятую машину для проверки поиска создать нечем"
        ),
        revisit_when=(
            "Бронь начнёт сохраняться: test_api_car_booking_flow (BOOKING_NOT_PERSISTED) даст XPASS, "
            "запись бага уберут — --check назовёт это исключение"
        ),
        reason_en=(
            "Bookings are not saved, bookedPeriods is empty for every car in the system (Q-API-12): "
            "there is no way to create a booked car for the search check"
        ),
        revisit_when_en=(
            "Bookings start being saved: test_api_car_booking_flow (BOOKING_NOT_PERSISTED) gives XPASS, "
            "the bug entry is removed — `coverage_matrix.py --check` will list this exception"
        ),
    ),
    "REQ-UI-CARPAGE-02": CoverageException(
        category=UNREACHABLE,
        basis=("REQ-UI-CARPAGE-01",),
        reason=(
            "Кнопка «Rent now!!» находится на странице машины, а страница не открывается: "
            "«Не удалось загрузить машину» (REQ-UI-CARPAGE-01, Q-UI-02)"
        ),
        revisit_when=(
            "Страница машины начнёт показывать данные: test_pw_car_card_opens_car_page (CAR_PAGE_NOT_LOADED) "
            "даст XPASS, запись бага уберут — --check назовёт это исключение"
        ),
        reason_en=(
            "The “Rent now!!” button is on the car page, and the page does not open: "
            "«Не удалось загрузить машину» (“Failed to load the car”) (REQ-UI-CARPAGE-01, Q-UI-02)"
        ),
        revisit_when_en=(
            "The car page starts showing data: test_pw_car_card_opens_car_page (CAR_PAGE_NOT_LOADED) "
            "gives XPASS, the bug entry is removed — `coverage_matrix.py --check` will list this exception"
        ),
    ),
    "DISC-06": CoverageException(
        category=UNREACHABLE,
        basis=("REQ-UI-CARPAGE-01",),
        reason=(
            "Сторона фронтенда — сообщение «Бронирование пока не реализовано в API» — на странице машины, "
            "которая не открывается (REQ-UI-CARPAGE-01). Сторону API проверяют REQ-BOOK-01 и REQ-BOOK-02"
        ),
        revisit_when=(
            "Страница машины начнёт показывать данные: test_pw_car_card_opens_car_page (CAR_PAGE_NOT_LOADED) "
            "даст XPASS, запись бага уберут — --check назовёт это исключение"
        ),
        reason_en=(
            "The frontend side — the message «Бронирование пока не реализовано в API» (“Booking is not implemented "
            "in the API yet”) — is on the car page, which does not open (REQ-UI-CARPAGE-01). The API side is checked "
            "by REQ-BOOK-01 and REQ-BOOK-02"
        ),
        revisit_when_en=(
            "The car page starts showing data: test_pw_car_card_opens_car_page (CAR_PAGE_NOT_LOADED) "
            "gives XPASS, the bug entry is removed — `coverage_matrix.py --check` will list this exception"
        ),
    ),
    "DISC-10": CoverageException(
        category=UNREACHABLE,
        reason=(
            "PUT /v1/user/profile фронт отправляет только после успешной загрузки профиля, а GET /v1/user/profile "
            "всегда заканчивается сбоем (Q-UI-27, Q-UI-33). Подменять ответ эндпоинта вне Swagger нельзя "
            "(правило подмены, CLAUDE.md)"
        ),
        # basis пуст: зарегистрированного дефекта, который точно следит за сбоем GET /v1/user/profile, нет
        revisit_when=(
            "Не отслеживается автоматически: исключение держится на сбое GET /v1/user/profile (Q-UI-27, Q-UI-33), "
            "а test_pw_profile_page_request_is_documented (DISC-05) проверяет, описан ли запрос в Swagger, "
            "а не успешен ли ответ. Пересмотреть, если GET /v1/user/profile начнёт отвечать успешно"
        ),
        reason_en=(
            "The frontend sends PUT /v1/user/profile only after the profile has loaded successfully, and "
            "GET /v1/user/profile always ends in a failure (Q-UI-27, Q-UI-33). Substituting the response of an "
            "endpoint outside Swagger is not allowed (the response substitution rule, CLAUDE.md)"
        ),
        revisit_when_en=(
            "Not tracked automatically: the exception rests on the failure of GET /v1/user/profile (Q-UI-27, "
            "Q-UI-33), while test_pw_profile_page_request_is_documented (DISC-05) checks whether the request is "
            "described in Swagger, not whether the response succeeds. Revisit if GET /v1/user/profile starts "
            "answering successfully"
        ),
    ),
    "DISC-09": CoverageException(
        category=BLOCKED,
        blocked_by=("DISC-05",),
        reason=(
            "Поля, которые читает страница машины, видны только в ответе GET /v1/cars/{id}, а у этого эндпоинта "
            "нет контракта (DISC-05): на бэкенде он отвечает 403, в браузере обрывается (Q-UI-01, Q-UI-19). "
            "Подменять ответ несуществующего эндпоинта не будем — его тело пришлось бы выдумать. "
            "Согласовано с пользователем"
        ),
        revisit_when=(
            "GET /v1/cars/{id} появится в Swagger: test_pw_car_page_request_is_documented даст XPASS. "
            "Запись FRONTEND_CALLS_UNDOCUMENTED_ENDPOINTS — о двух эндпоинтах (DISC-05): пока не починен и профиль, "
            "--check это исключение не назовёт — пересмотреть по XPASS"
        ),
        reason_en=(
            "The fields the car page reads are visible only in the response of GET /v1/cars/{id}, and this endpoint "
            "has no contract (DISC-05): on the backend it answers 403, in the browser the request is dropped "
            "with no response status (Q-UI-01, Q-UI-19). We do not substitute the response of a non-existent "
            "endpoint — its body would have to be invented. Agreed with the project author"
        ),
        revisit_when_en=(
            "GET /v1/cars/{id} appears in Swagger: test_pw_car_page_request_is_documented gives XPASS. "
            "The FRONTEND_CALLS_UNDOCUMENTED_ENDPOINTS entry covers two endpoints (DISC-05): until the profile "
            "endpoint is fixed as well, `coverage_matrix.py --check` will not list this exception — "
            "revisit on the XPASS"
        ),
    ),
}


# Опорные элементы текста, которые перевод переносит без изменений: по ним сверяются reason с reason_en
# и revisit_when с revisit_when_en. Правка оригинала без правки перевода (или наоборот) меняет их набор
# и валит реестр, а не проходит молча. Каждый элемент считается с кратностью (мультисет)
_TRANSLATION_ANCHORS = (
    re.compile(r"\bQ-(?:API|UI)-\d+\b"),  # ссылки на исследование: Q-API-12, Q-UI-02
    re.compile(r"\b(?:REQ|DISC|OBS)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b"),  # ID пунктов: REQ-UI-CARPAGE-01, DISC-05
    re.compile(r"\btest_\w+"),  # имена тестов: test_pw_car_card_opens_car_page
    # Ключи реестров: BOOKING_NOT_PERSISTED. Подчёркивание обязательно — иначе ловились бы API, GET, CLAUDE
    re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b"),
    re.compile(r"/v1/[\w/{}-]+"),  # пути эндпоинтов: /v1/cars/{id}; точка в конце предложения не входит
    re.compile(r"«[^«»]*[А-Яа-яЁё][^«»]*»"),  # русские тексты интерфейса — в переводе байт в байт
)


def _anchors(text: str) -> Counter:
    return Counter(match for pattern in _TRANSLATION_ANCHORS for match in pattern.findall(text))


def _check_translation(item_id: str, field_name: str, original: str, translation: str) -> None:
    """Перевод несёт те же опорные элементы, что и оригинал; иначе — ошибка реестра."""
    expected, actual = _anchors(original), _anchors(translation)
    if expected != actual:
        raise ValueError(
            f"Исключение покрытия {item_id!r}: {field_name}_en не согласован с {field_name}: "
            f"в переводе нет {sorted((expected - actual).elements()) or '—'}, "
            f"лишнее {sorted((actual - expected).elements()) or '—'}. Поправь перевод вместе с оригиналом."
        )


def _validate_registry() -> None:
    """Сверяет записи с requirements.md и правилами категорий. Вызывается один раз при импорте модуля."""
    known_ids = requirement_ids()
    for item_id, entry in COVERAGE_EXCEPTIONS.items():
        if item_id not in known_ids:
            raise ValueError(f"Исключение покрытия {item_id!r}: такого ID нет в docs/requirements/requirements.md.")
        if entry.category not in CATEGORY_TITLES:
            raise ValueError(
                f"Исключение покрытия {item_id!r}: неизвестная категория {entry.category!r}. "
                f"Допустимые: {', '.join(CATEGORY_TITLES)}."
            )
        if not entry.reason.strip():
            raise ValueError(f"Исключение покрытия {item_id!r}: не указана причина (reason).")
        if not entry.reason_en.strip():
            raise ValueError(
                f"Исключение покрытия {item_id!r}: не указан перевод причины (reason_en) — "
                "он нужен английской матрице docs/requirements/traceability.en.md."
            )

        if (entry.category == BLOCKED) != bool(entry.blocked_by):
            raise ValueError(
                f"Исключение покрытия {item_id!r}: blocked_by указывается для категории blocked и только для неё."
            )
        for blocker in entry.blocked_by:
            if blocker not in known_ids:
                raise ValueError(
                    f"Исключение покрытия {item_id!r}: блокирующего ID {blocker!r} нет "
                    "в docs/requirements/requirements.md."
                )
            if blocker == item_id:
                raise ValueError(f"Исключение покрытия {item_id!r}: пункт не может блокировать сам себя.")

        if entry.category in EXCEPTION_CATEGORIES and not entry.revisit_when.strip():
            raise ValueError(
                f"Исключение покрытия {item_id!r}: не указано условие пересмотра (revisit_when). "
                "Без него исключение останется навсегда, даже когда его основание исчезнет."
            )
        if entry.category in EXCEPTION_CATEGORIES and not entry.revisit_when_en.strip():
            raise ValueError(
                f"Исключение покрытия {item_id!r}: не указан перевод условия пересмотра (revisit_when_en) — "
                "он нужен английской матрице docs/requirements/traceability.en.md."
            )
        _check_translation(item_id, "reason", entry.reason, entry.reason_en)
        _check_translation(item_id, "revisit_when", entry.revisit_when, entry.revisit_when_en)
        if entry.basis and entry.category != UNREACHABLE:
            raise ValueError(f"Исключение покрытия {item_id!r}: basis указывается только для категории unreachable.")
        for ground in entry.basis:
            if ground not in known_ids:
                raise ValueError(
                    f"Исключение покрытия {item_id!r}: основания {ground!r} нет в docs/requirements/requirements.md."
                )
            if ground == item_id:
                raise ValueError(f"Исключение покрытия {item_id!r}: пункт не может быть основанием сам себе.")

        if (entry.category in CATEGORIES_WITH_PR) != (entry.pr is not None):
            raise ValueError(
                f"Исключение покрытия {item_id!r}: pr указывается для категорий planned и partial и только для них."
            )
        if entry.pr is not None and entry.pr not in PLANNED_PRS:
            raise ValueError(
                f"Исключение покрытия {item_id!r}: неизвестный шаг плана {entry.pr!r}. "
                f"Допустимые: {', '.join(PLANNED_PRS)}."
            )


_validate_registry()
