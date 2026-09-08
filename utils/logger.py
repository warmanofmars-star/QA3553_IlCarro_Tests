import logging
import os
import sys
from dotenv import load_dotenv

load_dotenv()

COLORS = {
    'WARNING': '\033[93m',
    'INFO': '\033[94m',
    'DEBUG': '\033[92m',
    'CRITICAL': '\033[91m',
    'ERROR': '\033[91m',
    'ENDC': '\033[0m'
}


class ColorFormatter(logging.Formatter):
    def format(self, record):
        log_message = super().format(record)
        return f"{COLORS.get(record.levelname, '')}{log_message}{COLORS['ENDC']}"


def get_logger(name="IlCarro"):
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter_file = logging.Formatter('%(asctime)s - [%(process)d] - %(levelname)s - %(message)s',
                                       datefmt='%Y-%m-%d %H:%M:%S')

    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Уникальный файл лога для каждого процесса при параллельном запуске
    file_handler = logging.FileHandler(f'logs/test_run_{os.getpid()}.log', encoding='utf-8')
    file_handler.setFormatter(formatter_file)
    logger.addHandler(file_handler)

    if os.getenv('ENABLE_CONSOLE_LOGS', 'true').lower() == 'true':
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            ColorFormatter('%(asctime)s - [%(process)d] - %(levelname)s - %(message)s', datefmt='%H:%M:%S'))
        logger.addHandler(console_handler)

    return logger