"""
Проверка относительных ссылок в Markdown: файл, на который ведёт ссылка, существует,
а якорь (#...) есть среди заголовков целевого .md.

README.md пишется вручную, и после переименования или удаления файла ссылки на него
молча ломаются: GitHub показывает их как обычные, а открываются они в 404.

Проверяются ссылки вида [текст](путь) вне блоков кода. Внешние (http:, https:, mailto:)
не проверяются: это сеть, а хук должен работать без неё. Якоря — упрощённый алгоритм GitHub:
нижний регистр, без пунктуации, пробелы — дефисы.

Запуск (так же его вызывает хук pre-commit, передавая изменённые .md):
    python scripts/check_links.py README.md commands.md
Код выхода 1, если есть битые ссылки.

Ограничение хука: pre-commit проверяет только изменённые .md. Если удалить файл, на который
ссылается неизменённый README, хук промолчит — это поймает `pre-commit run --all-files`.
"""

import re
import sys
from pathlib import Path

LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"^```.*?^```", re.S | re.M)
HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.M)
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


def _text_without_code(md: Path) -> str:
    return FENCE.sub("", md.read_text(encoding="utf-8"))


def _slug(heading: str) -> str:
    text = re.sub(r"[`*_]", "", heading.strip().lower())
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def _anchors(md: Path) -> set[str]:
    return {_slug(m.group(1)) for m in HEADING.finditer(_text_without_code(md))}


def check(md: Path) -> tuple[int, list[str]]:
    """Возвращает число проверенных ссылок и список ошибок по файлу."""
    targets = [t for t in LINK.findall(_text_without_code(md)) if not SCHEME.match(t)]
    errors = []
    for target in targets:
        path_part, _, anchor = target.partition("#")
        dest = (md.parent / path_part).resolve() if path_part else md.resolve()
        if not dest.exists():
            errors.append(f"{md}: {target} -> нет файла {dest}")
        elif anchor and dest.suffix == ".md" and anchor not in _anchors(dest):
            errors.append(f"{md}: {target} -> нет заголовка #{anchor}")
    return len(targets), errors


def main() -> int:
    total = 0
    errors: list[str] = []
    for arg in sys.argv[1:]:
        count, found = check(Path(arg))
        total += count
        errors += found
    for error in errors:
        print("BROKEN", error)
    print(f"Относительных ссылок: {total}, битых: {len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
