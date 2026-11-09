"""
Исследование фактического поведения UI IlCarro (вопросы Q-UI-01 … Q-UI-14).

Скрипт фиксирует факты: что сделали, какие запросы ушли, что показано на экране.
Оценок в нём нет. Запуск: python research/explore_ui.py --run 1
Лог: research/evidence/explore_ui_run1.log, скриншоты: research/evidence/q_ui_*.png
Токены в логи не попадают: значение localStorage['token'] заменяется на <hidden>.
"""

import json
import os
import re
import struct
import sys
import tempfile
import traceback
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

import common  # noqa: E402
from common import (  # noqa: E402
    API_BASE_URL,
    EVIDENCE_DIR,
    REG,
    UI_BASE_URL,
    VALID_PASSWORD,
    FactLog,
    body_json,
    call,
    car_payload,
    cleanup_cars,
    create_car,
    d,
    find_my_car,
    load_ui_cities,
    mask,
    new_email,
    new_serial,
    print_stats,
    register_user,
    run_name,
    short,
)

LOG = FactLog(run_name("explore_ui"))
UI_CITIES = load_ui_cities()
TIMEOUT_MS = 15000
FOOTER = "Best solution for rent your car"
NAV_RE = re.compile(r"^Search \| Let car work \| Terms of use \| (Sign up \| Log in|Log out) \| ")


# ---------------------------------------------------------------- наблюдение за страницей


class Net:
    """Собирает ответы API, диалоги браузера и ошибки консоли одной страницы."""

    def __init__(self, page):
        self.responses = []
        self.dialogs = []
        self.failed = []
        page.on("response", self._on_response)
        page.on("dialog", self._on_dialog)
        page.on("requestfailed", self._on_failed)

    def _on_response(self, resp):
        if resp.url.startswith(API_BASE_URL):
            self.responses.append(resp)

    def _on_dialog(self, dlg):
        self.dialogs.append(f"{dlg.type}: {dlg.message}")
        dlg.accept()

    def _on_failed(self, req):
        if req.url.startswith(API_BASE_URL):
            self.failed.append(f"{req.method} {req.url.replace(API_BASE_URL, '')} — {req.failure}")

    def take(self):
        """Возвращает накопленное и очищает буферы."""
        out = (list(self.responses), list(self.dialogs), list(self.failed))
        self.responses.clear()
        self.dialogs.clear()
        self.failed.clear()
        return out


def compact_json(text) -> str:
    """Укорачивает длинные строковые значения JSON (например image) до начала и длины."""
    if text is None:
        return "-"
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return short(str(text), 200)

    def walk(v):
        if isinstance(v, str) and len(v) > 60:
            return f"{v[:30]}...(длина {len(v)})"
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x) for x in v[:5]]
        return v

    return short(walk(data), 500)


def report_net(net: Net, label: str = "сеть"):
    """Печатает в лог: запросы к API (метод, путь, статус, тело запроса и ответа), диалоги, сбои запросов."""
    responses, dialogs, failed = net.take()
    if not responses:
        LOG.fact(f"{label}: запросов к API нет")
    for resp in responses:
        req = resp.request
        path = req.url.replace(API_BASE_URL, "")
        if path.startswith("/v1/cars/search") or path == "/v1/cars/cities":
            try:
                n = len((resp.json() or {}).get("cars" if "search" in path else "cities", []))
                answer = f"{'cars' if 'search' in path else 'cities'}={n}"
            except Exception:
                answer = "тело не прочитано"
        else:
            try:
                answer = compact_json(resp.text())
            except Exception as exc:
                answer = f"тело не прочитано ({type(exc).__name__})"
        LOG.fact(
            f"{label}: {req.method} {short(path, 120)} → HTTP {resp.status}; "
            f"запрос={compact_json(req.post_data) if req.post_data else '-'}; ответ={answer}"
        )
    for text in dialogs:
        LOG.fact(f"{label}: диалог браузера: {short(text, 200)}")
    for text in failed:
        LOG.fact(f"{label}: запрос оборван: {short(text, 200)}")
    return responses


def screen(page, limit: int = 350) -> str:
    """Видимый текст страницы без навигации и подвала."""
    text = page.inner_text("body")
    pos = text.find(FOOTER)
    text = text[:pos] if pos > 0 else text
    text = " | ".join(x.strip() for x in text.splitlines() if x.strip())
    text = NAV_RE.sub("", text + " | ").rstrip(" |")
    return short(text, limit)


def nav_state(page) -> str:
    n_out = page.get_by_role("button", name="Log out").count()
    return "кнопка Log out есть" if n_out else "кнопки Log out нет"


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


