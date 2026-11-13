"""
Журнал пользователей, зарегистрированных за прогон.

Пользователей API удалить не умеет: каждый зарегистрированный аккаунт навсегда остаётся на общем
бэкенде. Чтобы видеть цену прогона, каждая успешная регистрация пишется одной строкой в
logs/registered_users_<воркер>.jsonl (свой файл у каждого процесса, см. utils/run_journal.py),
а главный процесс pytest в конце печатает итог по всем файлам (см. pytest_sessionfinish
и pytest_terminal_summary в conftest.py).

Запись делается там, где регистрация подтверждена приложением, а не там, где она задумана:
  * API_CLIENT — IlCarroAPI.register получил 200 (фикстуры temp_user, shared_user, other_shared_user и тесты,
    которые регистрируют пользователя клиентом);
  * RAW_REQUEST — «сырой» запрос регистрации в tests/test_api_auth.py получил 200;
  * UI_FORM — форма регистрации показала окно «Registered»; запись делает сам тест одной явной строкой
    после проверки успеха (test_registration_success; test_registration_password_rejected_by_api — если
    бэкенд вопреки ожиданию принял регистрацию): page object побочных эффектов не имеет.
Отклонённые регистрации (400) пользователя не создают и в журнал не попадают.
"""

import logging

from config import PROJECT_ROOT, settings
from utils import run_journal

logger = logging.getLogger(__name__)

JOURNAL_DIR = PROJECT_ROOT / "logs"
JOURNAL_NAME = "registered_users"
JOURNAL_FIELDS = frozenset({"email", "source", "worker"})

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
    """Одна строка JSON на пользователя в файл журнала своего процесса.

    Сбой записи не роняет тест: журнал — учёт, а не проверка.
    """
    try:
        record = {"email": email, "source": source, "worker": settings.xdist_worker_id}
        run_journal.append_record(JOURNAL_DIR, JOURNAL_NAME, record)
    except OSError as exc:
        logger.warning(f"Не удалось записать журнал пользователей: {exc}")


def user_journal_summary() -> str:
    """Итог по журналу текущего прогона одной строкой. Нет файлов журнала — пользователей не создавали.

    Испорченная строка в любом файле журнала — run_journal.JournalError.
    """
    counts = dict.fromkeys(SOURCE_TITLES, 0)
    for record in run_journal.read_records(JOURNAL_DIR, JOURNAL_NAME, JOURNAL_FIELDS):
        source = record["source"]
        counts[source] = counts.get(source, 0) + 1
    details = ", ".join(f"{SOURCE_TITLES.get(source, source)} — {count}" for source, count in counts.items())
    return f"Пользователи: зарегистрировано за прогон {sum(counts.values())} ({details}); удалить их API не умеет"
