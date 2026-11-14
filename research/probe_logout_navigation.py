"""
Проба Q-UI-41: какой URL видит тест сразу после «Log out» и когда наступает /search.

Повод — падение test_playwright_session.py::test_pw_token_rejected_after_logout: предусловие прочитало
page.url после «Log out» и увидело https://icarro-v1.netlify.app/, а не /search. Код фронта (бандл
index-CIwwRVbQ.js): обработчик «Log out» вызывает logout() и navigate("/", {replace: true}); маршрут "/" —
<Navigate to="/search" replace>, который переходит в useEffect; token из localStorage удаляет тоже
useEffect провайдера. Кнопка OK окна «You are logged in success» — обычная ссылка <a href="/search">,
то есть загрузка нового документа, а не переход внутри SPA.

Сценарии (в каждом повторе — новый контекст браузера; в A и B вход токеном в localStorage, без запроса входа):
  A «окно успеха, как в тесте»: /login с окном успеха (флаг loginSuccess в sessionStorage — так его ставит форма входа),
    клик OK, ожидание видимой «Log out» (wait_for, как login_as), клик «Log out», ожидание скрытой
    «Log out», чтение token и мгновенное чтение page.url — тот же порядок, что в тесте;
  B «страница устоялась»: то же, но перед кликом «Log out» дождались /search и события load.
  C «точно как тест» (--form): вход через форму (запрос входа состояния не меняет, Q-API-19), OK, ожидание
    «Log out», GET /v1/cars/my через requests, затем то же, что в A.
Каждый из A и B — REPEATS повторов без замедления и REPEATS с замедлением CPU 4× (CDP
Emulation.setCPUThrottlingRate). После мгновенного чтения — ожидание /search до 10 с.

След: один вход через API (в сценарии C ещё вход через форму в каждом повторе) исследовательским
пользователем (research/evidence/explore_ui_faults_user.txt);
файла нет — проба останавливается, а не регистрирует. Регистраций 0, машин 0. Запросы браузера к бэкенду
записываются: выход клиентский, их быть не должно.

Запуск: python research/probe_logout_navigation.py --run 1
Ячейки с записью видео (как --video=on в Docker и CI): python research/probe_logout_navigation.py --run 2 --video;
сценарий C: python research/probe_logout_navigation.py --run 3 --form;
видео — research/evidence/probe_logout_navigation_video/ (в git не попадает, после прогона можно удалить).
Лог: research/evidence/probe_logout_navigation_run1.log. Код выхода 1 — проба не может утверждать факты.
"""

import argparse
import re
import sys
import time
import traceback
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

# Скрипт запускается как файл: research/ (common) и корень проекта (api, config) надо добавить
# в путь до импорта, поэтому импорты ниже стоят после кода — E402 подавлен намеренно
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import Browser, Page, sync_playwright  # noqa: E402
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError  # noqa: E402

from api.car_api import IlCarroAPI  # noqa: E402
from common import EVIDENCE_DIR, REG, VALID_PASSWORD, FactLog, run_name  # noqa: E402
from config import settings  # noqa: E402

UI = settings.ui_url
API = settings.api_url
USER_FILE = EVIDENCE_DIR / "explore_ui_faults_user.txt"
REPEATS = 50
CPU_RATE = 4
SEARCH_WAIT_MS = 10_000
VIDEO_DIR = EVIDENCE_DIR / "probe_logout_navigation_video"
SEARCH_URL = re.compile(r"/search(\?.*)?$")
# Те же локаторы, что в pages/pw_login_page.py
LOGOUT = "button.navigation-link"

LOG: FactLog  # создаётся в main(): имя лога зависит от --run
EMAIL: list[str] = []  # email исследовательского пользователя — для входа через форму в сценарии C


class ProbeFailure(Exception):
    """Проба не может утверждать факт."""


@dataclass
class Result:
    scenario: str
    throttled: bool
    video: bool = False
    url_before_click: str = ""
    url_right_after_click: str = ""
    url_instant: str = ""  # прочитан так же, как в тесте: после скрытия «Log out» и чтения token
    token_after: bool | None = None
    url_final: str = ""
    search_ms: float | None = None  # от клика «Log out» до /search; None — /search не наступил за 10 с
    navigations: list[str] = field(default_factory=list)  # переходы главного фрейма: «+мс URL» от клика
    api_requests: list[str] = field(default_factory=list)
    error: str = ""
    before_status: int | None = None  # сценарий C: GET /v1/cars/my до выхода