def shot(page, name: str):
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE_DIR / f"{name}.png"))
    LOG.fact(f"скриншот: research/evidence/{name}.png")


def settle(page, ms: int = 2500):
    page.wait_for_timeout(ms)


def attempt(label: str, fn, default=None):
    """Выполняет шаг; ошибку записывает как факт и продолжает."""
    try:
        return fn()
    except Exception as exc:
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
        LOG.fact(f"не удалось выполнить шаг «{label}»: {type(exc).__name__}: {short(first, 200)}")
        return default


# ---------------------------------------------------------------- действия в UI


def new_page(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.set_default_timeout(TIMEOUT_MS)
    return ctx, page, Net(page)


def pick_city(page, city: str):
    page.fill("#city", city)
    option = page.locator(f'[data-testid="city-option"][data-value="{city}"]')
    option.first.wait_for(state="visible", timeout=5000)
    option.first.click()


def find_card(page, serial: str, label: str):
    """Ищет карточку машины на странице выдачи; если её нет — открывает тот же URL с size=500 и ищет снова."""
    size = re.search(r"size=(\d+)", page.url)
    size = size.group(1) if size else "?"
    card = page.locator(f'a.car-container[href="/cars/{serial}"]')
    if card.count():
        LOG.fact(f"{label}: карточка найдена на странице выдачи (size={size} в URL)")
        return card
    LOG.fact(
        f"{label}: на странице выдачи (size={size} в URL) карточек {page.locator('a.car-container').count()}, нашей нет"
    )
    big = re.sub(r"size=\d+", "size=500", page.url)
    page.goto(big)
    settle(page, 4000)
    card = page.locator(f'a.car-container[href="/cars/{serial}"]')
    LOG.fact(
        f"{label}: тот же URL с size=500 → карточек {page.locator('a.car-container').count()}; наша "
        f"найдена={card.count() > 0}"
    )
    return card


def pick_dates(page, first: int = 2, second: int = 5) -> str:
    """Открывает календарь, листает на месяц вперёд и кликает два доступных дня."""
    page.click("#dates")
    page.locator(".rdrNextButton").click()
    page.wait_for_timeout(300)
    days = page.locator(".rdrDay:not(.rdrDayPassive):not(.rdrDayDisabled)")
    days.nth(first).click()
    days.nth(second).click()
    page.wait_for_timeout(300)
    return page.input_value("#dates")


def ui_search(page, city: str, goto: bool = True):
    if goto:
        page.goto(f"{UI_BASE_URL}/search?page=0&size=10")
    pick_city(page, city)
    value = pick_dates(page)
    page.click("button[type=submit]")
    settle(page, 3500)
    return value


def close_modal(page) -> str:
    """Закрывает окно с кнопкой OK. Возвращает, чем пользовались; окно ищем по роли link/button и по тексту."""
    for kind, locator in (
        ("link OK", page.get_by_role("link", name="OK", exact=True)),
        ("button OK", page.get_by_role("button", name="OK", exact=True)),
        ("текст OK", page.get_by_text("OK", exact=True)),
    ):
        if locator.count():
            locator.first.click()
            settle(page, 800)
            return kind
    return "кнопка OK не найдена"


def alert_texts(page) -> str:
    """Тексты блоков ошибок формы (.error и role=alert)."""
    return short(page.locator(".error, [role=alert]").all_inner_texts(), 250)


def login_ui(page, email: str, password: str):
    page.goto(f"{UI_BASE_URL}/login")
    page.fill("input[name=username]", email)
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    settle(page, 2000)
    close_modal(page)


def fill_car_form(page, city, serial, *, extras=False, price="150", skip_city=False, photo=None):
    REG.label_car(serial)
    if not skip_city:
        pick_city(page, city)
    page.fill("[name=manufacture]", "ProbeMake")
    page.fill("[name=model]", "ProbeModel")
    page.fill("[name=year]", "2020")
    page.select_option("[name=fuel]", "Petrol")
    if extras:
        page.select_option("[name=gear]", "Automatic")
        page.select_option("[name=wheelsDrive]", "AWD")
        page.fill("[name=doors]", "4")
    page.fill("[name=seats]", "4")
    page.fill("[name=carClass]", "Economy")
    page.fill("[name=serialNumber]", serial)
    page.fill("[name=pricePerDay]", price)
    page.fill("[name=about]", "research probe")
    if photo:
        page.set_input_files("#photo-file", photo)
        page.wait_for_timeout(1500)


def settle_car(token: str, serial: str):
    """Если машина появилась у владельца — учитываем её и ставим на удаление в finally."""
    REG.label_car(serial)
    REG.car_owner_token[serial] = token
    car = find_my_car(token, serial)
    if car:
        REG.cars_created += 1
        LOG.fact(
            f"  машина {REG.cars[serial]} есть у владельца в /v1/cars/my: city={car.get('city')!r}, "
            f"fuel={car.get('fuel')!r}, seats={car.get('seats')}, pricePerDay={car.get('pricePerDay')}, "
            f"image(длина)={len(car.get('image') or '')}"
        )
    else:
        REG.car_owner_token.pop(serial, None)
        LOG.fact(f"  машины {REG.cars[serial]} в /v1/cars/my владельца нет")
    return car


def png_bytes(width: int, height: int, noise: bool) -> bytes:
    """Простейший PNG без сторонних библиотек. noise=True — несжимаемые случайные пиксели."""

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    rows = b"".join(b"\x00" + (os.urandom(width * 3) if noise else b"\x20\x40\x80" * width) for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, 0 if noise else 9))
        + chunk(b"IEND", b"")
    )


