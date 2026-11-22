"""
Проверка английских переводов документов (*.en.md) против русских оригиналов.

    python scripts/check_translations.py                     # проверить все переводы (CI, pre-commit)
    python scripts/check_translations.py --print-hash <файл>  # напечатать отпечаток файла

Русский документ — оригинал, английский — перевод в файле *.en.md рядом с ним. Первая строка
перевода — служебная пометка (на GitHub не видна):

    <!-- translation-of: docs/requirements/requirements.md sha256:<первые 12 hex> -->

Отпечаток — sha256 текста оригинала в UTF-8 с переводами строк, приведёнными к \\n: так один и тот же
текст даёт один отпечаток на Windows (CRLF при checkout) и в Linux.

Что проверяется:
  1. Каждый *.en.md в репозитории (отслеживаемый или новый, не из .gitignore) несёт пометку
     translation-of или summary-of (сводка, см. ниже), оригинал
     из пометки существует, отпечаток совпадает. Оригинал изменили, а перевод нет — расхождение.
  2. Код переносится байт в байт — для каждого перевода с пометкой:
     - мультисет фрагментов в `обратных кавычках` во всём документе (вне блоков ```) совпадает
       с оригиналом: код не переводят и не теряют;
     - блоки ```: то же число, тот же порядок, тот же язык после ```, то же содержимое после удаления
       комментариев. Комментарий — # или // в начале строки или после пробела и до конца строки
       (поэтому https:// и ${#var} комментарием не считаются); строки, ставшие пустыми, и хвостовые
       пробелы не сравниваются. Комментарии в блоках переводятся, поэтому НЕ сверяются — это задумано:
       правка одного комментария в переводе проверку не роняет. Цена правила — текст « # …» или « // …»
       внутри строкового литерала тоже считается комментарием (с обеих сторон одинаково).
  3. Перевод не содержит непереведённого русского текста: кириллица допустима только в «ёлочках»
     и в `обратных кавычках`. Строка в «ёлочках» с кириллицей должна дословно встречаться в оригинале:
     это тексты интерфейса приложения на русском (данные, а не формулировки) — в переводе они остаются
     как есть, перевод — рядом в скобках. Код в кавычках сверяет с оригиналом правило 2 (например,
     сообщения Jenkinsfile в консоли). В блоках ``` кириллица — ошибка: код совпадает с оригиналом,
     а комментарии переведены.
  4. Для requirements.en.md — сверка по смыслу с requirements.md, построчно по разбору таблиц из
     data/requirement_ids.py: те же ID в том же порядке; у каждой строки тот же набор ссылок
     Q-API-NN / Q-UI-NN и тот же мультисет фрагментов в `обратных кавычках`; у REQ — тот же статус
     колонки «Факт» (словарь STATUSES ниже). У DISC вместо «Факта» «Последствие», у OBS в «Факте» —
     ссылки на исследование без статуса: там сверяются только ссылки и код.

Сводка (summary) — не перевод, а короткий английский пересказ большого русского документа
(журнал исследования) для читателя портфолио. Первая строка сводки — своя пометка:

    <!-- summary-of: docs/requirements/research-log.md sha256:<первые 12 hex> -->

Отпечаток тот же, что у переводов. Сводка пересказывает часть оригинала, поэтому сверяется
не на равенство, а на подмножество — она не может утверждать того, чего в оригинале нет:
  - отпечаток оригинала совпадает (правило 1): правка оригинала требует пересмотра сводки;
  - каждая ссылка Q-API-NN / Q-UI-NN сводки есть в оригинале;
  - каждый фрагмент в `обратных кавычках` сводки (вне блоков ```) есть среди фрагментов оригинала;
  - кириллица — по правилу 3, как у перевода.
Мультисет кода, блоки ``` и сверка ID и статусов (правила 2 и 4) к сводке не применяются.

Сгенерированные файлы на английском (GENERATED) — не переводы: у них нет пометки, проверка их
пропускает по имени. Их актуальность проверяет генератор (`scripts/coverage_matrix.py --check`).

Код выхода: 0 — всё согласовано; 1 — расхождение; 2 — ошибка использования или формата
(испорченная пометка, нет git, таблицы требований не разбираются).
Только stdlib (data/requirement_ids.py — тоже): зависимости проекта не нужны.
"""

