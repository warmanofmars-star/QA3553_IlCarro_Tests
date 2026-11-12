"""
Пробы шага 6.3b (вопросы Q-UI-20 … Q-UI-26): валидация формы машины, подсказка города, пагинация,
регистр города в поиске, сбой поиска, URL после регистрации, текст ошибки отправки машины.

Запросы, которые меняют данные (POST /v1/cars, POST регистрации), перехвачены через page.route
и до бэкенда не доходят. Тела подменённых ответов написаны скриптом; там, где у приложения есть
настоящий ответ, взят его формат (регистрация → {"accessToken": …}, Q-API-06; ошибки POST /v1/cars —
Q-UI-03, Q-UI-04). Вход — токеном в localStorage, без запроса входа.

Скрипт фиксирует факты, оценок в нём нет. Запуск: python research/explore_ui_rest.py --run 63b
Только отдельные вопросы: python research/explore_ui_rest.py --run 63b2 --only Q-UI-24,Q-UI-26
Лог: research/evidence/explore_ui_rest_run63b.log
Пользователь один (probe_<uuid>@example.com), город — Sderot (малое число машин, Q-API-14).
"""

import json
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from common import (  # noqa: E402
    API_BASE_URL,
    UI_BASE_URL,
    FactLog,
    new_email,
    new_serial,
    print_stats,
    register_user,
    run_name,
    short,
)

LOG = FactLog(run_name("explore_ui_rest"))
TIMEOUT_MS = 20000
CITY = "Sderot"
FIELDS = {
    "manufacture": "ProbeMake",
    "model": "ProbeModel",
    "year": "2020",
    "seats": "4",
    "carClass": "Economy",
    "serialNumber": None,  # заполняется новым номером
    "pricePerDay": "150",
}


def api_path(url: str) -> str:
    return urlsplit(url).path


def is_api(request, method: str, path: str) -> bool:
    return request.url.startswith(API_BASE_URL) and request.method == method and api_path(request.url) == path