# ---------------------------------------------------------------- вопросы


def q_ui_01_car_page(browser, city, state):
    LOG.header("Q-UI-01", "Страница машины: клик по карточке и прямой URL")
    owner, pwd, tok, _ = register_user()
    serial = new_serial("RU")
    resp = create_car(tok, car_payload(city, serial, pricePerDay=321.5))
    LOG.fact(f"машина создана через API в городе {city}: HTTP {resp.status_code}")
    state["serial"], state["owner"], state["pwd"], state["tok"] = serial, owner, pwd, tok
    ctx, page, net = new_page(browser)
    try:
        value = ui_search(page, city)
        LOG.fact(f"поиск в UI: город {city}, даты в поле: {value}; URL после «Yalla!»: {short(page.url, 150)}")
        report_net(net, "поиск")
        cards = page.locator("a.car-container")
        hrefs = [cards.nth(i).get_attribute("href") for i in range(cards.count())]
        LOG.fact(f"карточек на экране: {len(hrefs)}; ссылки: {mask(hrefs)}")
        card = find_card(page, serial, "поиск")
        if card.count() == 0:
            LOG.fact("карточки с нашей машиной в выдаче нет")
        else:
            card.first.click()
            settle(page, 3000)
            state["car_url"] = page.url.replace(UI_BASE_URL, "")
            LOG.fact(f"после клика по карточке: URL={mask(page.url)}")
            LOG.fact(f"текст на экране: {screen(page)}")
            LOG.fact(nav_state(page))
            report_net(net, "после клика")
            shot(page, "q_ui_01_card_click")
    finally:
        ctx.close()
    ctx, page, net = new_page(browser)
    try:
        page.goto(f"{UI_BASE_URL}/cars/{serial}")
        settle(page, 3500)
        LOG.fact(f"прямой URL /cars/<car>: итоговый URL={mask(page.url)}")
        LOG.fact(f"текст на экране: {screen(page)}")
        report_net(net, "прямой URL")
        shot(page, "q_ui_01_direct_url")
    finally:
        ctx.close()


def q_ui_02_rent_now(browser, state):
    LOG.header("Q-UI-02", "«Rent now!!» на странице машины: гость и залогиненный")
    serial = state.get("serial")
    path = state.get("car_url") or f"/cars/{serial}"
    LOG.fact(f"страница машины открывается по пути: {mask(path)}")
    for who in ("гость", "залогиненный"):
        ctx, page, net = new_page(browser)
        try:
            if who == "залогиненный":
                login_ui(page, state["owner"], state["pwd"])
                net.take()
            page.goto(f"{UI_BASE_URL}{path}")
            settle(page, 3000)
            LOG.fact(f"[{who}] URL страницы: {mask(page.url)}; текст: {screen(page, 250)}")
            btn = page.get_by_text(re.compile(r"Rent now", re.I))
            LOG.fact(f"[{who}] элементов с текстом «Rent now»: {btn.count()}")
            if btn.count() == 0:
                LOG.fact(
                    f"[{who}] кнопки/ссылки на странице: "
                    f"{mask([x for x in page.locator('button, a').all_inner_texts() if x.strip()][:20])}"
                )
                shot(page, f"q_ui_02_{'guest' if who == 'гость' else 'logged'}_no_button")
                continue
            net.take()
            btn.first.click()
            settle(page, 2500)
            LOG.fact(f"[{who}] после клика: URL={mask(page.url)}; текст: {screen(page, 250)}")
            LOG.fact(f"[{who}] {ls_dump(page)}")
            report_net(net, f"[{who}] после клика")
            shot(page, f"q_ui_02_{'guest' if who == 'гость' else 'logged'}")
        finally:
            ctx.close()