import argparse
import hashlib
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # разбор таблиц — тот же, что у реестров и матрицы
from data.requirement_ids import RequirementItem, parse_requirement_items  # noqa: E402

TRANSLATION_SUFFIX = ".en.md"
HASH_LENGTH = 12

# Сгенерированные английские файлы: не переводы, пометки translation-of у них нет.
# Сверяет их с источниками генератор, а не эта проверка
GENERATED = frozenset({"docs/requirements/traceability.en.md"})

# Пары «перевод → оригинал», которые сверяются по смыслу, а не только по отпечатку
REQUIREMENTS_PAIRS = {"docs/requirements/requirements.en.md": "docs/requirements/requirements.md"}

# Статусы колонки «Факт» (легенда requirements.md) и их перевод — единственный источник словаря
# статусов; CLAUDE.md ссылается сюда. Ячейка «Факт» у REQ начинается со статуса (может быть жирным)
STATUSES = {
    "соблюдается": "met",
    "частично": "partly",
    "нарушается": "violated",
    "не проверено": "not verified",
    "не проверяемо": "not verifiable",
}

# В оригинале факт записан без статуса: по коду / значение по умолчанию библиотеки
# («по коду» по легенде документа — основание факта, а не статус). У этих строк сверяются
# только ссылки Q-… и код. Список не должен устаревать молча: ID исчез из requirements.md
# или его «Факт» начал начинаться со статуса — расхождение
NO_STATUS_IN_ORIGINAL = frozenset({"REQ-UI-REG-04", "REQ-UI-SEARCH-06", "REQ-UI-SEARCH-07"})

SUMMARY = "summary-of"
MARKER = re.compile(r"^<!-- (?P<kind>translation-of|summary-of): (?P<path>\S+) sha256:(?P<hash>[0-9a-f]{12}) -->$")
MARKER_START = ("<!-- translation-of:", "<!-- summary-of:")
Q_REF = re.compile(r"\bQ-(?:API|UI)-\d+\b")
CODE = re.compile(r"`([^`]*)`")
FENCE = re.compile(r"^\s*```(?P<lang>.*)$")
# Комментарий в блоке кода: # или // в начале строки или после пробела — до конца строки
BLOCK_COMMENT = re.compile(r"(?:^|\s)(?:#|//).*$")
CYRILLIC = re.compile(r"[А-Яа-яЁё]")
GUILLEMETS = re.compile(r"«[^«»]*»")

FIX_HINT = (
    "Обнови перевод по изменениям оригинала, затем отпечаток: python scripts/check_translations.py --print-hash {orig}"
)


class FormatError(Exception):
    """Ошибка формата (код 2): проверить перевод по существу нельзя."""


def fingerprint(path: Path) -> str:
    """Первые 12 hex sha256 текста в UTF-8 с переводами строк \\n."""
    text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:HASH_LENGTH]


