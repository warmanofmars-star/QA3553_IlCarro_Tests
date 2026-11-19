"""
Индекс ID из docs/requirements/requirements.md.

Реестры known_bugs.py, observations.py и coverage_exceptions.py сверяют свои ссылки с этим индексом,
поэтому опечатка в ID (или ссылка на требование, которого нет в документе) ловится при сборе тестов.
Матрица трассируемости (scripts/coverage_matrix.py) берёт отсюда же формулировки и разделы:
requirements.md остаётся единственным местом, где записаны требования.

Разбор — функция от пути: тем же разбором читается английский перевод requirements.en.md
(матрица на английском и scripts/check_translations.py). Реестры по-прежнему читают только оригинал.
Модуль — только stdlib, без config.py: его импортирует и консольный скрипт проверки переводов,
которому не нужны зависимости проекта и чтение .env.
"""

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

REQUIREMENTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "requirements"
REQUIREMENTS_FILE = REQUIREMENTS_DIR / "requirements.md"
REQUIREMENTS_EN_FILE = REQUIREMENTS_DIR / "requirements.en.md"

# Строка таблицы: ID в первой колонке, формулировка — во второй:
# "| REQ-AUTH-01 | Регистрация … | SW: … | соблюдается |", "| DISC-02 | …", "| OBS-03 | …"
_ROW_PATTERN = re.compile(r"^\|\s*((?:REQ|DISC|OBS)-[A-Z0-9]+(?:-[A-Z0-9]+)*)\s*\|\s*(.*?)\s*\|")
# Заголовок раздела с таблицей: "### 1.1 Регистрация и вход (AUTH)", "## 3. Расхождения источников (DISC)"
_HEADING_PATTERN = re.compile(r"^#{2,3}\s+(.+?)\s*$")


@dataclass(frozen=True)
class RequirementItem:
    id: str  # REQ-…, DISC-… или OBS-…
    text: str  # вторая колонка таблицы: формулировка требования или суть расхождения/наблюдения
    section: str  # заголовок раздела, в котором стоит строка
    # Вся строка таблицы как есть: проверка перевода сверяет по ней ссылки Q-…, код и «Факт»
    line: str = ""

    @property
    def cells(self) -> tuple[str, ...]:
        """Ячейки строки таблицы без крайних «|». Экранированных «\\|» в таблицах требований нет."""
        return tuple(cell.strip() for cell in self.line.strip().strip("|").split("|"))


@cache
def parse_requirement_items(path: Path = REQUIREMENTS_FILE) -> tuple[RequirementItem, ...]:
    """Все пункты файла требований в порядке документа. Нет файла, нет ID или ID повторяется — ошибка."""
    if not path.is_file():
        raise FileNotFoundError(
            f"Не найден файл требований: {path}. "
            "Реестры известных багов, наблюдений и исключений покрытия сверяют ссылки с ним."
        )
    items: list[RequirementItem] = []
    section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if heading := _HEADING_PATTERN.match(line):
            section = heading.group(1)
        elif row := _ROW_PATTERN.match(line):
            items.append(RequirementItem(id=row.group(1), text=row.group(2), section=section, line=line))
    if not items:
        raise ValueError(f"В {path} не найдено ни одного ID (REQ-…, DISC-…, OBS-…): формат таблиц изменился?")
    ids = [item.id for item in items]
    duplicates = sorted({item_id for item_id in ids if ids.count(item_id) > 1})
    if duplicates:
        raise ValueError(f"В {path} повторяются ID: {', '.join(duplicates)}")
    return tuple(items)


def requirement_items() -> tuple[RequirementItem, ...]:
    """Все пункты оригинала requirements.md в порядке документа."""
    return parse_requirement_items(REQUIREMENTS_FILE)


@cache
def requirement_ids() -> frozenset[str]:
    """Множество всех ID из requirements.md."""
    return frozenset(item.id for item in requirement_items())