def q_ui_03_ui_only_city(browser, state):
    LOG.header("Q-UI-03", "Добавление машины в UI в городе, которого нет в API")
    api = {c.get("city") for c in (body_json(call("GET", "/v1/cars/cities")) or {}).get("cities", [])}
    only_ui = [c for c in UI_CITIES if c not in api]
    city = only_ui[0]
    LOG.fact(f"город только из фронтенда: {city}")
    owner, pwd, tok, _ = register_user()
    ctx, page, net = new_page(browser)
    try:
        login_ui(page, owner, pwd)
        net.take()
        page.goto(f"{UI_BASE_URL}/let-car-work")
        serial = new_serial("RU")
        fill_car_form(page, city, serial)
        page.click("button[type=submit]")
        settle(page, 3500)
        LOG.fact(f"тексты .error/role=alert: {alert_texts(page)}")
        report_net(net, "отправка формы")
        shot(page, "q_ui_03_ui_only_city")
        settle_car(tok, serial)
    finally:
        ctx.close()


def q_ui_04_no_city(browser):
    LOG.header("Q-UI-04", "Форма добавления машины без города")
    owner, pwd, tok, _ = register_user()
    ctx, page, net = new_page(browser)
    try:
        login_ui(page, owner, pwd)
        net.take()
        page.goto(f"{UI_BASE_URL}/let-car-work")
        serial = new_serial("RU")
        fill_car_form(page, None, serial, skip_city=True)
        btn = page.locator("button[type=submit]")
        LOG.fact(f"кнопка Submit: enabled={btn.is_enabled()}; disabled-атрибут={btn.get_attribute('disabled')!r}")
        if btn.is_enabled():
            btn.click()
            settle(page, 3000)
            LOG.fact(f"тексты .error/role=alert после клика: {alert_texts(page)}")
            report_net(net, "отправка формы")
        shot(page, "q_ui_04_no_city")
        settle_car(tok, serial)
    finally:
        ctx.close()


def q_ui_05_extra_fields(browser, city):
    LOG.header("Q-UI-05", "Форма машины: gear, wheelsDrive, doors, значение fuel")
    owner, pwd, tok, _ = register_user()
    ctx, page, net = new_page(browser)
    try:
        login_ui(page, owner, pwd)
        net.take()
        page.goto(f"{UI_BASE_URL}/let-car-work")
        serial = new_serial("RU")
        fill_car_form(page, city, serial, extras=True)
        LOG.fact(
            f"значения select в форме: fuel={page.input_value('[name=fuel]')!r}, "
            f"gear={page.input_value('[name=gear]')!r}, "
            f"wheelsDrive={page.input_value('[name=wheelsDrive]')!r}; doors={page.input_value('[name=doors]')!r}"
        )
        page.click("button[type=submit]")
        settle(page, 3500)
        resps = report_net(net, "отправка формы")
        for r in resps:
            if r.request.method == "POST" and r.url.endswith("/v1/cars") and r.request.post_data:
                body = json.loads(r.request.post_data)
                LOG.fact(f"ключи тела запроса: {sorted(body.keys())}")
                LOG.fact(f"fuel в запросе: {body.get('fuel')!r}")
                for key in ("gear", "wheelsDrive", "doors"):
                    LOG.fact(
                        f"поле {key} в теле запроса: {'есть, значение ' + repr(body[key]) if key in body else 'нет'}"
                    )
        LOG.fact(f"тексты .error/role=alert: {alert_texts(page)}")
        settle_car(tok, serial)
    finally:
        ctx.close()


def q_ui_06_photo(browser, city):
    LOG.header("Q-UI-06", "Загрузка фото через #photo-file")
    owner, pwd, tok, _ = register_user()
    tmp = Path(tempfile.mkdtemp(prefix="ilcarro_probe_"))
    small = tmp / "small.png"
    big = tmp / "big.png"
    small.write_bytes(png_bytes(1, 1, noise=False))
    big.write_bytes(png_bytes(600, 600, noise=True))
    LOG.fact(f"размеры файлов: small.png={small.stat().st_size} байт, big.png={big.stat().st_size} байт")
    for name, path in (("маленький PNG 1x1", small), ("PNG около 1 МБ", big)):
        ctx, page, net = new_page(browser)
        try:
            login_ui(page, owner, pwd)
            net.take()
            page.goto(f"{UI_BASE_URL}/let-car-work")
            serial = new_serial("RU")
            fill_car_form(page, city, serial, photo=str(path))
            LOG.fact(f"[{name}] значение поля image в форме: {short(page.input_value('[name=image]'), 80)!r}")
            page.click("button[type=submit]")
            settle(page, 5000)
            resps = report_net(net, f"[{name}] отправка")
            for r in resps:
                if r.request.method == "POST" and r.url.endswith("/v1/cars") and r.request.post_data:
                    image = json.loads(r.request.post_data).get("image")
                    LOG.fact(
                        f"[{name}] image в запросе: "
                        f"{'нет поля' if image is None else repr(image[:40]) + ', длина ' + str(len(image))}"
                    )
            LOG.fact(f"[{name}] текст на экране: {screen(page, 200)}")
            settle_car(tok, serial)
        finally:
            ctx.close()


