import os
import time
import pytest
import allure
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from dotenv import load_dotenv
from selenium.webdriver.support.events import EventFiringWebDriver
from utils.listener import IlCarroListener
from api.car_api import IlCarroAPI
from pages.login_page import LoginPage
from data.data_generator import UserGenerator

load_dotenv()


@pytest.fixture
def driver():
    is_headless = os.getenv('HEADLESS_MODE', 'false').lower() == 'true'
    is_ci = os.environ.get('CI') == 'true'
    use_selenoid = os.getenv('USE_SELENOID', 'false').lower() == 'true'

    session_id = None
    driver_instance = None

    if is_ci:
        options = ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        driver_instance = webdriver.Chrome(options=options)

    else:
        if use_selenoid:
            print("\n[INFO] Маршрутизация в изолированный Docker-контейнер (Selenoid)...")
            options = ChromeOptions()
            options.set_capability("browserName", "chrome")
            options.set_capability("browserVersion", "128.0")
            options.set_capability("selenoid:options", {
                "enableVNC": True,
                "enableVideo": True,
            })

            hub_url = os.getenv("SELENOID_HUB_URL", "http://localhost:4444/wd/hub")

            # Ожидание готовности Selenoid
            for attempt in range(5):
                try:
                    driver_instance = webdriver.Remote(
                        command_executor=hub_url,
                        options=options
                    )
                    break
                except Exception as e:
                    if attempt == 4:
                        raise e
                    print(f"\n[INFO] Ждем пробуждения Selenoid (попытка {attempt + 1})...")
                    time.sleep(2)

            session_id = driver_instance.session_id

        else:
            try:
                options = ChromeOptions()
                if is_headless:
                    options.add_argument('--headless=new')
                options.add_argument('--window-size=1920,1080')
                driver_instance = webdriver.Chrome(options=options)
            except Exception as e:
                print(f"\n[WARNING] Chrome не запустился. Причина: {e}")
                options = EdgeOptions()
                if is_headless:
                    options.add_argument('--headless')
                options.add_argument('--window-size=1920,1080')
                driver_instance = webdriver.Edge(options=options)

    if not is_headless and not use_selenoid:
        driver_instance.maximize_window()
    elif use_selenoid:
        driver_instance.maximize_window()

    driver_instance.set_page_load_timeout(30)
    decorated_driver = EventFiringWebDriver(driver_instance, IlCarroListener())

    yield decorated_driver

    if use_selenoid:
        time.sleep(1.5)

    decorated_driver.quit()

    # === ИНТЕГРАЦИЯ ВИДЕО В ALLURE ===
    if use_selenoid and session_id:
        video_dir = os.getenv("VIDEO_DIR", r"C:\selenoid\video")
        video_path = os.path.join(video_dir, f"{session_id}.mp4")

        for attempt in range(10):
            if os.path.exists(video_path):
                time.sleep(1)
                try:
                    with open(video_path, "rb") as video_file:
                        allure.attach(
                            video_file.read(),
                            name="Видео прохождения теста",
                            attachment_type=allure.attachment_type.MP4
                        )
                    print("\n[INFO] Видео успешно прикреплено к отчету!")
                    break
                except Exception as e:
                    print(f"\n[WARNING] Файл заблокирован, пробуем снова. Ошибка: {e}")
            time.sleep(1)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == 'call' and report.failed:
        # Учитываем, что фикстура может называться driver или authenticated_driver
        driver = item.funcargs.get('driver') or item.funcargs.get('authenticated_driver')
        if driver:
            test_name = item.name.replace("/", "_").replace("::", "_")
            allure.attach(
                driver.get_screenshot_as_png(),
                name=f"Скриншот ошибки: {test_name}",
                attachment_type=allure.attachment_type.PNG
            )


@pytest.fixture
def temp_user():
    """Создает уникального пользователя через API для полной изоляции тестов."""
    user = UserGenerator.get_random_user()
    api = IlCarroAPI()

    with allure.step(f"Setup Fixture: Генерация временного пользователя {user.email}"):
        response = api.register(user.email, user.password)
        assert response.status_code == 200, f"Не удалось зарегистрировать временного юзера: {response.text}"

    # Возвращаем словарь: и данные юзера, и готовую (авторизованную) API-сессию
    return {"user": user, "api": api}


@pytest.fixture
def auth_api(temp_user):
    """
    Фикстура-адаптер: берет изолированного API-клиента из песочницы (temp_user)
    и отдает его чистым API-тестам. Никаких изменений в самих тестах не потребуется!
    """
    return temp_user["api"]


@pytest.fixture
def authenticated_driver(driver, temp_user):
    """Автоматически логинится через UI под свежесозданным временным юзером."""
    with allure.step("Setup Fixture: Автоматическая UI-авторизация (Sandbox)"):
        login_page = LoginPage(driver)
        login_page.open()

        # Берем данные уникального юзера из песочницы
        user = temp_user["user"]

        login_page.login(user.email, user.password)
        login_page.is_logout_button_visible()

    return driver


def pytest_make_parametrize_id(val):
    return str(val)


@pytest.fixture
def page(context):
    """
    Переопределяем базовую фикстуру Playwright для авто-сохранения видео в Allure.
    Она прозрачно заменяет стандартный page во всех тестах.
    """
    page = context.new_page()
    yield page

    # 1. Запоминаем путь к видео (если запись была включена флагом --video=on)
    video_path = page.video.path() if page.video else None

    # 2. КРИТИЧЕСКИЙ ШАГ: Принудительно закрываем страницу и контекст.
    # Если этого не сделать, Playwright не успеет финализировать и сохранить .mp4 файл.
    page.close()
    context.close()

    # 3. Прикрепляем готовый файл в Allure
    if video_path and os.path.exists(video_path):
        allure.attach.file(
            video_path,
            name="Видео Playwright",
            attachment_type=allure.attachment_type.MP4
        )