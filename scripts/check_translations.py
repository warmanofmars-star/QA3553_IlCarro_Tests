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
  1. Каждый *.en.md в репозитории (отслеживаемый или новый, не из .gitignore) несёт пометку, оригинал
     из пометки существует, отпечаток совпадает. Оригинал изменили, а перевод нет — расхождение.
  2. Перевод не содержит непереведённого русского текста: кириллица допустима только в «ёлочках»,
     и каждая такая строка должна дословно встречаться в оригинале. Это тексты интерфейса приложения
     на русском (данные, а не формулировки): в переводе они остаются как есть, перевод — рядом в скобках.
  3. Для requirements.en.md — сверка по смыслу с requirements.md, построчно по разбору таблиц из
     data/requirement_ids.py: те же ID в том же порядке; у каждой строки тот же набор ссылок
     Q-API-NN / Q-UI-NN и тот же мультисет фрагментов в `обратных кавычках`; у REQ — тот же статус
     колонки «Факт» (словарь STATUSES ниже). У DISC вместо «Факта» «Последствие», у OBS в «Факте» —
     ссылки на исследование без статуса: там сверяются только ссылки и код.

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

MARKER = re.compile(r"^<!-- translation-of: (?P<path>\S+) sha256:(?P<hash>[0-9a-f]{12}) -->$")
MARKER_START = "<!-- translation-of:"
Q_REF = re.compile(r"\bQ-(?:API|UI)-\d+\b")
CODE = re.compile(r"`([^`]*)`")
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
def check_marker(translation: str) -> tuple[list[str], str | None]:
    """Расхождения пометки и путь оригинала (None — оригинал не определён)."""
    lines = (ROOT / translation).read_text(encoding="utf-8").splitlines()
    first = lines[0] if lines else ""
    if not first.startswith(MARKER_START):
        return [
            f"{translation}: нет пометки translation-of в первой строке — перевод без оригинала. "
            f"Добавь первой строкой <!-- translation-of: <путь оригинала> sha256:<отпечаток> -->; "
            "отпечаток: python scripts/check_translations.py --print-hash <путь оригинала>"
        ], None
    match = MARKER.match(first)
    if match is None:
        raise FormatError(
            f"{translation}: пометка не по формату: {first!r}. "
            "Нужно: <!-- translation-of: <путь от корня репозитория> sha256:<12 hex> -->"
        )
    original = match["path"]
    if not (ROOT / original).is_file():
        return [f"{translation}: оригинала {original} из пометки translation-of нет в репозитории"], None
    actual = fingerprint(ROOT / original)
    if actual != match["hash"]:
        return [
            f"{translation}: отпечаток оригинала {original} не совпал (в пометке {match['hash']}, "
            f"у оригинала {actual}) — оригинал изменился, а перевод нет. " + FIX_HINT.format(orig=original)
        ], original
    return [], original


def check_cyrillic(translation: str, original: str | None) -> list[str]:
    """Кириллица в переводе — только в «ёлочках», и такая строка дословно есть в оригинале."""
    original_text = (ROOT / original).read_text(encoding="utf-8") if original else ""
    problems = []
    lines = (ROOT / translation).read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
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
        marker_problems, original = check_marker(translation)
        problems += marker_problems
        problems += check_cyrillic(translation, original)
        expected_original = REQUIREMENTS_PAIRS.get(translation)
        if expected_original is not None:
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
    parser.add_argument("--print-hash", metavar="ФАЙЛ", help="напечатать отпечаток файла для пометки translation-of")
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
