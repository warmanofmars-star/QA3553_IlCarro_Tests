"""
Пробы шага 6.3a (вопросы Q-UI-15 … Q-UI-19): что отправляет фронтенд и как он ведёт себя
при подменённых ответах.

Отличие от explore_ui.py: запросы, которые меняют данные (POST /v1/cars, PUT /v1/user/profile),
перехватываются через page.route и до бэкенда не доходят — машин и фото скрипт не создаёт.
Тела подменённых ответов написаны скриптом; там, где у приложения есть настоящий ответ, взят его
формат (POST /v1/cars → 200 {"message": "Car added successfully"}, Q-UI-05).

Скрипт фиксирует факты, оценок в нём нет. Запуск: python research/explore_ui_interception.py --run 63
Лог: research/evidence/explore_ui_interception_run63.log
Пользователь один (probe_<uuid>@example.com), город — Sderot (малое число машин, Q-API-14).
"""

import base64
import json
import sys
import traceback
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from common import (  # noqa: E402
    API_BASE_URL,
    REG,
    ROOT,
    UI_BASE_URL,
    FactLog,
    mask,
    new_serial,
    print_stats,
    register_user,
    run_name,
    short,
)

LOG = FactLog(run_name("explore_ui_interception"))
TIMEOUT_MS = 20000
CITY = "Sderot"
CAR_ADDED = {"message": "Car added successfully"}
PHOTO_FILE = ROOT / "assets" / "car.jpg"
PHOTO_LINK = "https://example.com/probe-car.jpg"


# ---------------------------------------------------------------- наблюдение за страницей


def api_path(url: str) -> str:
    return urlsplit(url).path


def is_api(request, method: str, path: str) -> bool:
    return request.url.startswith(API_BASE_URL) and request.method == method and api_path(request.url) == path


def ls_dump(page) -> str:
    """Содержимое localStorage; значение token не печатается."""
    data = page.evaluate("() => Object.fromEntries(Object.entries(localStorage))")
    if not data:
        return "localStorage пуст"
    parts = []
    for key, value in sorted(data.items()):
        if key.lower() == "token" or str(value).startswith("eyJ"):
            parts.append(f"{key}=<hidden>(длина {len(str(value))})")
        else:
            parts.append(f"{key}={short(str(value), 80)}")
    return "localStorage: " + "; ".join(parts)


def nav_state(page) -> str:
    return "кнопка Log out есть" if page.get_by_role("button", name="Log out").count() else "кнопки Log out нет"


def main_text(page, limit: int = 300) -> str:
    """Видимый текст области main (без навигации и подвала)."""
    text = " | ".join(x.strip() for x in page.locator("main").inner_text().splitlines() if x.strip())
    return short(text, limit)


def status_texts(page) -> str:
    """Тексты блоков результата формы: .success[role=status] и .error[role=alert]."""
    return short(page.locator("[role=status], [role=alert]").all_inner_texts(), 200)


def describe_body(body: dict) -> str:
    """Тело запроса: длинные строки (image) — началом и длиной."""
    shown = {k: (f"{v[:30]}...(длина {len(v)})" if isinstance(v, str) and len(v) > 60 else v) for k, v in body.items()}
    return short(shown, 600)


# ---------------------------------------------------------------- действия в UI