def _register_via_ui(page, net, email, password, first="Probe", last="User", terms=True):
    page.goto(f"{UI_BASE_URL}/register")
    page.fill("[name=firstName]", first)
    page.fill("[name=lastName]", last)
    page.fill("[name=username]", email)
    page.fill("[name=password]", password)
    if terms:
        page.check("#terms-of-use")
    btn = page.locator("button[type=submit]")
    enabled = btn.is_enabled()
    if enabled:
        btn.click()
        settle(page, 3000)
    return enabled


def q_ui_07_weak_password(browser):
    LOG.header("Q-UI-07", "Регистрация с паролем 'abc123' пять раз подряд")
    for i in range(1, 6):
        email = new_email()
        REG.label_user(email)
        ctx, page, net = new_page(browser)
        try:
            enabled = _register_via_ui(page, net, email, "abc123")
            LOG.fact(f"попытка {i}: кнопка Submit была доступна={enabled}; текст на экране: {screen(page, 300)}")
            inline = page.locator(".error").all_inner_texts()
            LOG.fact(f"попытка {i}: тексты .error под полями: {short(inline, 200)}")
            resps = report_net(net, f"попытка {i}")
            if any(r.status == 200 and r.request.method == "POST" for r in resps):
                REG.users_created += 1
            if i == 1:
                shot(page, "q_ui_07_attempt1")
        finally:
            ctx.close()


def q_ui_08_duplicate(browser):
    LOG.header("Q-UI-08", "Повторная регистрация существующего email через UI")
    email, pwd, tok, _ = register_user()
    ctx, page, net = new_page(browser)
    try:
        enabled = _register_via_ui(page, net, email, pwd)
        LOG.fact(f"кнопка Submit была доступна={enabled}; текст на экране: {screen(page, 300)}")
        report_net(net, "повторная регистрация")
        shot(page, "q_ui_08_duplicate")
    finally:
        ctx.close()


def q_ui_09_uppercase_email(browser):
    LOG.header("Q-UI-09", "Регистрация с заглавными буквами в email, выход, вход")
    email = f"Probe_{new_email('Up')[3:-12]}@Example.COM"
    REG.label_user(email)
    ctx, page, net = new_page(browser)
    try:
        enabled = _register_via_ui(page, net, email, VALID_PASSWORD)
        LOG.fact(f"регистрация: Submit доступен={enabled}; текст на экране: {screen(page, 250)}")
        resps = report_net(net, "регистрация")
        if any(r.status == 200 and r.request.method == "POST" for r in resps):
            REG.users_created += 1
        LOG.fact(f"регистрация: {ls_dump(page)}")
        LOG.fact(f"закрытие окна через: {close_modal(page)}")
        LOG.fact(f"после закрытия окна: URL={mask(page.url)}; {nav_state(page)}; текст: {screen(page, 150)}")
        out = page.get_by_role("button", name="Log out")
        if out.count():
            out.first.click()
            settle(page, 1000)
        LOG.fact(f"после нажатия Log out: {nav_state(page)}; {ls_dump(page)}")
        page.goto(f"{UI_BASE_URL}/login")
        page.fill("input[name=username]", email)
        page.fill("input[name=password]", VALID_PASSWORD)
        net.take()
        page.click("button[type=submit]")
        settle(page, 3000)
        LOG.fact(f"вход тем же email: текст на экране: {screen(page, 250)}; {nav_state(page)}")
        report_net(net, "вход")
        shot(page, "q_ui_09_login_after_upper")
    finally:
        ctx.close()


def q_ui_10_login_failures(browser):
    LOG.header("Q-UI-10", "Окно ошибки логина при подменённых ответах")
    email, pwd, tok, _ = register_user()
    path_re = "**/v1/user/login/usernamepassword"
    mocks = [
        (
            "ответ 500 с JSON-телом (message — строка)",
            lambda route: route.fulfill(
                status=500,
                content_type="application/json",
                body='{"status":500,"error":"Internal Server Error","message":"mocked server error"}',
            ),
        ),
        (
            "ответ 400 с JSON-телом (message — строка)",
            lambda route: route.fulfill(
                status=400,
                content_type="application/json",
                body='{"status":400,"error":"Bad Request","message":"mocked bad request"}',
            ),
        ),
        (
            "ответ 400 с JSON-телом (message — объект)",
            lambda route: route.fulfill(
                status=400,
                content_type="application/json",
                body='{"status":400,"error":"Bad Request","message":{"password":"mocked field error"}}',
            ),
        ),
        ("запрос оборван (route.abort)", lambda route: route.abort()),
    ]
    for title, handler in mocks:
        ctx, page, net = new_page(browser)
        try:
            page.route(path_re, handler)
            page.goto(f"{UI_BASE_URL}/login")
            page.fill("input[name=username]", email)
            page.fill("input[name=password]", pwd)
            page.click("button[type=submit]")
            settle(page, 3000)
            LOG.fact(f"[{title}] текст на экране: {screen(page, 300)}")
            LOG.fact(f"[{title}] {nav_state(page)}; {ls_dump(page)}")
            report_net(net, f"[{title}]")
            shot(page, f"q_ui_10_case{mocks.index((title, handler)) + 1}")
        finally:
            ctx.close()


def q_ui_11_calendar(browser):
    LOG.header("Q-UI-11", "Календарь поиска: прошлое и граница 365 дней")
    from datetime import date, timedelta

    ctx, page, net = new_page(browser)
    try:
        page.goto(f"{UI_BASE_URL}/search?page=0&size=10")
        page.click("#dates")
        page.wait_for_timeout(500)

        def month():
            return (
                f"{page.locator('.rdrMonthPicker option:checked').first.inner_text()} "
                f"{page.locator('.rdrYearPicker option:checked').first.inner_text()}"
            )

        start = month()
        LOG.fact(f"сегодня по часам скрипта: {date.today().isoformat()}; месяц в календаре при открытии: {start}")
        LOG.fact(
            f"ячеек дня: {page.locator('.rdrDay').count()}; с классом rdrDayDisabled: "
            f"{page.locator('.rdrDayDisabled').count()}; "
            f"rdrDayPassive: {page.locator('.rdrDayPassive').count()}"
        )
        disabled_nums = page.locator(".rdrDay.rdrDayDisabled:not(.rdrDayPassive)").all_inner_texts()
        LOG.fact(f"недоступные дни текущего месяца (класс rdrDayDisabled): {[x.strip() for x in disabled_nums]}")
        # --- «предыдущий месяц»
        prev = page.locator(".rdrPprevButton")
        LOG.fact(
            f"кнопка «предыдущий месяц»: найдена={prev.count()}; "
            f"disabled-атрибут={prev.first.get_attribute('disabled')!r}"
        )
        prev.first.click()
        page.wait_for_timeout(500)
        after_prev = month()
        LOG.fact(f"месяц после клика «предыдущий»: {after_prev} (до клика: {start})")
        past_enabled = page.locator(".rdrDay:not(.rdrDayPassive):not(.rdrDayDisabled)").count()
        LOG.fact(
            "в этом месяце недоступных дней (rdrDayDisabled): "
            f"{page.locator('.rdrDay.rdrDayDisabled:not(.rdrDayPassive)').count()}; доступных: {past_enabled}"
        )
        shot(page, "q_ui_11_after_prev")
        if after_prev != start:
            page.locator(".rdrNextButton").click()
            page.wait_for_timeout(300)
        # --- клик по дню раньше сегодняшнего (если сегодня не 1-е число)
        today = date.today()
        if today.day > 1:
            page.locator(".rdrDay:not(.rdrDayPassive)").nth(0).click(force=True)
            page.wait_for_timeout(300)
            LOG.fact(
                f"клик по 1-му числу текущего месяца (раньше сегодняшнего {today.day}-го): значение поля дат = "
                f"{page.input_value('#dates')!r}"
            )
        else:
            LOG.fact("сегодня 1-е число: дней раньше сегодняшнего в текущем месяце нет")
        # --- 13 месяцев вперёд
        limit_date = today + timedelta(days=365)
        LOG.fact(f"сегодня + 365 дней = {limit_date.isoformat()}")
        for step in range(1, 14):
            page.locator(".rdrNextButton").click()
            page.wait_for_timeout(250)
            label = month()
            enabled = page.locator(".rdrDay:not(.rdrDayPassive):not(.rdrDayDisabled)").count()
            dis = page.locator(".rdrDay.rdrDayDisabled:not(.rdrDayPassive)").count()
            if step >= 11 or dis:
                LOG.fact(f"+{step} мес. от текущего: {label}; доступных дней={enabled}; недоступных={dis}")
        # день дальше 365 дней: 15-е число месяца на +13
        far = page.locator(".rdrDay:not(.rdrDayPassive)").nth(14)
        far_class = far.get_attribute("class")
        LOG.fact(f"15-е число месяца {month()}: классы ячейки={short(far_class, 120)}")
        far.click(force=True)
        page.wait_for_timeout(300)
        page.locator(".rdrDay:not(.rdrDayPassive)").nth(16).click(force=True)
        page.wait_for_timeout(300)
        LOG.fact(
            f"после клика по 15-му и 17-му числам месяца {month()}: значение поля дат = {page.input_value('#dates')!r}"
        )
        shot(page, "q_ui_11_far_future")
    finally:
        ctx.close()


