import logging
import os
import sys
import glob
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class ColoredFormatter(logging.Formatter):
    GREEN = "\x1b[32;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    FORMAT_TEMPLATE = "[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s"

    FORMATS = {
        logging.DEBUG: FORMAT_TEMPLATE,
        logging.INFO: GREEN + FORMAT_TEMPLATE + RESET,
        logging.WARNING: YELLOW + FORMAT_TEMPLATE + RESET,
        logging.ERROR: RED + FORMAT_TEMPLATE + RESET,
        logging.CRITICAL: BOLD_RED + FORMAT_TEMPLATE + RESET
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)


def clean_old_logs(log_dir, keep_last=30):
    # Увеличили лимит до 30 (этого хватит ровно на 10 запусков в 3 потока)
    if not os.path.exists(log_dir):
        return

    files = glob.glob(os.path.join(log_dir, "*.log"))
    files.sort(key=os.path.getmtime)

    while len(files) > keep_last:
        oldest_file = files.pop(0)
        try:
            os.remove(oldest_file)
        except OSError:
            pass


# ГЛОБАЛЬНАЯ ПЕРЕМЕННАЯ ДЛЯ ХРАНЕНИЯ ФАЙЛА ТЕКУЩЕГО ПРОЦЕССА
_PROCESS_LOG_FILE = None


def get_logger(name="IlCarro"):
    global _PROCESS_LOG_FILE

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # 1. Проверяем воркеров (есть ли переменная окружения)
    is_worker = "PYTEST_XDIST_WORKER" in os.environ

    # 2. Проверяем Мастер-процесс (читаем команду запуска из терминала на наличие флага -n)
    is_xdist_master = "-n" in sys.argv or any(arg.startswith("-n") for arg in sys.argv)

    # Итоговый вердикт
    is_xdist = is_worker or is_xdist_master

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter())

    if os.getenv('ENABLE_CONSOLE_LOGS', 'true').lower() == 'true':
        logger.addHandler(console_handler)

    # ЗАПИСЬ В ФАЙЛ ТОЛЬКО ЕСЛИ ЭТО НЕ ПАРАЛЛЕЛЬНЫЙ ЗАПУСК
    if not is_xdist:
        project_root = Path(__file__).resolve().parent.parent
        log_dir = project_root / "logs"
        log_dir.mkdir(exist_ok=True)

        clean_old_logs(str(log_dir), keep_last=15)

        if _PROCESS_LOG_FILE is None:
            current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            # Теперь PID в названии не нужен, так как файл всегда один
            _PROCESS_LOG_FILE = str(log_dir / f"run_{current_time}.log")

        file_formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler = logging.FileHandler(_PROCESS_LOG_FILE, encoding='utf-8')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger