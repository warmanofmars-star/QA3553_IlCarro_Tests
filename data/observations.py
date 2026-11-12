"""
Реестр наблюдений: плохое поведение приложения, для которого в requirements.md нет требования.

Чем наблюдение отличается от известного бага (data/known_bugs.py):
  * known_bug — нарушение требования REQ-… или расхождение источников DISC-…. Это дефект.
  * observation — запись OBS-… в requirements.md: требования нет, ожидание обосновано общими
    принципами (логика предметной области, UX). Источник ожидания уже записан в requirements.md,
    поэтому здесь его не дублируем. Решение — за пользователем: принять ожидание как требование
    или принять текущее поведение.

    @observation("NONSENSE_CAR_VALUES")
    def test_...(...):

Механика та же, что у known_bug: strict=True (исправили — прогон упадёт с XPASS, запись надо убрать),
raises=AssertionError (сбой окружения остаётся FAILED), ref сверяется с requirements.md при импорте
и должен начинаться с OBS-.
"""

from dataclasses import dataclass

import pytest

from data.requirement_ids import requirement_ids


@dataclass(frozen=True)
class Observation:
    ref: str  # ID наблюдения в requirements.md (OBS-…)
    description: str  # фактическое поведение приложения


OBSERVATIONS: dict[str, Observation] = {
    "NONSENSE_CAR_VALUES": Observation(
        ref="OBS-03",
        description=(
            "API сохраняет машину с бессмысленными значениями полей: отрицательная цена, цена 0, seats 0, "
            'year "abc", fuel "banana"'
        ),
    ),
    "STALE_SESSION_UI_AFTER_401": Observation(
        ref="OBS-05",
        description=(
            "После ответа 401 фронт удаляет токен, но оставляет пользователя на той же странице, и «Log out» "
            "остаётся в навигации до перезагрузки (Q-UI-13, Q-UI-17)"
        ),
    ),
    "SEARCH_CITY_CASE_SENSITIVE": Observation(
        ref="OBS-01",
        description=(
            "Поиск чувствителен к регистру города: введённые вручную «sderot» и «SDEROT» находят 0 машин, "
            "«Sderot» — все машины города (Q-API-02, Q-UI-23)"
        ),
    ),
    "INVALID_DATES_ACCEPTED": Observation(
        ref="OBS-02",
        description=(
            "Поиск и бронирование с прошедшими датами и с концом раньше начала отвечают 200, бронирование — "
            "«Car booked successfully!» (Q-API-01, Q-API-02, Q-API-18)"
        ),
    ),
    "SEARCH_OUTCOME_NOT_SHOWN": Observation(
        ref="OBS-04",
        description=(
            "Пустая выдача и сбой поиска (ответ 500, обрыв сети) ничем не обозначены: ни карточек, ни сообщения "
            "(Q-UI-12, Q-UI-24)"
        ),
    ),
    "GUEST_OPENS_CAR_FORM": Observation(
        ref="OBS-06",
        description=(
            "Гость открывает /let-car-work: форма на месте, переход на вход не происходит; отправка заканчивается "
            "«Failed to submit car» (Q-UI-13)"
        ),
    ),
    "CAR_SUBMIT_ERROR_WITHOUT_CAUSE": Observation(
        ref="OBS-07",
        description=(
            "При любой ошибке отправки машины на экране один текст «Failed to submit car»: причина из ответа "
            "сервера не показывается (Q-UI-03, Q-UI-04, Q-UI-26)"
        ),
    ),
    "CARD_PRICE_ROUNDED": Observation(
        ref="OBS-08",
        description="Цена на карточке округляется до одного знака: сохранённые 1234.56 показаны как «1234.6» (Q-UI-12)",
    ),
    "REGISTER_URL_UNCHANGED": Observation(
        ref="OBS-09",
        description="После регистрации и закрытия окна «Registered» URL остаётся /register (Q-UI-09, Q-UI-25)",
    ),
    "PREV_MONTH_BUTTON_ENABLED": Observation(
        ref="OBS-10",
        description=(
            "Кнопка «предыдущий месяц» в текущем месяце доступна (атрибута disabled нет), но клик ничего не меняет "
            "(Q-UI-11)"
        ),
    ),
    "RUSSIAN_TEXTS_IN_ENGLISH_UI": Observation(
        ref="OBS-11",
        description=(
            "Интерфейс на английском, а страницы машины и профиля показывают русские тексты: «Не удалось загрузить "
            "машину», «Не удалось загрузить профиль» (Q-UI-01, Q-UI-18)"
        ),
    ),
}


def _validate_registry() -> None:
    """Сверяет ref всех записей с requirements.md. Вызывается один раз при импорте модуля."""
    known_ids = requirement_ids()
    for key, item in OBSERVATIONS.items():
        if not item.ref.startswith("OBS-"):
            raise ValueError(
                f"Наблюдение {key!r}: ссылка {item.ref!r} должна начинаться с OBS-. "
                "Для REQ-…/DISC-… есть реестр data/known_bugs.py."
            )
        if item.ref not in known_ids:
            raise ValueError(f"Наблюдение {key!r}: ID {item.ref!r} нет в docs/requirements/requirements.md.")


_validate_registry()


def observation(key: str) -> pytest.MarkDecorator:
    """Маркер xfail для наблюдения из реестра.

    Работает и как декоратор теста, и внутри pytest.param(..., marks=observation("...")).
    Тег @allure.tag с ID наблюдения ставится на тест отдельно.
    """
    if key not in OBSERVATIONS:
        raise KeyError(f"Неизвестное наблюдение {key!r}. Добавь его в data/observations.py со ссылкой на OBS-….")
    item = OBSERVATIONS[key]
    return pytest.mark.xfail(
        strict=True,
        raises=AssertionError,
        reason=f"[{key}] {item.description}. Наблюдение {item.ref}, не нарушение требования",
    )