def q_ui_12_search(browser, city, state):
    LOG.header("Q-UI-12", "Поиск: город только из фронтенда, ручной ввод, цены на карточках")
    api = {c.get("city") for c in (body_json(call("GET", "/v1/cars/cities")) or {}).get("cities", [])}
    only_ui = [c for c in UI_CITIES if c not in api]
    ctx, page, net = new_page(browser)
    try:
        value = attempt("поиск по городу из фронтенда", lambda: ui_search(page, only_ui[0]))
        LOG.fact(f"город только из фронтенда ({only_ui[0]}): даты {value}; URL: {short(page.url, 150)}")
        LOG.fact(f"текст на экране: {screen(page)}; карточек: {page.locator('a.car-container').count()}")
        report_net(net, "поиск по городу из фронтенда")
        shot(page, "q_ui_12_ui_only_city")
    finally:
        ctx.close()
    ctx, page, net = new_page(browser)
    try:
        page.goto(f"{UI_BASE_URL}/search?page=0&size=10")
        page.fill("#city", city)
        page.wait_for_timeout(500)
        LOG.fact(f"город введён вручную «{city}» без выбора из списка; значение поля={page.input_value('#city')!r}")
        value = pick_dates(page)
        btn = page.locator("button[type=submit]")
        LOG.fact(f"даты {value}; кнопка Yalla! доступна={btn.is_enabled()}")
        if btn.is_enabled():
            btn.click()
            settle(page, 3500)
            LOG.fact(f"URL после клика: {short(page.url, 150)}; карточек: {page.locator('a.car-container').count()}")
            LOG.fact(f"текст на экране: {screen(page, 250)}")
        report_net(net, "ручной ввод города")
        shot(page, "q_ui_12_manual_city")
    finally:
        ctx.close()
    # --- цены: три машины с разными ценами в городе с малым числом машин
    owner, _, tok, _ = register_user()
    prices = [99.5, 250, 1234.56]
    serials = []
    for p in prices:
        s = new_serial("RU")
        create_car(tok, car_payload(city, s, pricePerDay=p))
        serials.append(s)
    ctx, page, net = new_page(browser)
    try:
        ui_search(page, city)
        responses = [r for r in net.responses if r.url.endswith("/v1/cars/search")]
        api_prices = {}
        if responses:
            for car in (responses[-1].json() or {}).get("cars", []):
                api_prices[car.get("serialNumber")] = car.get("pricePerDay")
        first_cards = page.locator("a.car-container")
        for i in range(min(3, first_cards.count())):
            href = first_cards.nth(i).get_attribute("href") or ""
            text = first_cards.nth(i).locator(".car-price-value").inner_text()
            LOG.fact(
                f"карточка №{i + 1} на странице выдачи (size=10): href={mask(href)}; цена на экране «{text}»; "
                f"pricePerDay в ответе search = {api_prices.get(href.split('/')[-1])!r}"
            )
        for s, p in zip(serials, prices, strict=True):
            card = find_card(page, s, f"цена {p}")
            if card.count():
                text = card.first.locator(".car-price-value").inner_text()
                LOG.fact(
                    f"цена {p} (отправлена при создании): на карточке «{text}»; pricePerDay в ответе search = "
                    f"{api_prices.get(s)!r}"
                )
            else:
                LOG.fact(f"цена {p}: карточки машины в выдаче нет; pricePerDay в ответе search = {api_prices.get(s)!r}")
        shot(page, "q_ui_12_prices")
    finally:
        ctx.close()