def find_translations() -> list[str]:
    """*.en.md в репозитории: отслеживаемые и новые, кроме игнорируемых .gitignore (.venv и т. п.)."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise FormatError(f"не удалось получить список файлов через git: {error}") from error
    paths = {path for path in result.stdout.decode("utf-8").split("\0") if path.endswith(TRANSLATION_SUFFIX)}
    # Удалённый, но ещё не закоммиченный файл git ls-files --cached всё ещё называет
    return sorted(path for path in paths if (ROOT / path).is_file())


# ==========================================
# Пометка и отпечаток
# ==========================================
def check_marker(translation: str) -> tuple[list[str], str | None, str | None]:
    """Расхождения пометки, путь оригинала (None — не определён) и вид файла: перевод или сводка."""
    lines = (ROOT / translation).read_text(encoding="utf-8").splitlines()
    first = lines[0] if lines else ""
    if not first.startswith(MARKER_START):
        return (
            [
                f"{translation}: нет пометки translation-of или summary-of в первой строке — английский файл "
                "без оригинала. Добавь первой строкой <!-- translation-of: <путь оригинала> sha256:<отпечаток> --> "
                "(для сводки — summary-of); "
                "отпечаток: python scripts/check_translations.py --print-hash <путь оригинала>"
            ],
            None,
            None,
        )
    match = MARKER.match(first)
    if match is None:
        raise FormatError(
            f"{translation}: пометка не по формату: {first!r}. "
            "Нужно: <!-- translation-of: <путь от корня репозитория> sha256:<12 hex> --> (или summary-of)"
        )
    original, kind = match["path"], match["kind"]
    if not (ROOT / original).is_file():
        return [f"{translation}: оригинала {original} из пометки {kind} нет в репозитории"], None, kind
    actual = fingerprint(ROOT / original)
    if actual != match["hash"]:
        return (
            [
                f"{translation}: отпечаток оригинала {original} не совпал (в пометке {match['hash']}, "
                f"у оригинала {actual}) — оригинал изменился, а {'сводка' if kind == SUMMARY else 'перевод'} нет. "
                + FIX_HINT.format(orig=original)
            ],
            original,
            kind,
        )
    return [], original, kind


# ==========================================
# Разбор Markdown: проза и блоки кода
# ==========================================
def split_fences(path: str) -> tuple[list[tuple[int, str, bool]], list[tuple[int, str, list[str]]]]:
    """Строки документа с признаком «внутри блока ```» и сами блоки: (строка начала, язык, содержимое)."""
    lines: list[tuple[int, str, bool]] = []
    blocks: list[tuple[int, str, list[str]]] = []
    current: tuple[int, str, list[str]] | None = None
    for number, line in enumerate((ROOT / path).read_text(encoding="utf-8").splitlines(), start=1):
        fence = FENCE.match(line)
        if fence and current is None:
            current = (number, fence["lang"].strip(), [])
            lines.append((number, line, True))
        elif fence and not fence["lang"].strip():
            blocks.append(current)
            current = None
            lines.append((number, line, True))
        elif current is not None:
            current[2].append(line)
            lines.append((number, line, True))
        else:
            lines.append((number, line, False))
    if current is not None:
        raise FormatError(f"{path}:{current[0]}: блок ``` не закрыт")
    return lines, blocks


def _code_without_comments(content: list[str]) -> list[str]:
    stripped = (BLOCK_COMMENT.sub("", line).rstrip() for line in content)
    return [line for line in stripped if line.strip()]


def check_code(translation: str, original: str) -> list[str]:
    """Код в `обратных кавычках` и блоки ``` перевода совпадают с оригиналом (комментарии блоков — нет)."""
    ru_lines, ru_blocks = split_fences(original)
    en_lines, en_blocks = split_fences(translation)
    problems = []
    ru_code = Counter(code for _, line, in_block in ru_lines if not in_block for code in CODE.findall(line))
    en_code = Counter(code for _, line, in_block in en_lines if not in_block for code in CODE.findall(line))
    if ru_code != en_code:
        problems.append(
            f"{translation}: код в `обратных кавычках` не совпадает с оригиналом {original}: "
            f"нет {sorted((ru_code - en_code).elements())}, лишний {sorted((en_code - ru_code).elements())}. "
            "Код переносится байт в байт"
        )
    if len(ru_blocks) != len(en_blocks):
        problems.append(f"{translation}: блоков ``` {len(en_blocks)}, а в оригинале {original} — {len(ru_blocks)}")
    for position, (ru, en) in enumerate(zip(ru_blocks, en_blocks, strict=False), start=1):
        where = f"{translation}:{en[0]}: блок ``` №{position} (в оригинале — строка {ru[0]})"
        if ru[1] != en[1]:
            problems.append(f"{where}: язык {en[1] or 'не указан'!r}, а в оригинале {ru[1] or 'не указан'!r}")
        ru_code_lines, en_code_lines = _code_without_comments(ru[2]), _code_without_comments(en[2])
        if ru_code_lines != en_code_lines:
            diff = next(
                (pair for pair in zip(ru_code_lines, en_code_lines, strict=False) if pair[0] != pair[1]),
                (f"{len(ru_code_lines)} строк кода", f"{len(en_code_lines)} строк кода"),
            )
            problems.append(
                f"{where}: код без комментариев отличается от оригинала: {diff[1]!r} вместо {diff[0]!r}. "
                "Команды переносятся байт в байт, переводятся только комментарии"
            )
    return problems


def _prose_code(path: str) -> set[str]:
    """Фрагменты в `обратных кавычках` вне блоков ```."""
    return {code for _, line, in_block in split_fences(path)[0] if not in_block for code in CODE.findall(line)}


