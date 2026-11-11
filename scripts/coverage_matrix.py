"""
Матрица трассируемости требований: docs/requirements/traceability.md из тегов автотестов.

    python scripts/coverage_matrix.py           # пересобрать матрицу и сводку в README.md
    python scripts/coverage_matrix.py --check   # ничего не писать, только проверить (CI, pre-commit)

Матрицу не пишут руками. Источники правды:
  * docs/requirements/requirements.md — пункты REQ-…, DISC-…, OBS-… и их формулировки;
  * теги @allure.tag("REQ-…") на тестах, в том числе в pytest.param(..., marks=allure.tag(...));
  * маркеры known_bug и observation — реестры data/known_bugs.py и data/observations.py;
  * data/coverage_exceptions.py — пункты без автотеста: исключения и запланированные тесты.

Тесты НЕ запускаются: pytest только собирает их (как --collect-only), поэтому матрица показывает,
ЧТО проверяет набор тестов, а не результат последнего прогона. Браузер, Grid и сеть не нужны.

Несогласованные данные — ошибка в любом режиме (код 2), все находки печатаются разом:
  * тег с ID, которого нет в requirements.md;
  * ID без теста и без записи в исключениях;
  * ID и с тестом, и с записью в исключениях любой категории, кроме partial;
  * запись partial на ID без теста;
  * тест под known_bug / observation без тега своих refs или с тегом сверх них;
  * xfail не из реестров.
В режиме --check дополнительно (код 1): traceability.md или сводка в README.md устарели.
"""

import argparse
import contextlib
import difflib
import io
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = ROOT / "docs" / "requirements" / "traceability.md"
README_PATH = ROOT / "README.md"
TESTS_DIR = "tests"

sys.path.insert(0, str(ROOT))  # реестры импортируются так же, как их импортируют тесты
from data.coverage_exceptions import (  # noqa: E402
    CATEGORY_TITLES,
    COVERAGE_EXCEPTIONS,
    PARTIAL,
    PLANNED,
    PLANNED_PRS,
)
from data.known_bugs import KNOWN_BUGS  # noqa: E402
from data.observations import OBSERVATIONS  # noqa: E402
from data.requirement_ids import RequirementItem, requirement_items  # noqa: E402

README_START = "<!-- coverage:start -->"
README_END = "<!-- coverage:end -->"

