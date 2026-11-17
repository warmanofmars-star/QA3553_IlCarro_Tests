import contextlib
import time
from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import urlsplit

import allure
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Request, Response, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from config import settings
from pages.pw_base_page import PwBasePage

# Сколько оборванных запросов перечислять в диагностике: остальные только считаются
_FAILED_SHOWN = 10


@dataclass
class _DocumentRequest:
    """Запрос документа главного фрейма к хосту UI и чем он кончился (пока известно)."""

    request: Request
    sent_s: float | None  # от начала журнала по часам теста; None — запрос ушёл до окна
    status: int | None = None
    response_start_ms: float | None = None  # от отправки до начала ответа, по часам браузера
    failure: str | None = None


class _NavigationLog:
    """Журнал перехода после OK: запросы документа главного фрейма и оборванные запросы к хосту UI.

    Зачем (Q-UI-42): OK — обычная ссылка на новый документ /search (Q-UI-41), и в CI клик однажды ждал
    его загрузки 30 с. Журнал различает версии «документ не ответил», «документ оборван», «документ пришёл,
    но оборваны скрипты». Один журнал ведут два окна подряд — клик OK и ожидание «Log out»: ответ документа
    и запросы бандла могут прийти уже после возврата клика. Между окнами события не теряются, пока между
    ними нет вызовов Playwright: синхронный клиент доставляет события только внутри своих вызовов.
    В URL документа и ассетов UI нет ни токена, ни пароля; запросы к API (другой хост) журнал не пишет.
    """

    def __init__(self, page: Page, origin: str):
        self.page = page
        self.origin = origin
        self.started = time.monotonic()
        self.host = urlsplit(settings.ui_url).netloc
        self.documents: list[_DocumentRequest] = []
        self.failed: list[str] = []
        self.failed_total = 0

    def _on_ui_host(self, request: Request) -> bool:
        return urlsplit(request.url).netloc == self.host

    def _is_document(self, request: Request) -> bool:
        if not (self._on_ui_host(request) and request.is_navigation_request()):
            return False
        try:
            return request.frame == self.page.main_frame
        except PlaywrightError:
            # У запроса без фрейма (service worker) frame недоступен — это не документ страницы
            return False

    def _document(self, request: Request) -> _DocumentRequest | None:
        if not self._is_document(request):
            return None
        for document in self.documents:
            if document.request == request:
                return document
        # Запрос ушёл до окна, а ответ или обрыв пришёл в окне
        document = _DocumentRequest(request, sent_s=None)
        self.documents.append(document)
        return document

    def on_request(self, request: Request) -> None:
        if self._is_document(request):
            self.documents.append(_DocumentRequest(request, sent_s=time.monotonic() - self.started))

    def on_response(self, response: Response) -> None:
        document = self._document(response.request)
        if document is not None:
            document.status = response.status
            document.response_start_ms = response.request.timing["responseStart"]

    def on_request_failed(self, request: Request) -> None:
        if not self._on_ui_host(request):
            return
        document = self._document(request)
        if document is not None:
            document.failure = request.failure
        self.failed_total += 1
        if len(self.failed) < _FAILED_SHOWN:
            self.failed.append(f"{request.resource_type} {request.url}: {request.failure}")

    def _ready_state(self) -> str:
        # Страница может быть посреди перехода: evaluate без таймаута ждал бы контекст сколько угодно,
        # wait_for_function ограничен секундой. readyState — всегда непустая строка, ждать нечего
        try:
            return self.page.wait_for_function("() => document.readyState", timeout=1000).json_value()
        except PlaywrightError as exc:
            return f"не прочитан ({str(exc).splitlines()[0]})"

    def report(self, step: str) -> str:
        lines = [
            f"Диагностика перехода после OK: таймаут на шаге «{step}».",
            f"URL страницы: {self.page.url}; document.readyState: {self._ready_state()}",
            f"Запросы документа главного фрейма к {self.host} "
            f"(время — от начала окна «{self.origin}», по часам теста):",
        ]
        for document in self.documents:
            sent = "до окна" if document.sent_s is None else f"через {document.sent_s:.1f} с"
            if document.failure is not None:
                outcome = f"requestfailed: {document.failure}"
            elif document.status is not None:
                start = document.response_start_ms
                timing = f"{start:.0f} мс" if start is not None and start >= 0 else "время неизвестно"
                outcome = f"ответ HTTP {document.status}, начало ответа через {timing} после отправки"
            else:
                outcome = "ответа нет"
            lines.append(f"  - {document.request.method} {document.request.url}: отправлен {sent}; {outcome}")
        if not self.documents:
            lines.append("  - запросов документа не было")
        lines.append(f"Оборванные запросы к {self.host}: всего {self.failed_total}")
        lines.extend(f"  - {failed}" for failed in self.failed)
        if self.failed_total > len(self.failed):
            lines.append(f"  - … и ещё {self.failed_total - len(self.failed)}")
        return "\n".join(lines)


