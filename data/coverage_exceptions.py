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


def _planned(pr: str, reason: str) -> CoverageException:
    return CoverageException(category=PLANNED, reason=reason, pr=pr)


def _partial(pr: str, not_covered: str) -> CoverageException:
    return CoverageException(category=PARTIAL, reason=not_covered, pr=pr)


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
    ),
    "DISC-10": CoverageException(
        category=UNREACHABLE,
        reason=(
            "PUT /v1/user/profile фронт отправляет только после успешной загрузки профиля, а GET /v1/user/profile "
            "всегда заканчивается сбоем (Q-UI-27, Q-UI-33). Подменять ответ эндпоинта вне Swagger нельзя "
            "(правило подмены, CLAUDE.md). Пока GET /v1/user/profile не отвечает успешно; если начнёт — "
            "исключение пересматривается"
        ),
        # basis пуст: зарегистрированного дефекта, который точно следит за сбоем GET /v1/user/profile, нет
        revisit_when=(
            "Не отслеживается автоматически: исключение держится на сбое GET /v1/user/profile (Q-UI-27, Q-UI-33), "
            "а test_pw_profile_page_request_is_documented (DISC-05) проверяет, описан ли запрос в Swagger, "
            "а не успешен ли ответ. Пересмотреть, если GET /v1/user/profile начнёт отвечать успешно"
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
    ),
}


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
