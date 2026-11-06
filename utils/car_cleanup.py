"""
Очистка машин, созданных тестами, и журнал фабрики машин.

Бэкенд общий и внешний, поэтому каждая машина, которую создал тест, должна быть удалена после него.
Тест не обязан помнить об этом сам: серийный номер регистрируется в CarCleanup, а удаление
выполняет teardown фикстуры (см. car_cleanup и create_car в conftest.py).

Почему серийный номер регистрируется ДО создания машины:
  * машину, созданную через UI, тест знает только по номеру из формы;
  * запрос создания мог дойти до сервера, а ответ — потеряться (таймаут);
  * негативный тест (мутации) не ждёт, что машина создастся, но если из-за дефекта она всё-таки
    создалась, её тоже надо убрать.
Поэтому в teardown удаляются только те зарегистрированные номера, которые реально есть в
/v1/cars/my владельца, — попытка удалить несозданную машину дала бы ложное предупреждение.

Сбой очистки не роняет тест (тест уже отработал, его результат важнее), но пишется в лог
предупреждением и попадает в журнал logs/car_factory.jsonl. По журналу главный процесс pytest
печатает итог: сколько машин создано и сколько удалено (см. pytest_terminal_summary в conftest.py).
"""

import logging
import json
import os
from dataclasses import asdict, dataclass, field

import allure

from config import PROJECT_ROOT

logger = logging.getLogger(__name__)

JOURNAL_FILE = PROJECT_ROOT / "logs" / "car_factory.jsonl"


@dataclass
class CleanupReport:
    """Итог очистки машин одного пользователя после одного теста."""
    owner: str
    test: str
    registered: int = 0  # номеров зарегистрировано для очистки
    created: int = 0  # из них машин реально было на бэкенде
    deleted: int = 0  # удалено фабрикой в teardown
    deleted_by_test: int = 0  # создано, но к teardown уже удалено самим тестом
    failed: list[str] = field(default_factory=list)  # номера, которые удалить не удалось
    left: list[str] = field(default_factory=list)  # машины, оставшиеся у пользователя после очистки


class CarCleanup:
    """Список машин пользователя, которые надо удалить после теста."""

    def __init__(self, api, owner_email: str, test_name: str):
        self._api = api
        self._owner = owner_email
        self._test = test_name
        self._registered: list[str] = []
        self._created: set[str] = set()  # подтверждено ответом 200 на создание

    def register(self, serial_number: str) -> None:
        """Регистрирует номер для удаления после теста (машина может быть ещё не создана)."""
        if serial_number not in self._registered:
            self._registered.append(serial_number)

    def mark_created(self, serial_number: str) -> None:
        """Сервер подтвердил создание: если к teardown машины нет, её удалил сам тест."""
        self.register(serial_number)
        self._created.add(serial_number)

    def _my_serials(self) -> set[str] | None:
        """Серийные номера машин пользователя или None, если список получить не удалось."""
        response = self._api.get_my_cars()
        if response.status_code != 200:
            logger.warning(
                f"Очистка машин {self._owner}: /v1/cars/my ответил {response.status_code}, "
                "проверить, какие машины созданы, нельзя"
            )
            return None
        return {car.get("serialNumber") for car in response.json().get("cars", [])}

    def run(self) -> CleanupReport:
        """Удаляет зарегистрированные машины. Никогда не бросает исключение: сбой — предупреждение."""
        report = CleanupReport(owner=self._owner, test=self._test, registered=len(self._registered))
        try:
            with allure.step(f"Teardown: удаление машин пользователя {self._owner}"):
                self._delete_registered(report)
                remaining = self._my_serials()
                if remaining is None:
                    report.left = ["<не удалось проверить>"]
                else:
                    report.left = sorted(remaining)
                if report.left:
                    # Сюда попадают и машины, которые тест создал, но забыл зарегистрировать
                    logger.warning(f"Очистка машин {self._owner}: после очистки у пользователя остались {report.left}")
        except Exception as exc:  # teardown не должен ронять тест — даже при сетевой ошибке
            logger.warning(f"Очистка машин {self._owner} прервана: {type(exc).__name__}: {exc}")
            report.failed.append(f"<ошибка: {type(exc).__name__}>")
        self._write_journal(report)
        return report

    def _delete_registered(self, report: CleanupReport) -> None:
        if not self._registered:
            return
        present = self._my_serials()
        for serial in self._registered:
            # Не удалось узнать, что есть на бэкенде, — пробуем удалить всё зарегистрированное
            is_present = present is None or serial in present
            if not is_present:
                if serial in self._created:
                    report.created += 1
                    report.deleted_by_test += 1
                continue

            response = self._api.delete_car(serial)
            if response.status_code == 200:
                report.created += 1
                report.deleted += 1
            elif present is None and serial not in self._created:
                # Списка нет, машина не подтверждена — скорее всего, её просто не было
                continue
            else:
                report.created += 1
                report.failed.append(serial)
                logger.warning(
                    f"Очистка машин {self._owner}: машину {serial} удалить не удалось: "
                    f"{response.status_code} {response.text}"
                )

    @staticmethod
    def _write_journal(report: CleanupReport) -> None:
        """Одна строка JSON на тест. Короткая запись в режиме append безопасна для воркеров xdist."""
        try:
            JOURNAL_FILE.parent.mkdir(exist_ok=True)
            record = asdict(report) | {"worker": os.environ.get("PYTEST_XDIST_WORKER", "main")}
            with open(JOURNAL_FILE, "a", encoding="utf-8") as journal:
                journal.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning(f"Не удалось записать журнал фабрики машин: {exc}")


def reset_journal() -> None:
    """Удаляет журнал прошлого прогона. Вызывается главным процессом до старта воркеров."""
    JOURNAL_FILE.unlink(missing_ok=True)


def journal_summary() -> str | None:
    """Итог по журналу текущего прогона одной строкой или None, если машин тесты не создавали."""
    if not JOURNAL_FILE.is_file():
        return None
    totals = {"users": 0, "registered": 0, "created": 0, "deleted": 0, "deleted_by_test": 0}
    failed: list[str] = []
    left: list[str] = []
    for line in JOURNAL_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        totals["users"] += 1
        for key in ("registered", "created", "deleted", "deleted_by_test"):
            totals[key] += record[key]
        failed += [f"{record['owner']}: {serial}" for serial in record["failed"]]
        left += [f"{record['owner']}: {serial}" for serial in record["left"]]
    summary = (
        f"Фабрика машин: пользователей {totals['users']}, номеров зарегистрировано {totals['registered']}, "
        f"машин создано {totals['created']}, удалено фабрикой {totals['deleted']}, "
        f"удалено самими тестами {totals['deleted_by_test']}, не удалось удалить {len(failed)}, "
        f"осталось у пользователей {len(left)}"
    )
    if failed:
        summary += "\n  Не удалось удалить: " + "; ".join(failed)
    if left:
        summary += "\n  Остались: " + "; ".join(left)
    return summary
