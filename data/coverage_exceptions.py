"""
Реестр пунктов requirements.md, для которых автотеста нет.

Матрица трассируемости (docs/requirements/traceability.md, scripts/coverage_matrix.py) собирается
из тегов тестов. Пункт без единого теста обязан быть записан здесь — с категорией и причиной:
«теста нет» должно быть решением, а не забытой строкой. Проверка `coverage_matrix.py --check` падает,
если у ID нет ни теста, ни записи здесь, а также если запись есть, а тест уже появился
(запись надо убрать).

Категории:
  * harms_shared_env — проверка вредит общему внешнему бэкенду (объём данных, нагрузка);
  * blocked          — проверку блокирует другой дефект; в blocked_by — его ID;
  * unreachable      — функциональность недостижима: до неё не добраться ни через UI, ни через API;
  * planned          — тест будет написан; в pr — шаг плана: «6.2» (API) или «6.3» (UI и наблюдения).

Первые три — исключения: теста не будет, пока не изменится приложение. planned — долг: запись
убирается тем же PR, который добавляет тест.

ID сверяются с requirements.md при импорте модуля, как в реестрах known_bugs.py и observations.py.
"""

from dataclasses import dataclass

from data.requirement_ids import requirement_ids

HARMS_SHARED_ENV = "harms_shared_env"
BLOCKED = "blocked"
UNREACHABLE = "unreachable"
PLANNED = "planned"

# Категория -> как она называется в матрице
CATEGORY_TITLES: dict[str, str] = {
    HARMS_SHARED_ENV: "вредит общему бэкенду",
    BLOCKED: "заблокировано другим дефектом",
    UNREACHABLE: "функциональность недостижима",
    PLANNED: "запланировано",
}

# Шаги плана, в которых пишутся запланированные тесты
PLANNED_PRS: dict[str, str] = {
    "6.2": "API",
    "6.3": "UI и наблюдения",
}


@dataclass(frozen=True)
class CoverageException:
    category: str  # одна из CATEGORY_TITLES
    reason: str  # почему теста нет; для planned — что именно проверит будущий тест
    blocked_by: tuple[str, ...] = ()  # только для blocked: ID дефектов, которые мешают проверке
    pr: str | None = None  # только для planned: шаг плана из PLANNED_PRS


def _planned(pr: str, reason: str) -> CoverageException:
    return CoverageException(category=PLANNED, reason=reason, pr=pr)


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
    # ---------- Запланировано: 6.2 (API) ----------
    "REQ-AUTH-01": _planned(
        "6.2",
        "Регистрация: 200 и accessToken. Сейчас это только предусловие фикстуры temp_user (require), а не проверка",
    ),
    "REQ-AUTH-02": _planned("6.2", "Регистрация без обязательных полей и с пустыми значениями: 400"),
    "REQ-AUTH-03": _planned("6.2", "Регистрация с паролем не по шаблону Swagger: 400"),
    "REQ-AUTH-05": _planned("6.2", "Вход с верными данными: 200 и accessToken"),
    "REQ-AUTH-06": _planned("6.2", "Вход с неверным паролем и несуществующим пользователем: 401"),
    "REQ-AUTH-07": _planned(
        "6.2",
        "Вход с телом не по контракту: 400. Требование нарушается (401, Q-API-07) — нужна запись в known_bugs.py",
    ),
    "REQ-CAR-05": _planned(
        "6.2",
        "Повтор serialNumber: 400. UI-тесты дубликата видят только общий текст «Failed to submit car» (OBS-07), "
        "код ответа они не проверяют",
    ),
    "REQ-CAR-06": _planned("6.2", "Машина с городом не из /v1/cars/cities: 400, машина не создана"),
    "REQ-CAR-07": _planned("6.2", "У двух пользователей свои машины: /v1/cars/my каждого отдаёт только его машины"),
    "REQ-SEARCH-01": _planned(
        "6.2", "Поиск без токена: 200. Сейчас поиск вызывается только в предусловиях и с токеном"
    ),
    "REQ-SEARCH-02": _planned("6.2", "У всех машин выдачи city равен искомому (город с малым числом машин)"),
    "REQ-BOOK-02": _planned(
        "6.2",
        "Бронирование несуществующей машины: 404. Требование нарушается (200, Q-API-01) — нужна запись в known_bugs.py",
    ),
    "REQ-BOOK-03": _planned(
        "6.2", "Бронирование без токена отклоняется. Код ответа — отдельное требование REQ-SEC-01 (известный баг)"
    ),
    "REQ-CITY-01": _planned(
        "6.2",
        "Список городов без токена: 200, элементы {city, lat, lng}. Сейчас запрос городов — только предусловие "
        "теста словарей",
    ),
    "REQ-SEC-03": _planned(
        "6.2",
        "Текст ошибки при невалидном токене не содержит текстов парсера JWT. Требование нарушается (Q-API-09) — "
        "нужна запись в known_bugs.py. Стоп-слова assert_secure_error это нарушение не ловят",
    ),
    "DISC-03": _planned(
        "6.2",
        "Вход через API тем же email с заглавными буквами, с которым прошла регистрация. Расхождение "
        "подтверждено (Q-API-06) — нужна запись в known_bugs.py",
    ),
    "DISC-08": _planned(
        "6.2",
        "Поиск через API с page и size: параметры игнорируются (Q-API-02). Что считать ожидаемым результатом "
        "при расхождении фронтенда и Swagger — решить до написания теста",
    ),
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
        "Клиентская пагинация: page и size в URL, 10, 20 и 50 карточек на странице. Тесты поиска только "
        "пользуются size=50, но число карточек не проверяют",
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

        if (entry.category == PLANNED) != (entry.pr is not None):
            raise ValueError(f"Исключение покрытия {item_id!r}: pr указывается для категории planned и только для неё.")
        if entry.pr is not None and entry.pr not in PLANNED_PRS:
            raise ValueError(
                f"Исключение покрытия {item_id!r}: неизвестный шаг плана {entry.pr!r}. "
                f"Допустимые: {', '.join(PLANNED_PRS)}."
            )


_validate_registry()