@contextlib.contextmanager
def _navigation_window(log: _NavigationLog, step: str) -> Iterator[None]:
    """Пока открыто, журнал слушает события страницы; на выходе подписки снимаются.

    Поведения и таймаутов не меняет: при таймауте внутри окна к тому же исключению добавляется заметка
    с журналом (и вложение Allure), и оно пробрасывается дальше. Тип прежний — TimeoutError: login_as
    намеренно не падает AssertionError, чтобы сбой предусловия не ушёл в xfail.
    """
    page = log.page
    page.on("request", log.on_request)
    page.on("response", log.on_response)
    page.on("requestfailed", log.on_request_failed)
    try:
        yield
    except PlaywrightTimeoutError as exc:
        text = log.report(step)
        exc.add_note(text)
        allure.attach(text, name="Диагностика перехода после OK", attachment_type=allure.attachment_type.TEXT)
        raise
    finally:
        page.remove_listener("request", log.on_request)
        page.remove_listener("response", log.on_response)
        page.remove_listener("requestfailed", log.on_request_failed)


class PwLoginPage(PwBasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.endpoint = "/login"

        # --- ЛОКАТОРЫ ---
        # В Playwright мы сохраняем готовые объекты локаторов
        self.email_input = page.locator("input[name='username']")
        self.password_input = page.locator("input[name='password']")
        self.submit_btn = page.locator("button[type='submit']")
        self.error_message = page.locator(".error")
        # Используем мощный селектор "по роли", который Playwright понимает из коробки
        self.ok_btn = page.get_by_role("link", name="OK", exact=True)
        self.global_message = page.locator("h3")
        self.logout_btn = page.locator("button.navigation-link")
        # Окно ошибки входа: role=dialog с заголовком h3 и текстом p (в окне успеха роли dialog нет)
        self.error_dialog = page.get_by_role("dialog")
        self.error_dialog_title = self.error_dialog.locator("h3")
        self.error_dialog_text = self.error_dialog.locator("p")
        # Журнал перехода, начатый кликом OK; его продолжает wait_logged_in (Q-UI-42)
        self._ok_navigation: _NavigationLog | None = None

    # --- ДЕЙСТВИЯ ---
    def open(self):
        self.open_url(self.endpoint)

    @allure.step("Ввод email")
    def fill_email(self, email: str):
        self.email_input.fill(email)

    # @allure.step("Ввод пароля")
    def fill_password(self, password: str):
        # ИСПОЛЬЗУЕМ КОНТЕКСТНЫЙ МЕНЕДЖЕР ВНУТРИ
        with allure.step("Ввод пароля: ********"):
            self.password_input.fill(password)

    @allure.step("Клик по кнопке отправки")
    def submit_login(self):
        self.submit_btn.click()

    def login(self, email, password):
        self.fill_email(email)
        self.fill_password(password)
        self.submit_login()

    def login_as(self, user):
        """Вход через форму как предусловие теста: открыть, войти, закрыть окно, дождаться «Log out».

        Ожидания — через wait_for (TimeoutError), а не expect (AssertionError): сбой входа
        не должен уйти в xfail теста под known_bug / observation.
        """
        with allure.step(f"Setup: вход через форму под {user.email}"):
            self.open()
            self.login(user.email, user.password)
            self.click_ok_button()
            self.wait_logged_in()

    @allure.step("Ожидание «Log out» после входа")
    def wait_logged_in(self):
        """Ждёт «Log out» (wait_for: TimeoutError, а не AssertionError — см. login_as).

        Ожидание идёт в окне диагностики перехода (Q-UI-42), продолжая журнал клика OK, если он был:
        бандл новой страницы /search грузится уже после возврата клика. Таймаут прежний.
        """
        log = self._ok_navigation or _NavigationLog(self.page, "ожидание «Log out»")
        self._ok_navigation = None
        with _navigation_window(log, "ожидание «Log out»"):
            self.logout_btn.wait_for(state="visible")

    @allure.step("Клик «Log out»")
    def click_logout(self):
        self.logout_btn.click()

    # --- ПРОВЕРКИ ---
    # Переносим магию expect() прямо внутрь Page Object
    @allure.step("Проверка успешного сообщения об авторизации")
    def check_success_message(self):
        expect(self.global_message).to_have_text("You are logged in success")

    @allure.step("Закрытие модального окна")
    def click_ok_button(self):
        # OK — ссылка на новый документ /search (Q-UI-41); клик ждёт начала перехода. Окно диагностики
        # (Q-UI-42) при таймауте назовёт, на чём встал переход; таймаут клика прежний
        self._ok_navigation = _NavigationLog(self.page, "клик OK")
        with _navigation_window(self._ok_navigation, "клик OK"):
            self.ok_btn.click()

    @allure.step("Проверка, что кнопка Logout появилась")
    def check_logout_button_visible(self):
        expect(self.logout_btn).to_be_visible()

    # for Playwright:
    @allure.step("Проверка ошибки валидации: {expected_text}")
    def check_error_message(self, expected_text: str):
        # Playwright сам будет ждать, пока текст не совпадет!
        expect(self.error_message).to_have_text(expected_text)

    @allure.step("Проверка блокировки кнопки Submit")
    def check_submit_button_disabled(self):
        expect(self.submit_btn).to_be_disabled()

    @allure.step("Снятие фокуса (клик по фону)")
    def remove_focus(self):
        self.page.locator("body").click()