def path_of(url: str) -> str:
    return urlsplit(url).path or "(пусто)"


def path_query(url: str) -> str:
    parts = urlsplit(url)
    return (parts.path or "(пусто)") + (f"?{parts.query}" if parts.query else "")


def api_login() -> str:
    if not USER_FILE.exists():
        raise ProbeFailure(f"нет {USER_FILE.name}: проба не регистрирует пользователей — нужен готовый")
    email = USER_FILE.read_text(encoding="utf-8").strip()
    REG.label_user(email)
    api = IlCarroAPI()
    resp = api.login(email, VALID_PASSWORD)
    if resp.status_code != 200 or not api.token:
        raise ProbeFailure(f"вход исследовательского пользователя через API: HTTP {resp.status_code}")
    REG.tokens[email] = api.token
    EMAIL.append(email)
    LOG.fact("исследовательский пользователь: вход через API (HTTP 200), регистраций нет")
    return api.token


def one_run(browser: Browser, token: str, scenario: str, throttled: bool, video: bool) -> Result:
    res = Result(scenario, throttled, video)
    # Запись видео — как --video=on в Docker и CI: она тоже нагружает рендерер
    context = browser.new_context(record_video_dir=str(VIDEO_DIR)) if video else browser.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(30_000)  # умолчание Playwright, как в тесте
    clicked_at: list[float] = []

    def on_nav(frame) -> None:
        if frame == page.main_frame and clicked_at:
            res.navigations.append(f"+{(time.monotonic() - clicked_at[0]) * 1000:.0f}мс {path_query(frame.url)}")

    def on_request(request) -> None:
        if request.url.startswith(API):
            res.api_requests.append(f"{request.method} {urlsplit(request.url).path}")

    page.on("framenavigated", on_nav)
    page.on("request", on_request)
    try:
        if throttled:
            cdp = context.new_cdp_session(page)
            cdp.send("Emulation.setCPUThrottlingRate", {"rate": CPU_RATE})
        page.goto(f"{UI}/login")
        if scenario == "C":
            # Как login_as: вход через форму (запрос входа состояния не меняет, Q-API-19)
            page.fill("input[name='username']", EMAIL[0])
            page.fill("input[name='password']", VALID_PASSWORD)
            page.click("button[type='submit']")
        else:
            page.evaluate(
                "(t) => { localStorage.setItem('token', t); localStorage.setItem('tokenType', 'Bearer');"
                " sessionStorage.setItem('loginSuccess', '1'); }",
                token,
            )
            page.reload()
        ok = page.get_by_role("link", name="OK", exact=True)
        ok.wait_for(state="visible")
        ok.click()
        if scenario == "B":
            page.wait_for_url(SEARCH_URL, wait_until="load")
        page.locator(LOGOUT).wait_for(state="visible")
        res.url_before_click = page.url
        if scenario == "C":
            # Как в тесте: токен из localStorage и GET /v1/cars/my до выхода (запрос не из браузера)
            session_token = page.evaluate("() => localStorage.getItem('token')")
            REG.tokens[f"form#{len(REG.tokens)}"] = session_token
            api = IlCarroAPI()
            api.session.headers.update({"Authorization": f"Bearer {session_token}"})
            res.before_status = api.get_my_cars().status_code

        clicked_at.append(time.monotonic())
        page.locator(LOGOUT).click()
        res.url_right_after_click = page.url
        page.locator(LOGOUT).wait_for(state="hidden")
        res.token_after = page.evaluate("() => localStorage.getItem('token')") is not None
        res.url_instant = page.url

        try:
            page.wait_for_url(SEARCH_URL, timeout=SEARCH_WAIT_MS, wait_until="commit")
            res.search_ms = (time.monotonic() - clicked_at[0]) * 1000
        except PlaywrightTimeoutError:
            pass
        res.url_final = page.url
    except Exception as exc:  # noqa: BLE001 — сбой одного повтора записывается, остальные идут дальше
        res.error = f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}"
    finally:
        context.close()
    return res


