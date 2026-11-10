"""
Индекс ID из docs/requirements/requirements.md.

Реестры known_bugs.py, observations.py и coverage_exceptions.py сверяют свои ссылки с этим индексом,
поэтому опечатка в ID (или ссылка на требование, которого нет в документе) ловится при сборе тестов.
Матрица трассируемости (scripts/coverage_matrix.py) берёт отсюда же формулировки и разделы:
requirements.md остаётся единственным местом, где записаны требования.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

from config import PROJECT_ROOT

REQUIREMENTS_FILE = PROJECT_ROOT / "docs" / "requirements" / "requirements.md"

# Строка таблицы: ID в первой колонке, формулировка — во второй:
# "| REQ-AUTH-01 | Регистрация … | SW: … | соблюдается |", "| DISC-02 | …", "| OBS-03 | …"
_ROW_PATTERN = re.compile(r"^\|\s*((?:REQ|DISC|OBS)-[A-Z0-9]+(?:-[A-Z0-9]+)*)\s*\|\s*(.*?)\s*\|")
# Заголовок раздела с таблицей: "### 1.1 Регистрация и вход (AUTH)", "## 3. Расхождения источников (DISC)"
_HEADING_PATTERN = re.compile(r"^#{2,3}\s+(.+?)\s*$")


@dataclass(frozen=True)
class RequirementItem:
    id: str  # REQ-…, DISC-… или OBS-…
    text: str  # вторая колонка таблицы: формулировка требования или суть расхождения/наблюдения
    section: str  # заголовок раздела requirements.md, в котором стоит строка


@lru_cache(maxsize=1)
def requirement_items() -> tuple[RequirementItem, ...]:
    """Все пункты requirements.md в порядке документа. Нет файла, нет ID или ID повторяется — ошибка."""
    if not REQUIREMENTS_FILE.is_file():
        raise FileNotFoundError(
            f"Не найден файл требований: {REQUIREMENTS_FILE}. "
            "Реестры известных багов, наблюдений и исключений покрытия сверяют ссылки с ним."
        )
    items: list[RequirementItem] = []
    section = ""
    for line in REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines():
        if heading := _HEADING_PATTERN.match(line):
            section = heading.group(1)
        elif row := _ROW_PATTERN.match(line):
            items.append(RequirementItem(id=row.group(1), text=row.group(2), section=section))
    if not items:
        raise ValueError(
            f"В {REQUIREMENTS_FILE} не найдено ни одного ID (REQ-…, DISC-…, OBS-…): формат таблиц изменился?"
        )
    ids = [item.id for item in items]
    duplicates = sorted({item_id for item_id in ids if ids.count(item_id) > 1})
    if duplicates:
        raise ValueError(f"В {REQUIREMENTS_FILE} повторяются ID: {', '.join(duplicates)}")
    return tuple(items)


@lru_cache(maxsize=1)
def requirement_ids() -> frozenset[str]:
    """Множество всех ID из requirements.md."""
    return frozenset(item.id for item in requirement_items())
