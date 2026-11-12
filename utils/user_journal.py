"""
Журнал пользователей, зарегистрированных за прогон.

Пользователей API удалить не умеет: каждый зарегистрированный аккаунт навсегда остаётся на общем
бэкенде. Чтобы видеть цену прогона, каждая успешная регистрация пишется одной строкой в
logs/registered_users.jsonl, а главный процесс pytest в конце печатает итог (см.
pytest_terminal_summary в conftest.py).

Запись делается там, где регистрация подтверждена приложением, а не там, где она задумана:
  * API_CLIENT — IlCarroAPI.register получил 200 (фикстуры temp_user, shared_user, user_pair и тесты,
    которые регистрируют пользователя клиентом);
  * RAW_REQUEST — «сырой» запрос регистрации в tests/test_api_auth.py получил 200;
  * UI_FORM — форма регистрации показала окно «Registered» (pages/registration_page.py).
Отклонённые регистрации (400) пользователя не создают и в журнал не попадают.
"""

import json
import logging

from config import PROJECT_ROOT, settings

logger = logging.getLogger(__name__)

USER_JOURNAL_FILE = PROJECT_ROOT / "logs" / "registered_users.jsonl"

API_CLIENT = "api_client"
RAW_REQUEST = "raw_request"
UI_FORM = "ui_form"

# Источник -> как он называется в итоговой строке
SOURCE_TITLES: dict[str, str] = {
    API_CLIENT: "фикстуры и API-клиент",
    RAW_REQUEST: "«сырые» запросы модуля авторизации",
    UI_FORM: "форма регистрации UI",
}


def record_registration(email: str, source: str) -> None:
    """Одна строка JSON на пользователя. Короткая запись в режиме append безопасна для воркеров xdist.

    Сбой записи не роняет тест: журнал — учёт, а не проверка.
    """
    try:
        USER_JOURNAL_FILE.parent.mkdir(exist_ok=True)
        record = {"email": email, "source": source, "worker": settings.xdist_worker_id}
        with open(USER_JOURNAL_FILE, "a", encoding="utf-8", newline="\n") as journal:
            journal.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning(f"Не удалось записать журнал пользователей: {exc}")


def reset_user_journal() -> None:
    """Удаляет журнал прошлого прогона. Вызывается главным процессом до старта воркеров."""
    USER_JOURNAL_FILE.unlink(missing_ok=True)


def user_journal_summary() -> str:
    """Итог по журналу текущего прогона одной строкой. Нет журнала — пользователей не создавали."""
    counts = dict.fromkeys(SOURCE_TITLES, 0)
    if USER_JOURNAL_FILE.is_file():
        for line in USER_JOURNAL_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            source = json.loads(line)["source"]
            counts[source] = counts.get(source, 0) + 1
    details = ", ".join(f"{SOURCE_TITLES.get(source, source)} — {count}" for source, count in counts.items())
    return f"Пользователи: зарегистрировано за прогон {sum(counts.values())} ({details}); удалить их API не умеет"