def check_summary(summary: str, original: str) -> list[str]:
    """Сводка не утверждает лишнего: её ссылки Q-… и код в `обратных кавычках` — подмножества оригинала."""
    problems = []
    ru_refs = set(Q_REF.findall((ROOT / original).read_text(encoding="utf-8")))
    en_refs = set(Q_REF.findall((ROOT / summary).read_text(encoding="utf-8")))
    if extra := sorted(en_refs - ru_refs):
        problems.append(
            f"{summary}: ссылки Q-…, которых нет в оригинале {original}: {', '.join(extra)}. "
            "Сводка пересказывает только записанное в оригинале"
        )
    if extra := sorted(_prose_code(summary) - _prose_code(original)):
        problems.append(
            f"{summary}: код в `обратных кавычках`, которого нет в оригинале {original}: {extra}. "
            "Код переносится из оригинала байт в байт"
        )
    return problems


# ==========================================
# Кириллица
# ==========================================
def check_cyrillic(translation: str, original: str | None) -> list[str]:
    """Кириллица в переводе — только в «ёлочках» (дословно из оригинала) и в `обратных кавычках`."""
    original_text = (ROOT / original).read_text(encoding="utf-8") if original else ""
    problems = []
    for number, line, in_block in split_fences(translation)[0]:
        if in_block:
            if leftover := CYRILLIC.search(line):
                problems.append(
                    f"{translation}:{number}: русский текст в блоке ``` (с позиции {leftover.start() + 1}) — "
                    "комментарии в блоках переводятся, код в оригинале кириллицы не содержит"
                )
            continue
        # Код в кавычках сверяет с оригиналом check_code; без оригинала (нет пометки) он не исключается
        line = CODE.sub("", line) if original else line
        for quoted in GUILLEMETS.findall(line):
            if CYRILLIC.search(quoted) and quoted not in original_text:
                problems.append(
                    f"{translation}:{number}: {quoted} — такой строки нет в оригинале. В «ёлочках» на русском "
                    "остаются только тексты интерфейса, байт в байт как в оригинале"
                )
        rest = GUILLEMETS.sub("", line)
        if leftover := CYRILLIC.search(rest):
            problems.append(
                f"{translation}:{number}: русский текст вне «ёлочек» (с позиции {leftover.start() + 1}) — "
                "непереведённый фрагмент. Переведи его; текст интерфейса на русском — в «ёлочках», как в оригинале"
            )
    return problems


# ==========================================
# Сверка требований по смыслу
# ==========================================
def _status(cell: str, statuses) -> str | None:
    """Статус, с которого начинается ячейка «Факт» (жирный — тоже), или None."""
    text = cell.lstrip("*").lstrip()
    for status in sorted(statuses, key=len, reverse=True):
        if re.match(rf"{re.escape(status)}(?![\w-])", text):
            return status
    return None


def _id_order_problems(translation: str, ru_ids: list[str], en_ids: list[str]) -> list[str]:
    problems = []
    missing = [item_id for item_id in ru_ids if item_id not in en_ids]
    extra = [item_id for item_id in en_ids if item_id not in ru_ids]
    if missing:
        problems.append(f"{translation}: пропущены пункты оригинала: {', '.join(missing)}")
    if extra:
        problems.append(f"{translation}: пункты, которых нет в оригинале: {', '.join(extra)}")
    common_ru = [item_id for item_id in ru_ids if item_id in en_ids]
    common_en = [item_id for item_id in en_ids if item_id in ru_ids]
    if common_ru != common_en:
        for position, (ru_id, en_id) in enumerate(zip(common_ru, common_en, strict=True), start=1):
            if ru_id != en_id:
                problems.append(
                    f"{translation}: порядок пунктов отличается от оригинала: на месте {position} "
                    f"в оригинале {ru_id}, в переводе {en_id}"
                )
                break
    return problems


