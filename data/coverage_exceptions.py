"""
Реестр исключений покрытия: пункты requirements.md без автотеста или с неполным покрытием.

Матрица трассируемости (docs/requirements/traceability.md, scripts/coverage_matrix.py) собирается
из тегов тестов. Пункт без единого теста обязан быть записан здесь — с категорией и причиной:
«теста нет» должно быть решением, а не забытой строкой.

Категории пунктов БЕЗ теста:
  * harms_shared_env — проверка вредит общему внешнему бэкенду (объём данных, нагрузка);
  * blocked          — проверку блокирует другой дефект; в blocked_by — его ID;
  * unreachable      — функциональность недостижима: до неё не добраться ни через UI, ни через API;
  * planned          — тест будет написан; в pr — шаг плана: «6.2» (API) или «6.3» (UI и наблюдения).
Первые три — исключения: теста не будет, пока не изменится приложение. planned — долг: запись
убирается тем же PR, который добавляет тест.

Категория пункта С тестом — одна:
  * partial          — тест есть, но его assert проверяет не весь пункт; в reason — что НЕ покрыто,
                       в pr — шаг плана, который доберёт остальное.

Проверка `coverage_matrix.py --check` падает, если у ID нет ни теста, ни записи; если у ID есть тест
и запись любой категории, кроме partial (запись надо убрать); если partial записан на ID без теста.

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

# Категории, у которых указывается шаг плана (pr)
CATEGORIES_WITH_PR = frozenset({PLANNED, PARTIAL})

# Шаги плана, в которых пишутся запланированные тесты
PLANNED_PRS: dict[str, str] = {
    "6.2": "API",
    "6.3": "UI и наблюдения",
}


@dataclass(frozen=True)
class CoverageException:
    category: str  # одна из CATEGORY_TITLES
    # почему теста нет; для planned — что проверит будущий тест; для partial — что из пункта НЕ покрыто
    reason: str
    blocked_by: tuple[str, ...] = ()  # только для blocked: ID дефектов, которые мешают проверке
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
    ),
    "REQ-SEARCH-03": CoverageException(
        category=BLOCKED,
        blocked_by=("REQ-BOOK-01",),
        reason=(
            "Бронирование не сохраняется, bookedPeriods пуст у всех машин системы (Q-API-12): "
            "занятую машину для проверки поиска создать нечем"
        ),
    ),
    "REQ-UI-CARPAGE-02": CoverageException(
        category=UNREACHABLE,
        reason=(
            "Кнопка «Rent now!!» находится на странице машины, а страница не открывается: "
            "«Не удалось загрузить машину» (REQ-UI-CARPAGE-01, Q-UI-02)"
        ),
    ),
    "DISC-06": CoverageException(
        category=UNREACHABLE,
        reason=(
            "Сторона фронтенда — сообщение «Бронирование пока не реализовано в API» — на странице машины, "
            "которая не открывается (REQ-UI-CARPAGE-01). Сторону API проверяют REQ-BOOK-01 и REQ-BOOK-02"
        ),
    ),
    # ---------- Покрыто частично: тест есть, остальное доберёт шаг плана ----------
    "REQ-UI-REG-02": _partial(
        "6.3",
        "Что пользователь после регистрации залогинен (токен, «Log out» в навигации): тест проверяет только "
        "тексты окна",
    ),
    "REQ-UI-LOGIN-01": _partial("6.3", "Приведение email к нижнему регистру перед отправкой (перехват запроса)"),
    "REQ-UI-LOGIN-03": _partial(
        "6.3",
        "Ветка «любая другая ошибка» (500, 400, обрыв сети) — «Login failed. Try again». Нарушается (Q-UI-10) — "
        "нужна запись в known_bugs.py. Проверена только ветка 401",
    ),
    "REQ-UI-CAR-02": _partial(
        "6.3", "Текст «Car submitted successfully»: тесты успешной отправки проверяют только очистку формы"
    ),
    "REQ-UI-SEARCH-02": _partial("6.3", "Верхняя граница: дни позже «сегодня + 365 дней» недоступны"),
    # ---------- Запланировано: 6.2 (API) ----------
    # ---------- Запланировано: 6.3 (UI и наблюдения) ----------
    "REQ-SEC-06": _planned(
        "6.3",
        "Токен после «Log out» не принимается API. Нужен браузер: серверного выхода в API нет. Требование "
        "нарушается (Q-UI-14) — нужна запись в known_bugs.py",
    ),
    "REQ-UI-CAR-01": _planned(
        "6.3",
        "Валидация обязательных полей формы машины до отправки. Для City нарушается (Q-UI-04) — нужна запись "
        "в known_bugs.py",
    ),
    "REQ-UI-CAR-03": _planned("6.3", "Значение Fuel в запросе POST /v1/cars — строчными (перехват запроса)"),
    "REQ-UI-CAR-04": _planned(
        "6.3",
        "Файл фото уходит в поле image как data URL. Только с перехватом запроса, без сохранения на бэкенде: "
        "иначе тест копит изображения на общем сервере (REQ-SEC-07)",
    ),
    "REQ-UI-SEARCH-03": _planned("6.3", "Подсказка города: не больше 8 вариантов; город, введённый вручную"),
    "REQ-UI-SEARCH-04": _planned(
        "6.3",
        "Клиентская пагинация: page и size в URL, 10, 20 и 50 карточек на странице. Тест поиска только "
        "пользуется size=50, но число карточек не проверяет",
    ),
    "REQ-UI-CARPAGE-01": _planned(
        "6.3",
        "Клик по карточке открывает страницу машины с её данными. Требование нарушается (Q-UI-01) — нужна "
        "запись в known_bugs.py",
    ),
    "REQ-UI-SESSION-01": _planned("6.3", "Ответ 401: фронт удаляет token и запоминает postLoginRedirect"),
    "REQ-UI-SESSION-02": _planned("6.3", "«Log out» удаляет токен и переводит на /search"),
    "DISC-04": _planned(
        "6.3",
        "Gear, WD и Doors из формы не попадают в запрос POST /v1/cars (перехват запроса). Расхождение "
        "подтверждено (Q-UI-05) — нужна запись в known_bugs.py",
    ),
    "DISC-05": _planned(
        "6.3",
        "Запросы фронта к эндпоинтам, которых нет в Swagger и на бэкенде (страница машины, профиль). Вместе "
        "с REQ-UI-CARPAGE-01",
    ),
    "DISC-07": _planned(
        "6.3",
        "Сторона фронтенда — форма не пропускает Seats и Price меньше 1 — вместе с REQ-UI-CAR-01. Сторону API "
        "уже фиксирует наблюдение OBS-03",
    ),
    "OBS-01": _planned("6.3", "Поиск тем же городом в другом регистре находит те же машины"),
    "OBS-02": _planned("6.3", "Поиск и бронирование с прошедшими датами, концом раньше начала и без дат"),
    "OBS-04": _planned("6.3", "Пустая выдача поиска обозначена сообщением"),
    "OBS-05": _planned("6.3", "После 401 — переход на страницу входа, «Log out» в навигации нет"),
    "OBS-06": _planned("6.3", "Гостю форма добавления машины не открывается"),
    "OBS-07": _planned("6.3", "Текст ошибки отправки машины называет причину"),
    "OBS-08": _planned(
        "6.3",
        "Цена на карточке совпадает с сохранённой. Правило округления фронтенда уже проверяет REQ-UI-SEARCH-05",
    ),
    "OBS-09": _planned("6.3", "После регистрации URL меняется с /register"),
    "OBS-10": _planned("6.3", "Кнопка «предыдущий месяц» в текущем месяце недоступна"),
    "OBS-11": _planned("6.3", "Тексты страницы машины и профиля — на английском, как остальной интерфейс"),
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
