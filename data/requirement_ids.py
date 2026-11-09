"""
Индекс ID из docs/requirements/requirements.md.

Реестры known_bugs.py и observations.py сверяют свои ссылки с этим индексом, поэтому опечатка
в ID (или ссылка на требование, которого нет в документе) ловится при сборе тестов.
"""

import re
from functools import lru_cache

from config import PROJECT_ROOT

REQUIREMENTS_FILE = PROJECT_ROOT / "docs" / "requirements" / "requirements.md"

# ID стоит в первой колонке таблицы: "| REQ-AUTH-01 |", "| DISC-02 |", "| OBS-03 |"
_ID_PATTERN = re.compile(r"^\|\s*((?:REQ|DISC|OBS)-[A-Z0-9]+(?:-[A-Z0-9]+)*)\s*\|", re.MULTILINE)


@lru_cache(maxsize=1)
def requirement_ids() -> frozenset[str]:
    """Множество всех ID из requirements.md. Нет файла или в нём нет ID — ошибка, а не пустое множество."""
    if not REQUIREMENTS_FILE.is_file():
        raise FileNotFoundError(
            f"Не найден файл требований: {REQUIREMENTS_FILE}. "
            "Реестры известных багов и наблюдений сверяют ссылки с ним."
        )
    ids = frozenset(_ID_PATTERN.findall(REQUIREMENTS_FILE.read_text(encoding="utf-8")))
    if not ids:
        raise ValueError(
            f"В {REQUIREMENTS_FILE} не найдено ни одного ID (REQ-…, DISC-…, OBS-…): формат таблиц изменился?"
        )
    return ids