def report(results: list[Result], scenario: str, throttled: bool, video: bool) -> None:
    rows = [r for r in results if (r.scenario, r.throttled, r.video) == (scenario, throttled, video)]
    title = f"сценарий {scenario}, {'CPU 4×' if throttled else 'без замедления'}{', запись видео' if video else ''}"
    LOG.header("Q-UI-41", title)
    errors = [r for r in rows if r.error]
    ok = [r for r in rows if not r.error]
    mismatch = [r for r in ok if path_of(r.url_instant) != "/search"]
    never = [r for r in ok if r.search_ms is None]
    LOG.fact(f"повторов: {len(rows)}; сбоев повтора: {len(errors)}")
    for r in errors:
        LOG.fact(f"сбой повтора: {r.error}")
    LOG.fact(f"мгновенное чтение URL (как в тесте) ≠ /search: {len(mismatch)} из {len(ok)}")
    LOG.fact(f"/search не наступил за 10 с: {len(never)} из {len(ok)}")
    LOG.fact(f"путь при мгновенном чтении: {dict(Counter(path_of(r.url_instant) for r in ok))}")
    LOG.fact(
        f"путь сразу после клика (до ожидания скрытия): {dict(Counter(path_of(r.url_right_after_click) for r in ok))}"
    )
    LOG.fact(f"путь перед кликом «Log out»: {dict(Counter(path_of(r.url_before_click) for r in ok))}")
    LOG.fact(f"token после выхода остался: {sum(1 for r in ok if r.token_after)} из {len(ok)}")
    times = sorted(r.search_ms for r in ok if r.search_ms is not None)
    if times:
        LOG.fact(
            f"от клика до /search, мс: мин {times[0]:.0f}, медиана {times[len(times) // 2]:.0f}, макс {times[-1]:.0f}"
        )
    LOG.fact(f"итоговый путь: {dict(Counter(path_of(r.url_final) for r in ok))}")
    seqs = Counter(" → ".join(n.split(" ", 1)[1] for n in r.navigations) or "(переходов нет)" for r in ok)
    LOG.fact(f"последовательности переходов главного фрейма после клика: {dict(seqs)}")
    for r in mismatch[:5]:
        LOG.fact(
            f"пример расхождения: до клика {path_of(r.url_before_click)}; переходы {r.navigations}; "
            f"итог {path_of(r.url_final)}"
        )
    if scenario == "C":
        LOG.fact(f"GET /v1/cars/my до выхода: {dict(Counter(r.before_status for r in ok))}")
    api = Counter(req for r in rows for req in r.api_requests)
    LOG.fact(f"запросы браузера к бэкенду: {dict(api) if api else 'нет'}")


def main() -> int:
    global LOG
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--run", default="1")
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument("--form", action="store_true", help="только сценарий C: вход через форму, как в тесте")
    parser.add_argument("--video", action="store_true", help="только ячейки с записью видео (как --video=on в CI)")
    args = parser.parse_args()
    LOG = FactLog(run_name("probe_logout_navigation"))
    LOG.line(f"# probe_logout_navigation, прогон {args.run}")
    LOG.fact(f"UI {UI}; повторов на ячейку {args.repeats}; Chromium headless; CPU-замедление {CPU_RATE}×")
    try:
        token = api_login()
        results: list[Result] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            if args.form:
                cells = [("C", False, False)]
            elif args.video:
                cells = [(s, False, True) for s in ("A", "B")]
            else:
                cells = [(s, t, False) for s in ("A", "B") for t in (False, True)]
            for scenario, throttled, video in cells:
                for _ in range(args.repeats):
                    results.append(one_run(browser, token, scenario, throttled, video))
                report(results, scenario, throttled, video)
            browser.close()
        LOG.header("Итог", "след на бэкенде")
        LOG.fact("запросов к бэкенду вне браузера: 1 (вход через API); регистраций 0; машин 0")
        if any(r.error for r in results):
            LOG.fact("есть сбои повторов — см. выше")
        return 0
    except ProbeFailure as exc:
        LOG.fact(f"ПРОБА ОСТАНОВЛЕНА: {exc}")
        return 1
    except Exception:
        LOG.line(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