REQUIREMENT_TAG = re.compile(r"^(?:REQ|DISC|OBS)-")
# Причина xfail из реестров начинается с ключа записи: "[NO_AUTH_403] …"
REGISTRY_REASON = re.compile(r"^\[([A-Z0-9_]+)\]")
# Конец первого предложения формулировки: точка, за которой начинается новое предложение
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ«`])")

PREFIXES = ("REQ", "DISC", "OBS")

COVERED = "covered"
PARTIAL_STATUS = "partial"
BUG = "bug"
OBSERVED = "observed"
EXCEPTION = "exception"
PLANNED_STATUS = "planned"

ICONS = {COVERED: "✅", PARTIAL_STATUS: "🟡", BUG: "🐞", OBSERVED: "👁", EXCEPTION: "⚪", PLANNED_STATUS: "🕓"}
STATUS_TITLES = {
    COVERED: "покрыт",
    PARTIAL_STATUS: "частично",
    BUG: "покрыт как известный баг",
    OBSERVED: "покрыт как наблюдение",
    EXCEPTION: "исключение",
    PLANNED_STATUS: "запланирован",
}
# Сводка в README.md — на английском, как весь README
STATUS_TITLES_EN = {
    COVERED: "Covered by a passing test",
    PARTIAL_STATUS: "Partly covered by a passing test, the rest is planned",
    BUG: "Covered, the test hits a known bug (strict xfail)",
    OBSERVED: "Covered as an observation (strict xfail)",
    EXCEPTION: "No test — exception with a recorded reason",
    PLANNED_STATUS: "No test yet — planned",
}
CATEGORY_TITLES_EN = {
    "harms_shared_env": "the check would harm the shared backend",
    "blocked": "blocked by another defect",
    "unreachable": "the feature is unreachable",
}
PLANNED_PRS_EN = {"6.2": "API", "6.3": "UI and observations"}


# ==========================================
# Сбор тестов
# ==========================================
@dataclass
class CollectedTest:
    path: str  # файл теста относительно корня проекта
    function: str  # имя функции без параметров
    param_id: str | None  # id параметризации или None
    tags: set[str] = field(default_factory=set)  # только теги-ID требований
    bugs: set[str] = field(default_factory=set)  # ключи known_bug
    observations: set[str] = field(default_factory=set)  # ключи observation
    foreign_xfail: bool = False  # xfail, причина которого не ведёт в реестры

    @property
    def name(self) -> str:
        suffix = f"[{self.param_id}]" if self.param_id is not None else ""
        return f"{self.path}::{self.function}{suffix}"

    @property
    def registry_refs(self) -> set[str]:
        """ID, ради которых тест помечен как ожидаемо падающий."""
        refs = {ref for key in self.bugs for ref in KNOWN_BUGS[key].refs}
        return refs | {OBSERVATIONS[key].ref for key in self.observations}


class _Collector:
    """Плагин pytest: забирает собранные тесты, ничего не запуская."""

    def __init__(self) -> None:
        self.tests: list[CollectedTest] = []

    def pytest_collection_finish(self, session) -> None:
        self.tests = [_describe(item) for item in session.items]


def _describe(item) -> CollectedTest:
    callspec = getattr(item, "callspec", None)
    test = CollectedTest(
        path=Path(item.path).relative_to(ROOT).as_posix(),
        function=getattr(item, "originalname", None) or item.name,
        param_id=callspec.id if callspec else None,
    )
    # iter_markers видит и декораторы функции, и marks отдельного параметра
    for mark in item.iter_markers("allure_label"):
        if mark.kwargs.get("label_type") == "tag":
            test.tags.update(str(tag) for tag in mark.args if REQUIREMENT_TAG.match(str(tag)))

    for mark in item.iter_markers("xfail"):
        match = REGISTRY_REASON.match(mark.kwargs.get("reason", ""))
        key = match.group(1) if match else None
        if key in KNOWN_BUGS:
            test.bugs.add(key)
        elif key in OBSERVATIONS:
            test.observations.add(key)
        else:
            test.foreign_xfail = True
    return test


def collect_tests() -> list[CollectedTest]:
    collector = _Collector()
    output = io.StringIO()
    os.chdir(ROOT)  # pytest.ini и conftest.py ищутся от текущей папки
    with contextlib.redirect_stdout(output):
        exit_code = pytest.main([TESTS_DIR, "--collect-only", "-q", "-p", "no:cacheprovider"], plugins=[collector])
    if exit_code != pytest.ExitCode.OK:
        print(output.getvalue(), file=sys.stderr)
        raise SystemExit(f"ОШИБКА: pytest не смог собрать тесты (код {int(exit_code)}), вывод выше")
    return collector.tests


# ==========================================
# Сопоставление тестов и требований
# ==========================================
@dataclass
class Row:
    """Пункт requirements.md и всё, что о нём известно матрице."""

    item: RequirementItem
    tests: list[CollectedTest] = field(default_factory=list)

    @property
    def prefix(self) -> str:
        return self.item.id.split("-", 1)[0]

    @property
    def bugs(self) -> list[str]:
        """Ключи известных багов, которые ссылаются на этот пункт и стоят на его тестах."""
        keys = {key for test in self.tests for key in test.bugs if self.item.id in KNOWN_BUGS[key].refs}
        return sorted(keys)

    @property
    def observations(self) -> list[str]:
        keys = {key for test in self.tests for key in test.observations if OBSERVATIONS[key].ref == self.item.id}
        return sorted(keys)

    @property
    def exception(self):
        return COVERAGE_EXCEPTIONS.get(self.item.id)

    @property
    def is_partial(self) -> bool:
        return self.exception is not None and self.exception.category == PARTIAL

    @property
    def status(self) -> str:
        if self.bugs:
            return BUG
        if self.observations:
            return OBSERVED
        if self.tests:
            return PARTIAL_STATUS if self.is_partial else COVERED
        if self.exception is not None and self.exception.category == PLANNED:
            return PLANNED_STATUS
        return EXCEPTION


def build_rows(tests: list[CollectedTest]) -> tuple[list[Row], list[str]]:
    """Строки матрицы и список несогласованностей (пустой — данные в порядке)."""
    rows = {item.id: Row(item) for item in requirement_items()}
    problems: list[str] = []

    for test in tests:
        if test.foreign_xfail:
            problems.append(
                f"{test.name}: xfail не из реестров. Ожидаемое падение оформляется только через "
                "@known_bug (data/known_bugs.py) или @observation (data/observations.py)"
            )
        for tag in sorted(test.tags):
            if tag in rows:
                rows[tag].tests.append(test)
            else:
                problems.append(f"{test.name}: тег {tag} — такого ID нет в docs/requirements/requirements.md")

        if test.bugs or test.observations:
            keys = ", ".join(sorted(test.bugs | test.observations))
            for ref in sorted(test.registry_refs - test.tags):
                problems.append(f"{test.name}: тест под маркером {keys} не несёт тег {ref} из refs своей записи")
            # В тесте под xfail через assert остаётся только проверка, ради которой стоит маркер:
            # лишний тег показал бы пункт покрытым проверкой, провал которой прячется за xfail
            for tag in sorted(test.tags - test.registry_refs):
                if tag in rows:
                    problems.append(
                        f"{test.name}: тег {tag} не входит в refs маркера {keys}. Под xfail остаётся только "
                        "проверка, ради которой он стоит, — остальное проверяет отдельный тест"
                    )

    for row in rows.values():
        if row.tests and row.exception is not None and not row.is_partial:
            problems.append(
                f"{row.item.id}: есть и тест ({row.tests[0].name}), и запись в data/coverage_exceptions.py "
                f"({row.exception.category}). Убери запись из реестра исключений "
                "(или замени на partial, если тест покрывает пункт не целиком)"
            )
        elif not row.tests and row.is_partial:
            problems.append(
                f"{row.item.id}: запись partial в data/coverage_exceptions.py, но теста с таким тегом нет. "
                "partial — только вместе с тестом; без теста это planned"
            )
        elif not row.tests and row.exception is None:
            problems.append(
                f"{row.item.id}: нет ни теста с таким тегом, ни записи в data/coverage_exceptions.py. "
                "Поставь тег на тест, который проверяет пункт, или запиши причину отсутствия теста"
            )
    return list(rows.values()), problems


# ==========================================
# Подсчёты
# ==========================================
def count_statuses(rows: list[Row]) -> dict[str, dict[str, int]]:
    """{статус: {REQ: n, DISC: n, OBS: n}}."""
    counts = {status: dict.fromkeys(PREFIXES, 0) for status in STATUS_TITLES}
    for row in rows:
        counts[row.status][row.prefix] += 1
    return counts


def count_exceptions(rows: list[Row]) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    """Исключения по категориям; запланированные и частично покрытые — по шагам плана."""
    categories = dict.fromkeys((c for c in CATEGORY_TITLES if c not in (PLANNED, PARTIAL)), 0)
    planned = dict.fromkeys(PLANNED_PRS, 0)
    partial = dict.fromkeys(PLANNED_PRS, 0)
    for row in rows:
        if row.status == EXCEPTION:
            categories[row.exception.category] += 1
        elif row.status == PLANNED_STATUS:
            planned[row.exception.pr] += 1
        elif row.is_partial and row.tests:
            partial[row.exception.pr] += 1
    return categories, planned, partial


def _summary_table(rows: list[Row], header: str, titles: dict[str, str], total_title: str) -> list[str]:
    counts = count_statuses(rows)
    lines = [f"| {header} | REQ | DISC | OBS | {total_title} |", "|---|---:|---:|---:|---:|"]
    for status, title in titles.items():
        by_prefix = counts[status]
        cells = " | ".join(str(by_prefix[prefix]) for prefix in PREFIXES)
        lines.append(f"| {ICONS[status]} {title} | {cells} | {sum(by_prefix.values())} |")
    totals = [sum(counts[status][prefix] for status in titles) for prefix in PREFIXES]
    lines.append(f"| **{total_title}** | {' | '.join(str(n) for n in totals)} | {sum(totals)} |")
    return lines


# ==========================================
# Markdown: traceability.md
# ==========================================
def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _brief(text: str) -> str:
    """Краткая формулировка — первое предложение пункта; полный текст остаётся в requirements.md."""
    for match in SENTENCE_END.finditer(text):
        head = text[: match.start()]
        # Точка внутри кавычек («Login failed. Try again») предложение не заканчивает
        if head.count("«") == head.count("»"):
            return head
    return text


class Renderer:
    def __init__(self, rows: list[Row], tests: list[CollectedTest]) -> None:
        self.rows = rows
        self.tests = tests
        self.params_total: dict[tuple[str, str], int] = {}
        for test in tests:
            key = (test.path, test.function)
            self.params_total[key] = self.params_total.get(key, 0) + 1

    # ---------- ячейки ----------
    def tests_cell(self, tests: list[CollectedTest]) -> str:
        if not tests:
            return "—"
        groups: dict[tuple[str, str], list[CollectedTest]] = {}
        for test in tests:
            groups.setdefault((test.path, test.function), []).append(test)

        lines = []
        for (path, function), group in groups.items():
            line = f"`{Path(path).name}::{function}`"
            # Параметры перечисляем, только если пункт проверяет часть из них
            if group[0].param_id is not None and len(group) < self.params_total[(path, function)]:
                line += " — " + "; ".join(f"`[{_cell(test.param_id)}]`" for test in group)
            lines.append(line)
        return "<br>".join(lines)

    @staticmethod
    def registry_cell(row: Row) -> str:
        return ", ".join(f"`{key}`" for key in row.bugs + row.observations) or "—"

    @staticmethod
    def status_cell(row: Row) -> str:
        status = row.status
        text = f"{ICONS[status]} {STATUS_TITLES[status]}"
        if status == PLANNED_STATUS:
            return f"{text} (PR {row.exception.pr})"
        if row.is_partial:
            # Известный баг или наблюдение важнее «частично», но неполнота покрытия не теряется
            separator = " — " if status == PARTIAL_STATUS else "; "
            return f"{text}{separator}не покрыто: {_cell(row.exception.reason)} (PR {row.exception.pr})"
        if status == EXCEPTION:
            text += f": {CATEGORY_TITLES[row.exception.category]}"
            if row.exception.blocked_by:
                text += f" ({', '.join(row.exception.blocked_by)})"
        return text

    # ---------- разделы ----------
    def summary(self) -> list[str]:
        categories, planned, partial = count_exceptions(self.rows)
        tagged = sum(1 for test in self.tests if test.tags)
        lines = [
            "## Сводка",
            "",
            *_summary_table(self.rows, "Статус", STATUS_TITLES, "Всего"),
            "",
            "- **Исключения по категориям:** "
            + "; ".join(f"{CATEGORY_TITLES[category]} — {n}" for category, n in categories.items())
            + ".",
            "- **Запланировано:** "
            + "; ".join(f"PR {pr} ({PLANNED_PRS[pr]}) — {n}" for pr, n in planned.items())
            + ".",
            "- **Покрыто частично, доработка:** "
            + "; ".join(f"PR {pr} ({PLANNED_PRS[pr]}) — {n}" for pr, n in partial.items())
            + ".",
            f"- **Известные баги:** {len(KNOWN_BUGS)} в реестре `data/known_bugs.py`; "
            f"**наблюдения:** {len(OBSERVATIONS)} в реестре `data/observations.py`.",
            f"- **Автотесты:** собрано {len(self.tests)}, из них с тегами требований — {tagged}, "
            f"без тегов — {len(self.tests) - tagged} (список — в конце документа).",
        ]
        return lines

    def requirement_sections(self) -> list[str]:
        lines: list[str] = []
        section = None
        for row in self.rows:
            if row.item.section != section:
                section = row.item.section
                lines += [
                    "",
                    f"### {section}",
                    "",
                    "| ID | Формулировка | Тесты | Реестр | Статус |",
                    "|---|---|---|---|---|",
                ]
            lines.append(
                f"| {row.item.id} | {_cell(_brief(row.item.text))} | {self.tests_cell(row.tests)} "
                f"| {self.registry_cell(row)} | {self.status_cell(row)} |"
            )
        return lines

    def exceptions_section(self) -> list[str]:
        lines = [
            "## Реестр исключений покрытия",
            "",
            "Реестр — `data/coverage_exceptions.py`. Исключения: теста не будет, пока не изменится приложение.",
            "Запланированные: запись убирает тот PR, который добавляет тест. Частично покрытые: тест есть,",
            "в таблице — что из пункта он не проверяет; запись убирает тот PR, который доберёт остальное.",
            "",
            "### Исключения",
            "",
            "| ID | Категория | Причина |",
            "|---|---|---|",
        ]
        for row in self.rows:
            if row.status == EXCEPTION:
                category = CATEGORY_TITLES[row.exception.category]
                if row.exception.blocked_by:
                    category += f": {', '.join(row.exception.blocked_by)}"
                lines.append(f"| {row.item.id} | {category} | {_cell(row.exception.reason)} |")

        for pr, title in PLANNED_PRS.items():
            lines += ["", f"### Запланировано: PR {pr} ({title})", "", "| ID | Что проверит тест |", "|---|---|"]
            for row in self.rows:
                if row.status == PLANNED_STATUS and row.exception.pr == pr:
                    lines.append(f"| {row.item.id} | {_cell(row.exception.reason)} |")

        lines += ["", "### Покрыто частично", "", "| ID | Что не покрыто | PR |", "|---|---|---|"]
        for row in self.rows:
            if row.is_partial and row.tests:
                lines.append(f"| {row.item.id} | {_cell(row.exception.reason)} | {row.exception.pr} |")
        return lines

    def untagged_section(self) -> list[str]:
        untagged = [test for test in self.tests if not test.tags]
        lines = [
            "## Тесты без тегов требований",
            "",
            "Эти тесты проверяют поведение, для которого в `requirements.md` нет пункта. ID для них",
            "не придумывают: нужен пункт — его сначала добавляют в `requirements.md`.",
            "",
        ]
        cell = self.tests_cell(untagged)
        lines += [f"- {line}" for line in cell.split("<br>")] if untagged else ["Таких тестов нет."]
        return lines

    def render(self) -> str:
        lines = [
            "# Матрица трассируемости требований",
            "",
            "> **Файл сгенерирован `scripts/coverage_matrix.py`, руками не править.**",
            "> Пункты и формулировки — из [`requirements.md`](requirements.md) (здесь — первое предложение пункта),",
            "> покрытие — теги `@allure.tag` на тестах, маркеры `known_bug` и `observation`, отсутствие теста —",
            "> реестр `data/coverage_exceptions.py`. Обновить: `python scripts/coverage_matrix.py`.",
            "> CI и pre-commit проверяют актуальность: `python scripts/coverage_matrix.py --check`.",
            "",
            "Матрица показывает, что проверяет набор тестов, а не результат прогона. Колонка «Факт»",
            "в `requirements.md` — снимок исследования, а не статус автоматизации.",
            "",
            "Статусы:",
            "",
            f"- {ICONS[COVERED]} **покрыт** — на пункт есть тест, и он проходит;",
            f"- {ICONS[PARTIAL_STATUS]} **частично** — тест есть и проходит, но проверяет не весь пункт:",
            "  что не покрыто и в каком PR это появится — в колонке «Статус» (реестр",
            "  `data/coverage_exceptions.py`, категория `partial`);",
            f"- {ICONS[BUG]} **покрыт как известный баг** — тест есть и упирается в дефект из `data/known_bugs.py`",
            "  (строгий xfail); ключ записи — в колонке «Реестр»;",
            f"- {ICONS[OBSERVED]} **покрыт как наблюдение** — тест фиксирует поведение из `data/observations.py`",
            "  (строгий xfail);",
            f"- {ICONS[EXCEPTION]} **исключение** — теста нет и не будет, пока не изменится приложение;",
            f"- {ICONS[PLANNED_STATUS]} **запланирован** — теста пока нет, указан PR, в котором он появится.",
            "",
            "«Покрыт» значит, что assert хотя бы одного теста проверяет пункт так, как он записан",
            "в `requirements.md`; если проверена только часть, пункт записан как частично покрытый.",
            "",
            *self.summary(),
            "",
            "## Требования и тесты",
            *self.requirement_sections(),
            "",
            *self.exceptions_section(),
            "",
            *self.untagged_section(),
        ]
        return "\n".join(lines) + "\n"


# ==========================================
# Markdown: сводка в README.md
# ==========================================
def render_readme_block(rows: list[Row], tests: list[CollectedTest]) -> str:
    categories, planned, partial = count_exceptions(rows)
    tagged = sum(1 for test in tests if test.tags)
    exceptions = "; ".join(f"{CATEGORY_TITLES_EN[category]} — {n}" for category, n in categories.items())
    plans = ", ".join(f"{n} in step {pr} ({PLANNED_PRS_EN[pr]})" for pr, n in planned.items())
    partly = ", ".join(f"{n} in step {pr}" for pr, n in partial.items())
    lines = [
        *_summary_table(rows, "Status", STATUS_TITLES_EN, "Total"),
        "",
        f"Exceptions: {exceptions}. Planned: {plans}. The rest of the partly covered items: {partly}.",
        f"{tagged} of {len(tests)} tests reference at least one ID.",
    ]
    return "\n".join(lines)


def replace_readme_block(readme: str, block: str) -> str:
    """README с новой сводкой между маркерами. Маркеров нет или они перепутаны — ошибка."""
    start, end = readme.find(README_START), readme.find(README_END)
    if start == -1 or end == -1 or end < start:
        raise SystemExit(
            f"ОШИБКА: в README.md нет пары маркеров {README_START} … {README_END}: сводку покрытия некуда вставить"
        )
    return readme[: start + len(README_START)] + "\n" + block + "\n" + readme[end:]


# ==========================================
# Запуск
# ==========================================
def _read(path: Path) -> str:
    # Git на Windows может отдать файл с CRLF: сравниваем содержимое, а не переводы строк
    return path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else ""


def _report_stale(path: Path, current: str, expected: str) -> None:
    relative = path.relative_to(ROOT).as_posix()
    diff = difflib.unified_diff(
        current.splitlines(),
        expected.splitlines(),
        f"{relative} (в репозитории)",
        f"{relative} (по тестам и реестрам)",
        lineterm="",
    )
    print(
        f"ОШИБКА: {relative} устарел — не совпадает с тем, что генерируется из тестов и реестров.\n"
        f"Запусти `python scripts/coverage_matrix.py` и закоммить обновлённый файл.\n"
        "Расхождения (первые 40 строк):",
        file=sys.stderr,
    )
    print("\n".join(list(diff)[:40]), file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--check", action="store_true", help="не писать файлы, а проверить, что они актуальны")
    args = parser.parse_args()
    # Консоль Windows (cp1251) не умеет эмодзи из diff: заменяем такие символы, а не падаем
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="replace")

    tests = collect_tests()
    rows, problems = build_rows(tests)
    if problems:
        print(f"ОШИБКА: теги тестов, реестры и requirements.md не согласованы ({len(problems)}):", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2

    targets = {
        MATRIX_PATH: Renderer(rows, tests).render(),
        README_PATH: replace_readme_block(_read(README_PATH), render_readme_block(rows, tests)),
    }

    if not args.check:
        for path, content in targets.items():
            relative = path.relative_to(ROOT).as_posix()
            if _read(path) == content:
                print(f"{relative}: без изменений")
            else:
                path.write_text(content, encoding="utf-8", newline="\n")
                print(f"{relative}: обновлён")
        return 0

    stale = False
    for path, content in targets.items():
        current = _read(path)
        if current == content:
            print(f"{path.relative_to(ROOT).as_posix()}: актуален")
        else:
            stale = True
            _report_stale(path, current, content)
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
