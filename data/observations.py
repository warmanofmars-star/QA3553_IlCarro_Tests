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
