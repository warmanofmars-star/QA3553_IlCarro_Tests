"""
Фабрика WebDriver: создание браузера для всех режимов запуска.

Режимы (выбираются настройками из config.py):
  * Selenium Grid (USE_GRID=true)  — браузер на узле Grid в Docker, с записью видео.
  * Локально      (USE_GRID=false) — браузер на этой машине; headless при HEADLESS_MODE=true
                                     или на «голом» CI-раннере (CI=true).

Раньше всё это жило в фикстуре driver в conftest.py, и опции каждого браузера повторялись
в трёх ветках (CI, удалённый браузер, локально). Теперь они собираются в одном месте — _build_options().
"""

import logging
import os

import allure
import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait

from config import settings

logger = logging.getLogger(__name__)

# Единственный список поддерживаемых браузеров: его берут и --browser_name в conftest.py,
# и проверка в create_driver(). Значение — имя браузера в протоколе WebDriver (browserName):
# так Grid подписывает слоты узлов в /status, по нему ищем нужный узел.
GRID_BROWSER_NAMES = {"chrome": "chrome", "firefox": "firefox", "edge": "MicrosoftEdge"}
SUPPORTED_BROWSERS = tuple(GRID_BROWSER_NAMES)

WINDOW_WIDTH, WINDOW_HEIGHT = 1920, 1080
PAGE_LOAD_TIMEOUT = 30  # секунды на полную загрузку страницы

# Ожидания Grid (секунды). WebDriverWait здесь — просто опрос условия с таймаутом, драйвер ему не нужен.
# Хаб ждём недолго: не отвечает — значит, скорее всего, не запущен, и тянуть время незачем.
# Узлы регистрируются в хабе через несколько секунд после старта контейнеров (depends_on в compose
# ждёт только запуска контейнера, а не готовности), поэтому узел нужного браузера ждём дольше.
GRID_HUB_TIMEOUT = 10
GRID_NODE_TIMEOUT = 60

# Сколько ждать, пока узел допишет видео после закрытия сессии
VIDEO_WAIT_TIMEOUT = 20


class GridUnavailableError(RuntimeError):
    """Grid не готов принять сессию: хаб не отвечает или нет узла нужного браузера."""


# ==========================================
# Опции браузеров
# ==========================================
def _build_options(browser: str, headless: bool, ci: bool):
    """Собирает опции браузера. Единственное место, где они настраиваются."""
    if browser == "firefox":
        options = FirefoxOptions()
        if headless:
            options.add_argument("--headless")
        # У Firefox свой синтаксис размера окна
        options.add_argument(f"--width={WINDOW_WIDTH}")
        options.add_argument(f"--height={WINDOW_HEIGHT}")
        return options

    # Edge построен на Chromium, поэтому аргументы у него те же, что у Chrome
    options = EdgeOptions() if browser == "edge" else ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument(f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}")
    if ci:
        # Без этих флагов Chromium часто падает на CI-раннерах: нет песочницы ядра,
        # маленький /dev/shm, нет GPU
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
    return options


# ==========================================
# Готовность Grid
# ==========================================
def _grid_browsers(status: dict) -> set[str]:
    """Какие браузеры сейчас предлагают работающие узлы Grid (по слотам из /status)."""
    browsers = set()
    for node in status.get("value", {}).get("nodes", []):
        if node.get("availability", "UP") != "UP":
            continue  # узел уходит (DRAINING) или недоступен (DOWN)
        for slot in node.get("slots", []):
            name = slot.get("stereotype", {}).get("browserName")
            if name:
                browsers.add(name)
    return browsers


def wait_for_grid(browser: str) -> None:
    """Ждёт, пока Grid сможет создать сессию браузера, иначе бросает GridUnavailableError.

    Проверяем не только «хаб отвечает», но и «есть узел именно этого браузера»: хаб без узлов
    отвечает на /status, но запрос сессии повиснет в его очереди на 5 минут (таймаут Grid
    по умолчанию) и упадёт невнятной ошибкой.
    """
    status_url = f"{settings.grid_url}/status"
    expected = GRID_BROWSER_NAMES[browser]
    start_hint = f"COMPOSE_PROFILES={browser} docker compose up -d selenium-hub {browser}"

    logger.info(f"Проверка Selenium Grid: {status_url}")
    try:
        # Достаточно любого HTTP-ответа: здесь важно, что хаб слушает. «is not None» нужен потому,
        # что Response с кодом 4xx/5xx ложен в bool и WebDriverWait принял бы его за «ещё нет»
        WebDriverWait(
            None, GRID_HUB_TIMEOUT, poll_frequency=0.5, ignored_exceptions=(requests.RequestException,)
        ).until(lambda _: requests.get(status_url, timeout=3) is not None)
    except TimeoutException:
        raise GridUnavailableError(
            f"Selenium Grid недоступен: {status_url} не ответил за {GRID_HUB_TIMEOUT} с. "
            f"Запусти Grid ({start_hint}) или запускай браузер локально: USE_GRID=false."
        ) from None

    available: set[str] = set()

    def node_registered(_) -> bool:
        nonlocal available
        available = _grid_browsers(requests.get(status_url, timeout=3).json())
        return expected in available

    logger.info(f"Ожидание узла {browser} в Selenium Grid")
    try:
        WebDriverWait(
            None, GRID_NODE_TIMEOUT, poll_frequency=1, ignored_exceptions=(requests.RequestException, ValueError)
        ).until(node_registered)
    except TimeoutException:
        registered = ", ".join(sorted(available)) or "ни одного"
        raise GridUnavailableError(
            f"В Selenium Grid ({settings.grid_url}) за {GRID_NODE_TIMEOUT} с не появился узел браузера "
            f"{browser} (зарегистрированы: {registered}). Узлы запускаются по профилю compose: "
            f"COMPOSE_PROFILES={browser} и тот же браузер в BROWSER ({start_hint})."
        ) from None