def _guest_or_session_submit(browser, city, token_value=None, user=None, label=""):
    ctx, page, net = new_page(browser)
    try:
        serial = new_serial("RU")
        if user:
            login_ui(page, user[0], user[1])
            if token_value is not None:
                page.evaluate("(v) => localStorage.setItem('token', v)", token_value)
                LOG.fact(f"[{label}] в localStorage подставлен token=<мусор, длина {len(token_value)}>")
            net.take()
            page.reload()
            settle(page, 1000)
        page.goto(f"{UI_BASE_URL}/let-car-work")
        settle(page, 1500)
        LOG.fact(
            f"[{label}] /let-car-work: итоговый URL={mask(page.url)}; поле #city на странице: "
            f"{page.locator('#city').count()}; {nav_state(page)}"
        )
        LOG.fact(f"[{label}] текст на экране до отправки: {screen(page, 200)}")
        if page.locator("#city").count():
            fill_car_form(page, city, serial)
            page.click("button[type=submit]")
            settle(page, 3500)
            LOG.fact(f"[{label}] после отправки: URL={mask(page.url)}; тексты .error/role=alert: {alert_texts(page)}")
            LOG.fact(f"[{label}] {nav_state(page)}; {ls_dump(page)}")
            report_net(net, f"[{label}] отправка")
            shot(page, "q_ui_13_" + ("guest" if label == "гость" else "garbage_token"))
    finally:
        ctx.close()


def q_ui_13_session(browser, city):
    LOG.header("Q-UI-13", "Сессия: мусорный token в localStorage и форма машины гостем")
    email, pwd, tok, _ = register_user()
    _guest_or_session_submit(
        browser, city, token_value="garbage-token-value", user=(email, pwd), label="мусорный token"
    )
    _guest_or_session_submit(browser, city, label="гость")


def q_ui_14_logout(browser):
    LOG.header("Q-UI-14", "Выход: токен после Log out")
    email, pwd, tok, _ = register_user()
    ctx, page, net = new_page(browser)
    try:
        login_ui(page, email, pwd)
        saved = page.evaluate("() => localStorage.getItem('token')")
        LOG.fact(f"после входа: {ls_dump(page)}; {nav_state(page)}")
        out = page.get_by_role("button", name="Log out")
        out.first.click()
        settle(page, 1500)
        LOG.fact(f"после Log out: URL={mask(page.url)}; {nav_state(page)}; {ls_dump(page)}")
        resp = requests.get(
            f"{API_BASE_URL}/v1/cars/my", headers={"Authorization": f"Bearer {saved}"}, timeout=common.TIMEOUT
        )
        LOG.fact(
            f"GET /v1/cars/my с токеном, сохранённым до выхода: HTTP {resp.status_code}; тело={short(resp.text, 150)}"
        )
    finally:
        ctx.close()


# ---------------------------------------------------------------- запуск


def pick_low_count_city() -> str:
    """Город из пересечения API и UI_CITIES с наименьшим числом машин (кроме Tel Aviv: его ответ ~18 МБ)."""
    in_api = {c.get("city") for c in (body_json(call("GET", "/v1/cars/cities")) or {}).get("cities", [])}
    counts = {}
    for city in UI_CITIES:
        if city in in_api and city != "Tel Aviv":
            resp = call("POST", "/v1/cars/search", json={"city": city, "startDate": d(10), "endDate": d(14)})
            counts[city] = len((body_json(resp) or {}).get("cars", []))
    LOG.fact(f"число машин в поиске по городам из пересечения (без Tel Aviv): {counts}")
    return min(counts, key=lambda c: (counts[c], c))


def main():
    LOG.line("# Факты: explore_ui.py")
    LOG.line(f"UI_BASE_URL: {UI_BASE_URL}")
    state = {}
    try:
        city = pick_low_count_city()
        LOG.fact(f"город для проб: {city}")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                steps = [
                    lambda: q_ui_01_car_page(browser, city, state),
                    lambda: q_ui_02_rent_now(browser, state),
                    lambda: q_ui_03_ui_only_city(browser, state),
                    lambda: q_ui_04_no_city(browser),
                    lambda: q_ui_05_extra_fields(browser, city),
                    lambda: q_ui_06_photo(browser, city),
                    lambda: q_ui_07_weak_password(browser),
                    lambda: q_ui_08_duplicate(browser),
                    lambda: q_ui_09_uppercase_email(browser),
                    lambda: q_ui_10_login_failures(browser),
                    lambda: q_ui_11_calendar(browser),
                    lambda: q_ui_12_search(browser, city, state),
                    lambda: q_ui_13_session(browser, city),
                    lambda: q_ui_14_logout(browser),
                ]
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
        cleanup_cars(LOG)
        print_stats(LOG)


if __name__ == "__main__":
    main()
