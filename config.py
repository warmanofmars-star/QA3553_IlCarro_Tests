"""
Единая точка конфигурации проекта.

ПРАВИЛО: переменные окружения читаются ТОЛЬКО в этом файле и load_dotenv() вызывается ТОЛЬКО здесь.
Все остальные модули берут настройки так:

    from config import settings
    url = f"{settings.api_url}/v1/cars"

Откуда берутся значения (по убыванию приоритета):
  1. Реальные переменные окружения (Docker Compose, GitHub Actions, оболочка).
  2. Файл .env в корне проекта (удобно для локального запуска).
  3. Значения по умолчанию, указанные ниже.

load_dotenv() не перезаписывает уже существующие переменные окружения, поэтому значение
из CI или из командной строки всегда побеждает значение из локального .env.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Корень проекта = папка, в которой лежит этот файл
PROJECT_ROOT = Path(__file__).resolve().parent

# Явный путь к .env: так не важно, из какой папки запущен pytest
load_dotenv(PROJECT_ROOT / ".env")


# Переменные окружения всегда строки. Функции ниже приводят их к нужному типу и одинаково
# обрабатывают случай «не задана или пустая».

def _env_str(name: str, default: str | None = None) -> str | None:
    """Строка; пустое значение считается незаданным. Без default незаданная переменная даёт None."""
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_bool(name: str, default: bool) -> bool:
    """Булево значение: true/1/yes/on (в любом регистре) считаются True."""
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("true", "1", "yes", "on")


def _env_int(name: str, default: int) -> int:
    """Целое число. При мусоре падаем сразу и с понятным сообщением, а не посреди прогона."""
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Переменная окружения {name} должна быть целым числом, получено: {value!r}") from None


@dataclass(frozen=True)  # frozen: настройки нельзя случайно изменить во время прогона
class Settings:
    # --- Адреса тестируемого приложения ---
    ui_url: str  # фронтенд
    api_url: str  # бэкенд

    # --- Запуск браузеров ---
    headless: bool  # запуск без окна браузера (локально)
    is_ci: bool  # запуск на «голом» раннере GitHub Actions: браузер локально, без Grid
    use_grid: bool  # браузеры в Docker через Selenium Grid
    grid_url: str  # адрес хаба Selenium Grid
    video_dir: str | None  # где лежат видео сессий Grid (None — видео к отчёту не прикладываем)

    # --- Таймауты ---
    pw_timeout_ms: int  # ожидания Playwright, миллисекунды

    # --- Логи ---
    enable_console_logs: bool  # дублировать логи в консоль
    is_xdist_worker: bool  # процесс — воркер pytest-xdist (его задаёт сам xdist, не пользователь)
    xdist_worker_id: str  # имя воркера xdist (gw0, gw1…) или "main" вне воркера

    @classmethod
    def from_env(cls) -> "Settings":
        """Собирает настройки из окружения. Вызывается один раз при импорте модуля."""
        return cls(
            # rstrip("/"): чтобы f"{api_url}/v1/..." никогда не давал двойной слэш
            ui_url=_env_str("UI_BASE_URL", "https://icarro-v1.netlify.app").rstrip("/"),
            api_url=_env_str("API_BASE_URL", "https://ilcarro-backend.herokuapp.com").rstrip("/"),
            headless=_env_bool("HEADLESS_MODE", False),
            is_ci=_env_bool("CI", False),
            use_grid=_env_bool("USE_GRID", False),
            # rstrip("/"): к адресу дописывается /status, двойной слэш не нужен
            grid_url=_env_str("GRID_URL", "http://localhost:4444").rstrip("/"),
            # По умолчанию видео нет: узлы Grid пишут его в Docker-том, доступный только контейнеру
            # с тестами (там VIDEO_DIR=/app/video задаёт docker-compose.yml)
            video_dir=_env_str("VIDEO_DIR"),
            pw_timeout_ms=_env_int("PW_TIMEOUT", 10000),
            enable_console_logs=_env_bool("ENABLE_CONSOLE_LOGS", True),
            is_xdist_worker=os.environ.get("PYTEST_XDIST_WORKER") is not None,
            xdist_worker_id=os.environ.get("PYTEST_XDIST_WORKER") or "main",
        )


# Единственный экземпляр настроек на весь проект
settings = Settings.from_env()