# ==========================================
# Создание драйвера
# ==========================================
def _create_remote_driver(browser: str) -> WebDriver:
    """Браузер на узле Selenium Grid. Готовность Grid проверяет вызывающий код (wait_for_grid)."""
    options = _build_options(browser, headless=False, ci=False)
    # Запись видео этой сессии встроенным рекордером узла (SE_RECORD_VIDEO в docker-compose.yml).
    # Capability se:name не задаём: тогда файл называется <id сессии>.mp4 и после теста
    # его легко найти (attach_session_video)
    options.set_capability("se:recordVideo", True)
    logger.info(f"Создание сессии в Selenium Grid, браузер: {browser}")
    return webdriver.Remote(command_executor=settings.grid_url, options=options)


def _create_local_driver(browser: str, headless: bool) -> WebDriver:
    """Браузер на этой машине или на CI-раннере."""
    options = _build_options(browser, headless=headless, ci=settings.is_ci)
    driver_classes = {"chrome": webdriver.Chrome, "firefox": webdriver.Firefox, "edge": webdriver.Edge}
    logger.info(f"Локальный запуск: {browser}, headless={headless}")
    try:
        return driver_classes[browser](options=options)
    except Exception as error:
        logger.warning(f"Браузер {browser} не запустился. Причина: {error}")
        raise


def create_driver(browser: str) -> WebDriver:
    """Создаёт и настраивает WebDriver для текущего режима запуска.

    Grid имеет приоритет: если USE_GRID=true, браузер всегда удалённый.
    """
    if browser not in SUPPORTED_BROWSERS:
        raise ValueError(f"Неизвестный браузер {browser!r}, доступны: {', '.join(SUPPORTED_BROWSERS)}")

    if settings.use_grid:
        driver = _create_remote_driver(browser)
        headless = False  # на узле Grid браузер всегда с окном, иначе на видео будет пустой экран
    else:
        headless = settings.headless or settings.is_ci  # на CI-раннере экрана нет
        driver = _create_local_driver(browser, headless)

    # В headless размер окна уже задан опциями; maximize там ничего не даёт
    if not headless:
        driver.maximize_window()
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    return driver


# ==========================================
# Видео сессии
# ==========================================
def attach_session_video(session_id: str, browser: str) -> None:
    """Прикрепляет к Allure видео сессии, записанное узлом Grid."""
    if not settings.video_dir:
        # Локальный запуск против Grid: видео лежит в Docker-томе, с этой машины его не достать
        logger.debug("VIDEO_DIR не задан — видео к отчёту не прикладываем")
        return

    video_path = os.path.join(settings.video_dir, f"{session_id}.mp4")
    video = _read_finished_video(video_path)
    if video is None:
        logger.warning(f"Видео ({browser}) не готово за {VIDEO_WAIT_TIMEOUT} с: {video_path}")
        return
    allure.attach(video, name=f"Видео прохождения теста ({browser})", attachment_type=allure.attachment_type.MP4)
    logger.info(f"Видео ({browser}) прикреплено к отчёту")


def _read_finished_video(video_path: str) -> bytes | None:
    """Ждёт, пока узел допишет видео сессии, и возвращает его содержимое (None — не дождались).

    Рекордер дописывает mp4 уже после закрытия сессии: файл появляется не сразу и какое-то время
    растёт. Готовым считается непустой файл, размер которого не изменился между двумя опросами.
    Нет файла или он ещё занят записью (PermissionError на Windows) — не готов.
    """
    last_size = -1

    def finished(_):
        nonlocal last_size
        size = os.path.getsize(video_path)
        if size == 0 or size != last_size:
            last_size = size
            return False
        with open(video_path, "rb") as video_file:
            return video_file.read()

    try:
        return WebDriverWait(None, VIDEO_WAIT_TIMEOUT, poll_frequency=1, ignored_exceptions=(OSError,)).until(finished)
    except TimeoutException:
        return None