def new_page(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.set_default_timeout(TIMEOUT_MS)
    return ctx, page


def login_ui(page, email: str, password: str):
    page.goto(f"{UI_BASE_URL}/login")
    page.fill("input[name=username]", email)
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    page.get_by_role("link", name="OK", exact=True).click()
    page.get_by_role("button", name="Log out").wait_for(state="visible")


def fill_car_form(page, serial: str, *, fuel: str = "Petrol", extras: bool = False):
    REG.label_car(serial)
    page.fill("#city", CITY)
    page.locator(f'[data-testid="city-option"][data-value="{CITY}"]').first.click()
    page.fill("[name=manufacture]", "ProbeMake")
    page.fill("[name=model]", "ProbeModel")
    page.fill("[name=year]", "2020")
    page.select_option("[name=fuel]", label=fuel)
    if extras:
        page.select_option("[name=gear]", label="Automatic")
        page.select_option("[name=wheelsDrive]", label="AWD")
        page.fill("[name=doors]", "4")
    page.fill("[name=seats]", "4")
    page.fill("[name=carClass]", "Economy")
    page.fill("[name=serialNumber]", serial)
    page.fill("[name=pricePerDay]", "150")
    page.fill("[name=about]", "research probe")


def submit_intercepted(page, status: int, body: dict, label: str):
    """Отправляет форму машины; POST /v1/cars перехвачен и получает подменённый ответ.

    Возвращает тело запроса (dict) или None. Сколько запросов поймано — пишется в лог: вывод
    о содержимом запроса без пойманного запроса был бы пустым.
    """
    caught = []

    def handler(route):
        if route.request.method != "POST":
            route.fallback()
            return
        caught.append(route.request)
        route.fulfill(status=status, json=body)

    page.route("**/v1/cars", handler)
    try:
        with page.expect_response(lambda r: is_api(r.request, "POST", "/v1/cars")) as info:
            page.click("button[type=submit]")
        LOG.fact(
            f"[{label}] POST /v1/cars: перехвачено запросов {len(caught)}; браузер получил HTTP {info.value.status} "
            f"(подмена, до бэкенда запрос не дошёл)"
        )
    finally:
        page.unroute("**/v1/cars", handler)
    return json.loads(caught[0].post_data) if caught and caught[0].post_data else None


# ---------------------------------------------------------------- вопросы


def q_ui_15_fuel_values(page):
    LOG.header("Q-UI-15", "Форма машины: значение fuel в запросе для каждого варианта списка (ответ подменён)")
    for fuel in ("Petrol", "Diesel", "Hybrid", "Electric"):
        page.goto(f"{UI_BASE_URL}/let-car-work")
        fill_car_form(page, new_serial("RU"), fuel=fuel, extras=True)
        LOG.fact(
            f"[{fuel}] значения в форме: fuel={page.input_value('[name=fuel]')!r}, "
            f"gear={page.input_value('[name=gear]')!r}, wheelsDrive={page.input_value('[name=wheelsDrive]')!r}, "
            f"doors={page.input_value('[name=doors]')!r}"
        )
        body = submit_intercepted(page, 200, CAR_ADDED, fuel)
        if body is None:
            continue
        LOG.fact(f"[{fuel}] ключи тела запроса: {sorted(body)}")
        LOG.fact(f"[{fuel}] fuel в запросе: {body.get('fuel')!r}")
        for key in ("gear", "wheelsDrive", "doors", "features"):
            LOG.fact(f"[{fuel}] поле {key} в теле: {'есть, значение ' + repr(body[key]) if key in body else 'нет'}")
        page.wait_for_function("() => document.querySelector('[name=manufacture]').value === ''")
        LOG.fact(
            f"[{fuel}] после ответа 200: поле Make пустое; блоки role=status/alert: {status_texts(page)}; "
            f"URL={mask(page.url)}"
        )


def q_ui_16_photo(page):
    LOG.header("Q-UI-16", "Форма машины: фото ссылкой и файлом JPEG — что уходит в поле image (ответ подменён)")
    page.goto(f"{UI_BASE_URL}/let-car-work")
    fill_car_form(page, new_serial("RU"))
    page.fill("[name=image]", PHOTO_LINK)
    body = submit_intercepted(page, 200, CAR_ADDED, "ссылка")
    if body is not None:
        LOG.fact(f"[ссылка] в поле введено {PHOTO_LINK!r}; image в запросе: {body.get('image')!r}")

    page.goto(f"{UI_BASE_URL}/let-car-work")
    fill_car_form(page, new_serial("RU"))
    raw = PHOTO_FILE.read_bytes()
    page.set_input_files("#photo-file", str(PHOTO_FILE))
    page.wait_for_function("() => document.querySelector('[name=image]').value.startsWith('data:')")
    body = submit_intercepted(page, 200, CAR_ADDED, "файл")
    if body is not None:
        image = body.get("image") or ""
        prefix, _, encoded = image.partition(",")
        try:
            same = base64.b64decode(encoded) == raw
        except ValueError:
            same = False
        LOG.fact(
            f"[файл] assets/car.jpg, {len(raw)} байт; image в запросе: начало {image[:40]!r}, длина {len(image)}; "
            f"префикс до запятой: {prefix!r}; base64 после запятой декодируется в байты файла: {same}"
        )
        LOG.fact(f"[файл] тело запроса: {describe_body(body)}")


def q_ui_17_substituted_401(page):
    LOG.header("Q-UI-17", "Сессия: настоящий вход, затем подменённый ответ 401 на POST /v1/cars")
    page.goto(f"{UI_BASE_URL}/let-car-work")
    LOG.fact(f"до отправки: URL={mask(page.url)}; {nav_state(page)}; {ls_dump(page)}")
    fill_car_form(page, new_serial("RU"))
    fake_401 = {"status": 401, "error": "Unauthorized", "message": "mocked unauthorized", "path": "/v1/cars"}
    body = submit_intercepted(page, 401, fake_401, "401")
    LOG.fact(f"запрос ушёл с телом: {body is not None}")
    page.locator("[role=alert]").wait_for(state="visible")
    LOG.fact(f"после ответа 401: URL={mask(page.url)}; блоки role=status/alert: {status_texts(page)}")
    LOG.fact(f"после ответа 401: {nav_state(page)}; {ls_dump(page)}")
    page.reload()
    page.locator("#city").wait_for(state="visible")
    LOG.fact(f"после перезагрузки страницы: URL={mask(page.url)}; {nav_state(page)}; {ls_dump(page)}")


def q_ui_18_profile(browser, page, email, password):
    LOG.header("Q-UI-18", "Страница /profile: запросы фронта (залогиненный, гость, подменённый ответ)")
    # Перезагрузка в Q-UI-17 оставила страницу без токена — входим заново тем же пользователем
    login_ui(page, email, password)

    with page.expect_event(
        "requestfailed", lambda r: is_api(r, "GET", "/v1/user/profile"), timeout=TIMEOUT_MS
    ) as failed:
        page.goto(f"{UI_BASE_URL}/profile")
    request = failed.value
    LOG.fact(
        f"[залогиненный] запрос {request.method} {api_path(request.url)} оборван браузером: {request.failure}; "
        f"заголовок Authorization в запросе: {'есть' if request.headers.get('authorization') else 'нет'}"
    )
    page.get_by_text("Загрузка...").wait_for(state="hidden")
    LOG.fact(f"[залогиненный] URL={mask(page.url)}; текст main: {main_text(page)}; {nav_state(page)}")

    # Подмена GET: тело придумано скриптом (у приложения такого ответа нет) — только чтобы дойти до PUT
    fake_profile = {"firstName": "Probe", "lastName": "User", "username": "probe@example.com"}
    sent_put = []
    dialogs = []

    def profile_handler(route):
        if route.request.method == "GET":
            route.fulfill(status=200, json=fake_profile)
        elif route.request.method == "PUT":
            sent_put.append(route.request)
            route.fulfill(status=200, json=fake_profile)
        else:
            route.fallback()

    def on_dialog(dialog):
        dialogs.append(f"{dialog.type}: {dialog.message}")
        dialog.accept()

    page.route("**/v1/user/profile", profile_handler)
    page.on("dialog", on_dialog)
    try:
        page.goto(f"{UI_BASE_URL}/profile")
        page.get_by_role("button", name="Сохранить").wait_for(state="visible")
        LOG.fact(f"[подмена GET 200 {json.dumps(fake_profile)}] текст main: {main_text(page)}")
        LOG.fact(f"[подмена GET] подписи полей: {page.locator('.form-row label').all_inner_texts()}")
        with page.expect_response(lambda r: is_api(r.request, "PUT", "/v1/user/profile")):
            page.get_by_role("button", name="Сохранить").click()
        LOG.fact(
            f"[подмена GET] клик «Сохранить»: перехвачено PUT /v1/user/profile — {len(sent_put)} "
            f"(до бэкенда не дошёл); тело: {short(sent_put[0].post_data or '-', 200) if sent_put else '-'}"
        )
        page.get_by_role("button", name="Сохранить").wait_for(state="visible")
        LOG.fact(f"[подмена GET] диалоги браузера: {dialogs}")
    finally:
        page.remove_listener("dialog", on_dialog)
        page.unroute("**/v1/user/profile", profile_handler)

    ctx, guest = new_page(browser)
    try:
        api_requests = []
        guest.on("request", lambda r: api_requests.append(r) if r.url.startswith(API_BASE_URL) else None)
        guest.goto(f"{UI_BASE_URL}/profile")
        guest.wait_for_url("**/login")
        LOG.fact(
            f"[гость] /profile → URL={mask(guest.url)}; {ls_dump(guest)}; "
            f"запросов к API: {[f'{r.method} {api_path(r.url)}' for r in api_requests]}"
        )
    finally:
        ctx.close()


def q_ui_19_listed_car(browser):
    LOG.header("Q-UI-19", "Страница машины: чужая машина из выдачи (скрипт машину не создаёт)")
    ctx, page = new_page(browser)
    try:
        page.goto(f"{UI_BASE_URL}/search")
        page.fill("#city", CITY)
        page.locator(f'[data-testid="city-option"][data-value="{CITY}"]').first.click()
        page.click("#dates")
        page.locator(".rdrDayToday").click()
        page.locator(".rdrDayToday").click()
        with page.expect_response(lambda r: is_api(r.request, "POST", "/v1/cars/search")) as info:
            page.click("button[type=submit]")
        cars = info.value.json().get("cars", [])
        cards = page.locator("a.car-container")
        cards.first.wait_for(state="visible")
        LOG.fact(
            f"поиск {CITY}: HTTP {info.value.status}, машин в ответе {len(cars)}; "
            f"карточек на странице {cards.count()}; URL={mask(page.url)}"
        )
        href = cards.first.get_attribute("href")
        serial = href.rsplit("/", 1)[-1]
        REG.label_car(serial)
        car = next((c for c in cars if c.get("serialNumber") == serial), None)
        LOG.fact(f"первая карточка: href={href!r}; машина с таким serialNumber в ответе поиска: {car is not None}")
        LOG.fact(f"текст первой карточки: {short(cards.first.inner_text().replace(chr(10), ' | '), 200)}")
        api_requests = []
        page.on("request", lambda r: api_requests.append(r) if r.url.startswith(API_BASE_URL) else None)
        with page.expect_event("requestfailed", lambda r: r.url.startswith(API_BASE_URL)) as failed:
            cards.first.click()
        request = failed.value
        page.get_by_text("Загрузка...").wait_for(state="hidden")
        LOG.fact(f"после клика: URL={mask(page.url)}")
        LOG.fact(f"запросы к API после клика: {[f'{r.method} {api_path(r.url)}' for r in api_requests]}")
        LOG.fact(f"запрос {request.method} {api_path(request.url)} оборван браузером: {request.failure}")
        LOG.fact(f"текст main: {main_text(page)}")
        if car:
            text = page.locator("main").inner_text()
            LOG.fact(
                f"на странице есть model машины: {bool(car.get('model')) and car['model'] in text}; "
                f"manufacture: {bool(car.get('manufacture')) and car['manufacture'] in text}"
            )
    finally:
        ctx.close()


# ---------------------------------------------------------------- запуск


def main():
    LOG.line("# Факты: explore_ui_interception.py")
    LOG.line(f"UI_BASE_URL: {UI_BASE_URL}")
    try:
        email, password, _token, response = register_user()
        LOG.fact(f"временный пользователь: регистрация HTTP {response.status_code}")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx, page = new_page(browser)
            try:
                login_ui(page, email, password)
                steps = [
                    lambda: q_ui_15_fuel_values(page),
                    lambda: q_ui_16_photo(page),
                    lambda: q_ui_17_substituted_401(page),
                    lambda: q_ui_18_profile(browser, page, email, password),
                    lambda: q_ui_19_listed_car(browser),
                ]
                for step in steps:
                    try:
                        step()
                    except Exception as exc:
                        first = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
                        LOG.fact(f"вопрос не завершён: {type(exc).__name__}: {short(first, 250)}")
                        traceback.print_exc()
            finally:
                ctx.close()
                browser.close()
    finally:
        # Машин скрипт не создаёт: POST /v1/cars перехвачен. Статистика — для единообразия с другими скриптами
        print_stats(LOG)


if __name__ == "__main__":
    main()