def _row_problems(translation: str, ru: RequirementItem, en: RequirementItem) -> list[str]:
    problems = []
    prefix = f"{translation}: {ru.id}:"
    ru_refs, en_refs = set(Q_REF.findall(ru.line)), set(Q_REF.findall(en.line))
    if ru_refs != en_refs:
        problems.append(
            f"{prefix} ссылки Q-… не совпадают с оригиналом: нет {sorted(ru_refs - en_refs) or '—'}, "
            f"лишние {sorted(en_refs - ru_refs) or '—'}"
        )
    ru_code, en_code = Counter(CODE.findall(ru.line)), Counter(CODE.findall(en.line))
    if ru_code != en_code:
        problems.append(
            f"{prefix} код в `обратных кавычках` не совпадает с оригиналом: "
            f"нет {sorted((ru_code - en_code).elements())}, лишний {sorted((en_code - ru_code).elements())}"
        )
    if not ru.id.startswith("REQ-"):
        return problems  # DISC: «Последствие» вместо «Факта»; OBS: в «Факте» только ссылки на исследование

    ru_status = _status(ru.cells[-1], STATUSES)
    en_status = _status(en.cells[-1], STATUSES.values())
    if ru.id in NO_STATUS_IN_ORIGINAL:
        if ru_status is not None:
            problems.append(
                f"{prefix} «Факт» в оригинале теперь начинается со статуса «{ru_status}» — убери ID "
                "из NO_STATUS_IN_ORIGINAL в scripts/check_translations.py"
            )
        elif en_status is not None:
            problems.append(f"{prefix} в оригинале «Факт» без статуса, а в переводе — статус «{en_status}»")
        return problems
    if ru_status is None:
        problems.append(
            f"{prefix} «Факт» в оригинале не начинается со статуса из легенды ({', '.join(STATUSES)}). "
            "Поставь статус; если факт сознательно записан без статуса — согласуй и добавь ID в NO_STATUS_IN_ORIGINAL"
        )
    elif en_status != STATUSES[ru_status]:
        problems.append(
            f"{prefix} статус «Факта» в переводе «{en_status or 'нет статуса'}», "
            f"а в оригинале «{ru_status}» → должно быть «{STATUSES[ru_status]}»"
        )
    return problems


def check_requirements(translation: str, original: str) -> list[str]:
    try:
        ru_items = parse_requirement_items(ROOT / original)
        en_items = parse_requirement_items(ROOT / translation)
    except (OSError, ValueError) as error:
        raise FormatError(f"таблицы требований не разбираются: {error}") from error
    ru_ids = [item.id for item in ru_items]
    problems = [
        f"{original}: ID {item_id} из NO_STATUS_IN_ORIGINAL (scripts/check_translations.py) нет в оригинале — "
        "убери его из списка"
        for item_id in sorted(NO_STATUS_IN_ORIGINAL - set(ru_ids))
    ]
    problems += _id_order_problems(translation, ru_ids, [item.id for item in en_items])
    en_by_id = {item.id: item for item in en_items}
    for ru in ru_items:
        if ru.id in en_by_id:
            problems += _row_problems(translation, ru, en_by_id[ru.id])
    return problems


# ==========================================
# Запуск
# ==========================================
def check_all() -> int:
    problems: list[str] = []
    for translation in find_translations():
        if translation in GENERATED:
            continue
        marker_problems, original, kind = check_marker(translation)
        problems += marker_problems
        problems += check_cyrillic(translation, original)
        if original is not None:
            problems += check_summary(translation, original) if kind == SUMMARY else check_code(translation, original)
        expected_original = REQUIREMENTS_PAIRS.get(translation)
        if expected_original is not None:
            if kind == SUMMARY:
                problems.append(f"{translation}: сверяется по смыслу как перевод, а помечен как сводка (summary-of)")
            if original is not None and original != expected_original:
                problems.append(f"{translation}: пометка ссылается на {original}, а оригинал — {expected_original}")
            problems += check_requirements(translation, expected_original)
    if problems:
        print(f"ОШИБКА: переводы не согласованы с оригиналами ({len(problems)}):", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("Переводы согласованы с оригиналами")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "--print-hash", metavar="ФАЙЛ", help="напечатать отпечаток файла для пометки translation-of или summary-of"
    )
    args = parser.parse_args()
    # Консоль Windows (cp1251) может не уметь отдельные символы: заменяем их, а не падаем
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="replace")
    try:
        if args.print_hash:
            path = Path(args.print_hash)
            if not path.is_file():
                raise FormatError(f"нет файла {args.print_hash}")
            print(fingerprint(path))
            return 0
        return check_all()
    except FormatError as error:
        print(f"ОШИБКА: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
