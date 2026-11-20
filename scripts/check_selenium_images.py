"""
Проверка тегов образов Selenium Grid в docker-compose*.yml.

Selenium публикует один и тот же образ узла под двумя схемами тегов: по версии Grid
(4.51.0-20261010) и по версии браузера (155.0-20261010, 99.0-20220327). Dependabot сравнивает
числа и однажды перевёл узлы на теги браузеров (PR #32), в другой раз — на старые браузеры 99.x
(PR #34). Во втором случае Edge не стартовал, а Chrome и Firefox на браузерах 2022 года прошли
зелёными: откат браузера тесты не ловят. Поэтому теги проверяются отдельно, до тестов.

Правила:
  1. Тег каждого образа selenium/* — релиз Grid 4 с датой сборки (GRID_TAG_PATTERN).
  2. Все образы на одном теге: хаб и узлы из одного релиза, иначе узлы могут не подключиться.

Коды выхода: 0 — порядок; 1 — нарушение правил; 2 — ошибка формата или использования
(в том числе ни одного образа selenium/*: проверка не должна молча проходить, если compose
перестроили и образы переехали).

Запуск (по умолчанию — все docker-compose*.yml в корне репозитория):
    python scripts/check_selenium_images.py
    python scripts/check_selenium_images.py путь/к/compose.yml ...
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Тег релиза Grid 4: «4.<минор>.<патч>-<дата сборки ГГГГММДД>». Связан с правилом ignore
# в .github/dependabot.yml (selenium/*, versions ">= 5"): бот предлагает только 4.x, проверка
# пропускает только 4.x. Мажор Selenium меняется вручную — правило и шаблон вместе (commands.md).
GRID_TAG_PATTERN = re.compile(r"^4\.\d+\.\d+-\d{8}$")

# Строка «image: selenium/<имя>[:<тег>]», значение — в кавычках или без. Тег необязателен в шаблоне
# намеренно: образ без тега (latest) — тоже нарушение, а не «не нашли образ».
IMAGE_LINE = re.compile(r"""^\s*image:\s*["']?(selenium/[\w.-]+)(?::([^\s"'#]+))?["']?\s*(?:#.*)?$""")

HINT = (
    "похоже на тег версии браузера — Grid-образы обновляются только внутри 4.x, см. commands.md, раздел про Dependabot"
)


def find_images(path: Path) -> list[tuple[int, str, str]]:
    """Образы selenium/* в файле: (номер строки, образ, тег; пустой тег — тега нет)."""
    images = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = IMAGE_LINE.match(line)
        if match:
            images.append((number, match.group(1), match.group(2) or ""))
    return images


def main(args: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # эмодзи и кириллица в консоли Windows
    files = [Path(arg) for arg in args] if args else sorted(ROOT.glob("docker-compose*.yml"))
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        print(f"❌ Файлы не найдены: {', '.join(missing)}")
        return 2
    if not files:
        print(f"❌ В {ROOT} нет ни одного docker-compose*.yml")
        return 2

    found = []  # (файл, строка, образ, тег)
    for path in files:
        found += [(path.name, number, image, tag) for number, image, tag in find_images(path)]
    if not found:
        names = ", ".join(path.name for path in files)
        print(f"❌ Ни одного образа selenium/* в {names}: проверять нечего — compose перестроили?")
        return 2

    ok = True
    for file_name, number, image, tag in found:
        if not GRID_TAG_PATTERN.match(tag):
            shown = tag or "(без тега)"
            print(f"❌ {file_name}:{number}: {image}:{shown} — тег не релиза Grid 4 (4.x.y-ГГГГММДД); {HINT}")
            ok = False

    tags = {tag for _, _, _, tag in found}
    if len(tags) > 1:
        print("❌ Образы Selenium на разных тегах — хаб и узлы должны быть из одного релиза Grid:")
        for file_name, number, image, tag in found:
            print(f"   {file_name}:{number}: {image} → {tag or '(без тега)'}")
        ok = False

    if ok:
        print(f"✅ Образы Selenium ({len(found)}) — на одном теге Grid 4: {tags.pop()}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
