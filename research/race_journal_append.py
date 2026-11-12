"""
Воспроизведение гонки записи в журналах прогона (logs/car_factory*.jsonl, logs/registered_users*.jsonl).

Вопрос: портятся ли строки журнала, когда несколько процессов (как воркеры xdist) одновременно
дописывают записи. Скрипт фиксирует факт — сколько строк не разбирается как JSON, — без оценок.

Как устроено:
  * PROCESSES процессов стартуют одновременно (барьер) и каждый пишет RECORDS записей в каждый
    журнал ТЕМИ ЖЕ функциями, что и тесты: CarCleanup._write_journal и record_registration;
  * у каждого процесса своё имя воркера (PYTEST_XDIST_WORKER=gw0, gw1…), как у воркеров xdist;
  * журналы пишутся во временный каталог, а не в logs/: каталог журналов модулей подменяется
    в каждом процессе до записи;
  * затем все *.jsonl каталога разбираются построчно: строка, которая не разбирается как JSON
    или не содержит полей записи, считается испорченной; недостача целых записей до
    PROCESSES * RECORDS — потерянные записи.

Запуск: python research/race_journal_append.py [--processes 4] [--records 5000]
Сеть и .env скрипту не нужны.
"""

import argparse
import json
import multiprocessing
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Поля, без которых запись журнала не годится для итога прогона
CAR_FIELDS = {"owner", "test", "registered", "created", "deleted", "deleted_by_test", "failed", "left", "worker"}
USER_FIELDS = {"email", "source", "worker"}


def _writer(worker_id: str, journal_dir: str, records: int, barrier) -> None:
    """Процесс-«воркер»: пишет records записей в оба журнала функциями проекта."""
    # Имя воркера config.py читает при импорте, поэтому окружение — до импорта модулей проекта
    os.environ["PYTEST_XDIST_WORKER"] = worker_id
    sys.path.insert(0, str(ROOT))
    from utils import car_cleanup, user_journal

    car_cleanup.JOURNAL_FILE = Path(journal_dir) / car_cleanup.JOURNAL_FILE.name
    user_journal.USER_JOURNAL_FILE = Path(journal_dir) / user_journal.USER_JOURNAL_FILE.name

    barrier.wait()  # все процессы начинают писать одновременно
    for number in range(records):
        email = f"race_{worker_id}_{number}@example.com"
        report = car_cleanup.CleanupReport(
            owner=email,
            test=f"tests/test_race.py::test_{worker_id}_{number}",
            registered=1,
            created=1,
            deleted=1,
        )
        car_cleanup.CarCleanup._write_journal(report)
        user_journal.record_registration(email, user_journal.API_CLIENT)


def _count(journal_dir: Path) -> dict:
    """Разбирает все журналы каталога: сколько строк целых и сколько испорчено."""
    totals = {"files": 0, "car_ok": 0, "user_ok": 0, "broken": 0, "examples": []}
    for path in sorted(journal_dir.glob("*.jsonl")):
        totals["files"] += 1
        fields = CAR_FIELDS if path.name.startswith("car_factory") else USER_FIELDS
        key = "car_ok" if fields is CAR_FIELDS else "user_ok"
        # newline="" — видеть строки как есть: лишний \r тоже след порчи
        with open(path, encoding="utf-8", errors="replace", newline="") as journal:
            for number, line in enumerate(journal, start=1):
                text = line.rstrip("\n").rstrip("\r")
                try:
                    record = json.loads(text)
                    ok = isinstance(record, dict) and fields <= record.keys()
                except json.JSONDecodeError:
                    ok = False
                if ok:
                    totals[key] += 1
                else:
                    totals["broken"] += 1
                    if len(totals["examples"]) < 3:
                        totals["examples"].append(f"{path.name}:{number}: {text[:120]!r}")
    return totals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--processes", type=int, default=4)
    parser.add_argument("--records", type=int, default=5000)
    args = parser.parse_args()

    expected = args.processes * args.records
    with tempfile.TemporaryDirectory(prefix="race_journal_") as tmp:
        barrier = multiprocessing.Barrier(args.processes)
        workers = [
            multiprocessing.Process(target=_writer, args=(f"gw{index}", tmp, args.records, barrier))
            for index in range(args.processes)
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        if any(worker.exitcode != 0 for worker in workers):
            print("Процесс записи завершился с ошибкой:", [worker.exitcode for worker in workers])
            return 2
        totals = _count(Path(tmp))

    print(f"Процессов: {args.processes}, записей на процесс в каждый журнал: {args.records}")
    print(f"Файлов журнала: {totals['files']}")
    print(f"Целых записей фабрики машин: {totals['car_ok']} из {expected}")
    print(f"Целых записей пользователей: {totals['user_ok']} из {expected}")
    print(f"Испорченных строк: {totals['broken']}")
    # Потерянная запись — та, что затёрта записью соседа: разбору она не мешает, но итог занижает
    print(f"Потеряно записей: фабрика машин {expected - totals['car_ok']}, пользователи {expected - totals['user_ok']}")
    for example in totals["examples"]:
        print(f"  пример: {example}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
