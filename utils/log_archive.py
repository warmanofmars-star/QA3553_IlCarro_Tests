"""
Архив логов и журналов прошлых прогонов: logs/archive/<YYYYMMDD-HHMMSS>/.

Раньше главный процесс при старте удалял logs/*.log и журналы прогона, и разобрать упавший прогон
после следующего запуска было нечем. Теперь файлы прошлого прогона переносятся в архив; хранятся
последние KEEP_ARCHIVES архивов, старшие удаляются.

Архивирует только главный процесс (без xdist — единственный, с xdist — контроллер): он стартует
раньше воркеров. Воркер перенёс бы в архив файлы соседей, которые уже пишут текущий прогон, —
та же гонка, что с общим файлом журнала (utils/run_journal.py).

Итоги журналов (run_journal.read_records) берут только файлы верхнего уровня logs/, поэтому архив
в итог текущего прогона не попадает и испорченная строка в архиве прогон не роняет.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

ARCHIVE_DIR_NAME = "archive"
KEEP_ARCHIVES = 5
# Что оставляет прогон в logs/: логи pytest (pytest.log, pytest_gw0.log…) и журналы *.jsonl
RUN_FILE_PATTERNS = ("*.log", "*.jsonl")
STAMP_FORMAT = "%Y%m%d-%H%M%S"


def _archive_name(archive_root: Path, files: list[Path]) -> Path:
    """Папка архива по времени последней записи прошлого прогона: по нему архив легко сопоставить с прогоном.

    Два прогона в одну секунду (короткий набор подряд) получают суффикс -1, -2…, а не сливаются в одну папку.
    """
    stamp = datetime.fromtimestamp(max(path.stat().st_mtime for path in files)).strftime(STAMP_FORMAT)
    taken = [_order(path)[1] for path in archive_root.glob(f"{stamp}*") if _order(path)[0] == stamp]
    # Суффикс — после наибольшего занятого, а не первый свободный: имя, освобождённое ротацией,
    # встало бы в начало порядка, и новейший архив удалился бы первым
    return archive_root / (f"{stamp}-{max(taken) + 1}" if taken else stamp)


def _order(path: Path) -> tuple[str, int]:
    """Ключ порядка архива «YYYYMMDD-HHMMSS[-N]»: время, затем суффикс числом (строкой «-10» встал бы раньше «-2»)."""
    stamp_length = len("YYYYMMDD-HHMMSS")
    suffix = path.name[stamp_length + 1 :]
    return path.name[:stamp_length], int(suffix) if suffix.isdigit() else 0


def _prune(archive_root: Path, keep: int) -> None:
    """Удаляет архивы старше последних keep. Имена — время, поэтому порядок имён и есть порядок прогонов."""
    archives = sorted((path for path in archive_root.iterdir() if path.is_dir()), key=_order)
    for old in archives[:-keep]:
        shutil.rmtree(old)
        logger.info(f"Удалён старый архив логов: {old.name}")


def archive_previous_run(log_dir: Path, keep: int = KEEP_ARCHIVES) -> Path | None:
    """Переносит файлы прошлого прогона из log_dir в новый архив и оставляет keep последних архивов.

    Возвращает папку архива или None, если переносить было нечего. Сбой переноса не глушится:
    оставшийся в logs/ журнал попал бы в итог текущего прогона и исказил бы его.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    files = sorted({path for pattern in RUN_FILE_PATTERNS for path in log_dir.glob(pattern) if path.is_file()})
    archive_root = log_dir / ARCHIVE_DIR_NAME
    target = None
    if files:
        target = _archive_name(archive_root, files)
        target.mkdir(parents=True)
        for path in files:
            shutil.move(path, target / path.name)
    if archive_root.is_dir():
        _prune(archive_root, keep)
    return target