def new_page(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.set_default_timeout(TIMEOUT_MS)
    return ctx, page


def restore_session(page, token: str):
    page.goto(f"{UI_BASE_URL}/login")
    page.evaluate(
        "(t) => { localStorage.setItem('token', t); localStorage.setItem('tokenType', 'Bearer'); }",
        token,
    )


def block_writes(page, caught: list):
    """Любой не-GET запрос к API обрывается: скрипт ничего не создаёт на бэкенде."""

    def handler(route):
        if route.request.method in ("GET", "HEAD", "OPTIONS"):
            route.fallback()
            return
        caught.append(f"{route.request.method} {api_path(route.request.url)}")
        route.abort()

    page.route(lambda url: url.startswith(API_BASE_URL), handler)


def roles_text(page) -> str:
    return short(page.locator("[role=status], [role=alert]").all_inner_texts(), 200)


def main_text(page, limit: int = 200) -> str:
    text = " | ".join(x.strip() for x in page.locator("main").inner_text().splitlines() if x.strip())
    return short(text, limit)


# ---------------------------------------------------------------- форма машины


def fill_valid_car_form(page):
    page.fill("#city", CITY)
    page.locator(f'[data-testid="city-option"][data-value="{CITY}"]').first.click()
    for name, value in FIELDS.items():
        page.fill(f"[name={name}]", value or new_serial())
    page.select_option("[name=fuel]", label="Petrol")


def field_error(page, name: str) -> str:
    errors = page.locator(f"[name={name}] ~ div.error")
    return errors.first.inner_text() if errors.count() else "<нет>"


def submit_state(page) -> str:
    return "Submit недоступна" if page.locator("button[type=submit]").is_disabled() else "Submit доступна"


def q_ui_20_car_form_validation(browser, token):
    LOG.header("Q-UI-20", "Форма машины: проверка полей до отправки (пустое поле, Seats и Price меньше 1)")
    ctx, page = new_page(browser)
    caught: list = []
    try:
        block_writes(page, caught)
        restore_session(page, token)
        cases = [(name, "") for name in (*FIELDS, "fuel")]
        cases += [("seats", "0"), ("pricePerDay", "0"), ("pricePerDay", "-5"), ("seats", "-1")]
        for name, value in cases:
            page.goto(f"{UI_BASE_URL}/let-car-work")
            fill_valid_car_form(page)
            before = submit_state(page)
            if name == "fuel":
                page.select_option("[name=fuel]", value="")
            else:
                page.fill(f"[name={name}]", value)
            page.locator(f"[name={name}]").focus()
            page.locator("h1.title").click()  # снять фокус: поле становится touched
            LOG.fact(
                f"{name}={value!r}: со всеми полями — {before}; после изменения поля — {submit_state(page)}; "
                f"ошибка под полем: {field_error(page, name)!r}"
            )
        # Город: выбран из подсказки, затем стёрт
        page.goto(f"{UI_BASE_URL}/let-car-work")
        fill_valid_car_form(page)
        before = submit_state(page)
        page.fill("#city", "")
        page.locator("h1.title").click()
        page.locator("[data-testid=city-dropdown]").wait_for(state="hidden")
        city_errors = page.locator("[data-testid=city-autocomplete] ~ div.error").count()
        LOG.fact(
            f"city стёрт после выбора: со всеми полями — {before}; после — {submit_state(page)}; "
            f"значение #city={page.input_value('#city')!r}; блоков ошибки у города: {city_errors}"
        )
        LOG.fact(f"оборвано пишущих запросов: {len(caught)} {caught}")
    finally:
        ctx.close()


# ---------------------------------------------------------------- подсказка города


def suggestions(page) -> list:
    return page.locator("[data-testid=city-option]").all_inner_texts()


def q_ui_21_city_suggestions(browser):
    LOG.header("Q-UI-21", "Подсказка города на /search: число и состав вариантов")
    ctx, page = new_page(browser)
    try:
        page.goto(f"{UI_BASE_URL}/search")
        page.click("#city")
        page.locator("[data-testid=city-option]").first.wait_for()
        LOG.fact(f"фокус в пустом поле: вариантов {len(suggestions(page))}: {suggestions(page)}")
        for text in ("a", "Kiryat", "kiryat", "sderot", "Zzz"):
            page.fill("#city", text)
            options = suggestions(page)
            LOG.fact(f"введено {text!r}: вариантов {len(options)}: {options}")
    finally:
        ctx.close()


# ---------------------------------------------------------------- поиск


def pick_dates(page):
    """Диапазон: сегодня — завтра (два клика в календаре)."""
    page.click("#dates")
    page.locator(".rdrDayToday").click()
    tomorrow = date.today() + timedelta(days=1)
    if tomorrow.month != date.today().month:
        page.click(".rdrNextButton")
    page.locator(f"button.rdrDay:not(.rdrDayPassive):not(.rdrDayDisabled) >> text='{tomorrow.day}'").first.click()


def run_search(page, city: str, *, choose_option: bool):
    page.goto(f"{UI_BASE_URL}/search")
    page.fill("#city", city)
    if choose_option:
        page.locator(f'[data-testid="city-option"][data-value="{city}"]').first.click()
    else:
        page.keyboard.press("Tab")
        page.locator("[data-testid=city-dropdown]").wait_for(state="hidden")
    pick_dates(page)
    page.locator("h1.title").click()
    with page.expect_response(lambda r: is_api(r.request, "POST", "/v1/cars/search")) as info:
        page.click("button[type=submit]")
    return info.value


def query(page) -> dict:
    return {k: v[0] for k, v in parse_qs(urlsplit(page.url).query).items()}


def cards(page) -> int:
    return page.locator("a.car-container").count()


def q_ui_22_pagination(browser):
    LOG.header("Q-UI-22", "Пагинация выдачи: URL, число карточек, варианты Rows per page, Next")
    ctx, page = new_page(browser)
    try:
        resp = run_search(page, CITY, choose_option=True)
        total = len(resp.json().get("cars", []))
        page.locator("a.car-container").first.wait_for()
        select = page.locator(".search-results select")
        LOG.fact(f"ответ поиска: HTTP {resp.status}, машин {total}; URL query={query(page)}; карточек {cards(page)}")
        LOG.fact(
            f"Rows per page: варианты {select.locator('option').all_inner_texts()}; выбрано {select.input_value()}; "
            f"подпись: {short(page.locator('.search-results').inner_text().splitlines()[-3:], 120)}"
        )
        page.click("button[title=Next]")
        page.wait_for_url("**page=1**")
        LOG.fact(f"после Next: URL query={query(page)}; карточек {cards(page)}")
        for size in ("20", "50", "10"):
            select.select_option(size)
            page.wait_for_url(f"**size={size}**")
            LOG.fact(f"Rows per page={size}: URL query={query(page)}; карточек {cards(page)}")
    finally:
        ctx.close()


def q_ui_23_city_case(browser):
    LOG.header("Q-UI-23", "Поиск городом в другом регистре, введённым вручную")
    ctx, page = new_page(browser)
    try:
        for city, choose in ((CITY, True), (CITY.lower(), False), (CITY.upper(), False)):
            resp = run_search(page, city, choose_option=choose)
            sent = json.loads(resp.request.post_data or "{}").get("city")
            total = len(resp.json().get("cars", []))
            page.wait_for_load_state("networkidle")
            LOG.fact(
                f"введено {city!r} ({'из подсказки' if choose else 'вручную'}): в запросе city={sent!r}; "
                f"HTTP {resp.status}; машин {total}; карточек {cards(page)}"
            )
    finally:
        ctx.close()


def q_ui_24_search_failures(browser):
    LOG.header("Q-UI-24", "Поиск: пустая выдача и сбой запроса (ответ подменён или оборван)")
    ctx, page = new_page(browser)
    try:
        resp = run_search(page, "Beersheba", choose_option=True)
        page.wait_for_load_state("networkidle")
        LOG.fact(
            f"Beersheba: HTTP {resp.status}, машин {len(resp.json().get('cars', []))}; карточек {cards(page)}; "
            f"блоков role=status/alert: {roles_text(page)}; блок результатов: "
            f"{page.locator('.search-results-card').count()}"
        )
        for label, action in (
            ("подменён 500", lambda route: route.fulfill(status=500, json={"status": 500, "message": "probe"})),
            ("оборван", lambda route: route.abort()),
        ):
            # Обработчик маршрута с двумя параметрами Playwright вызывает как (route, request),
            # поэтому действие передаётся замыканием, а не аргументом по умолчанию
            handler = route_handler(action)
            page.route("**/v1/cars/search", handler)
            page.goto(f"{UI_BASE_URL}/search")
            page.fill("#city", CITY)
            page.locator(f'[data-testid="city-option"][data-value="{CITY}"]').first.click()
            pick_dates(page)
            page.locator("h1.title").click()
            with page.expect_request(lambda r: is_api(r, "POST", "/v1/cars/search")) as info:
                page.click("button[type=submit]")
            info.value.response()
            page.locator("button[type=submit]", has_text="Yalla!").wait_for()
            LOG.fact(
                f"поиск {label}: карточек {cards(page)}; блоков role=status/alert: {roles_text(page)}; "
                f"кнопка: {page.locator('button[type=submit]').inner_text()!r}; URL query={query(page)}"
            )
            page.unroute("**/v1/cars/search", handler)
    finally:
        ctx.close()


# ---------------------------------------------------------------- регистрация и отправка машины


def route_handler(action):
    return lambda route: action(route)


def post_handler(status: int, body: dict):
    def handler(route):
        if route.request.method != "POST":
            route.fallback()
            return
        route.fulfill(status=status, json=body)

    return handler


def q_ui_25_register_url(browser):
    LOG.header("Q-UI-25", "URL после регистрации (POST регистрации перехвачен, ответ подменён на 200)")
    ctx, page = new_page(browser)
    caught: list = []
    try:
        block_writes(page, caught)
        sent = []

        def handler(route):
            sent.append(route.request)
            route.fulfill(status=200, json={"accessToken": "probe.substituted.token"})

        page.route("**/v1/user/registration/usernamepassword", handler)
        page.goto(f"{UI_BASE_URL}/register")
        page.fill("[name=firstName]", "Probe")
        page.fill("[name=lastName]", "User")
        page.fill("[name=username]", new_email())
        page.fill("[name=password]", "Probe2026ab")
        page.check("#terms-of-use")
        page.click("button[type=submit]")
        page.locator("h3", has_text="Registered").wait_for()
        window = short(page.locator(".modal-content").inner_text(), 120)
        LOG.fact(f"перехвачено запросов регистрации: {len(sent)}; окно: {window}")
        LOG.fact(f"при открытом окне: path={urlsplit(page.url).path}")
        page.get_by_role("button", name="OK").click()
        page.locator("h3", has_text="Registered").wait_for(state="hidden")
        has_logout = page.get_by_role("button", name="Log out").count()
        LOG.fact(
            f"после OK: path={urlsplit(page.url).path}; кнопка Log out: {has_logout}; "
            f"token в localStorage: {page.evaluate('() => localStorage.getItem(`token`) !== null')}"
        )
        LOG.fact(f"оборвано пишущих запросов мимо подмены: {len(caught)} {caught}")
    finally:
        ctx.close()


def q_ui_26_submit_error_text(browser, token):
    LOG.header("Q-UI-26", "Текст ошибки отправки машины при подменённых ответах POST /v1/cars")
    ctx, page = new_page(browser)
    caught: list = []
    try:
        block_writes(page, caught)
        restore_session(page, token)
        bodies = [
            (400, {"status": 400, "error": "Bad Request", "message": "City Beersheba is not supported"}),
            (400, {"status": 400, "error": "Bad Request", "message": {"city": "must not be blank"}}),
            (401, {"status": 401, "error": "Unauthorized", "message": "probe unauthorized"}),
            (200, {"message": "Car added successfully"}),
        ]
        for status, body in bodies:
            restore_session(page, token)
            page.goto(f"{UI_BASE_URL}/let-car-work")
            fill_valid_car_form(page)

            handler = post_handler(status, body)
            page.route("**/v1/cars", handler)
            with page.expect_response(lambda r: is_api(r.request, "POST", "/v1/cars")):
                page.click("button[type=submit]")
            page.locator("button[type=submit]", has_text="Submit").wait_for()
            page.wait_for_load_state("networkidle")
            LOG.fact(
                f"ответ {status} {short(body.get('message'), 60)}: блоки role=status/alert: {roles_text(page)}; "
                f"поле Make: {page.input_value('[name=manufacture]')!r}"
            )
            page.unroute("**/v1/cars", handler)
        LOG.fact(f"оборвано пишущих запросов мимо подмены: {len(caught)} {caught}")
    finally:
        ctx.close()


# ---------------------------------------------------------------- запуск


def main():
    LOG.line("# Факты: explore_ui_rest.py")
    LOG.line(f"UI_BASE_URL: {UI_BASE_URL}")
    try:
        _email, _password, token, response = register_user()
        LOG.fact(f"временный пользователь: регистрация HTTP {response.status_code}")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                steps = [
                    lambda: q_ui_20_car_form_validation(browser, token),
                    lambda: q_ui_21_city_suggestions(browser),
                    lambda: q_ui_22_pagination(browser),
                    lambda: q_ui_23_city_case(browser),
                    lambda: q_ui_24_search_failures(browser),
                    lambda: q_ui_25_register_url(browser),
                    lambda: q_ui_26_submit_error_text(browser, token),
                ]
                # --only Q-UI-24,Q-UI-26 — только перечисленные вопросы
                only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
                ids = [f"Q-UI-{n}" for n in range(20, 27)]
                steps = [step for qid, step in zip(ids, steps, strict=True) if only is None or qid in only]
                for step in steps:
                    try:
                        step()
                    except Exception as exc:
                        first = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
                        LOG.fact(f"вопрос не завершён: {type(exc).__name__}: {short(first, 250)}")
                        traceback.print_exc()
            finally:
                browser.close()
    finally:
        # Машин скрипт не создаёт: POST /v1/cars перехвачен
        print_stats(LOG)


if __name__ == "__main__":
    main()
