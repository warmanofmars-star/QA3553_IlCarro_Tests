"""
Журналы прогона в формате JSON Lines: запись по файлу на процесс и строгое чтение.

Журналы (фабрика машин — utils/car_cleanup.py, пользователи — utils/user_journal.py) пишут сразу
несколько процессов прогона — воркеры xdist. Общий файл в режиме append на Windows не атомарен:
дозапись там — «перейти в конец, записать», и соседний процесс успевает записать между этими
шагами. Записи затираются молча, изредка остаются пустые или склеенные строки
(research/race_journal_append.py, docs/requirements/research-log.md). Поэтому:
  * каждый процесс пишет свой файл <имя>_<воркер>.jsonl (gw0, gw1…; без xdist — main),
    по образцу logs/pytest_gw0.log; у файла один писатель, гонки нет;
  * одна запись — один вызов write со строкой вместе с переводом строки;
  * итог собирается из всех файлов журнала, а испорченная строка — ошибка JournalError с именем
    файла и номером строки: молча пропущенная запись сделала бы итог неверным.
"""

import json
from pathlib import Path

from config import settings


class JournalError(Exception):
    """Журнал прогона нельзя разобрать: итог по нему был бы неверным."""


def append_record(directory: Path, name: str, record: dict) -> None:
    """Дописывает запись в файл журнала текущего процесса. OSError обрабатывает вызывающий."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}_{settings.xdist_worker_id}.jsonl"
    # newline="\n": без него Windows превратит перевод строки в \r\n, и файлы с Linux и Windows разойдутся
    with open(path, "a", encoding="utf-8", newline="\n") as journal:
        journal.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_records(directory: Path, name: str, required: frozenset[str]) -> list[dict]:
    """Все записи журнала из файлов всех процессов. Испорченная строка — JournalError.

    Испорченной считается строка, которая не разбирается как объект JSON или в которой нет
    полей required. Пустая строка тоже испорчена: запись никогда не пишет пустых строк.
    """
    records: list[dict] = []
    for path in sorted(directory.glob(f"{name}_*.jsonl")):
        with open(path, encoding="utf-8", newline="") as journal:
            for number, line in enumerate(journal, start=1):
                text = line.removesuffix("\n")
                try:
                    record = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise JournalError(f"{path.name}, строка {number}: не JSON ({exc.msg}): {text[:120]!r}") from exc
                if not isinstance(record, dict) or not required <= record.keys():
                    missing = sorted(required - record.keys()) if isinstance(record, dict) else "запись не объект"
                    raise JournalError(f"{path.name}, строка {number}: нет полей {missing}: {text[:120]!r}")
                records.append(record)
    return records
