"""
Проверка разбиения тестов между jobs CI (.github/workflows/tests.yml).

CI делит прогон на две части выражениями -m:
  * Selenium-тесты — матрица браузеров через Grid;
  * всё остальное (API и Playwright) — один раз.
Разбиение должно быть дополняющим: каждый тест попадает ровно в один job. В Phonebook отбор
однажды разошёлся с реальностью из-за приоритета and/or в выражении, и это заметили не сразу.
Скрипт собирает тесты (не запуская их) по каждому выражению и по всему набору и проверяет:
  1. ни одна часть не пуста;
  2. пересечение частей пустое;
  3. объединение частей — ровно весь набор.

Запуск (выражения по умолчанию — те же, что в workflow):
    python scripts/check_ci_split.py
    python scripts/check_ci_split.py "selenium" "not selenium"
"""

import os
import subprocess
import sys

DEFAULT_EXPRESSIONS = ("selenium", "not selenium")


def collect(markexpr: str | None) -> set[str]:
    """ID тестов, которые pytest отберёт по выражению (None — весь набор)."""
    command = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]
    if markexpr is not None:
        command += ["-m", markexpr]
    # PYTHONUTF8: на Windows дочерний pytest иначе пишет в кодировке консоли, и вывод не читается
    env = os.environ | {"PYTHONUTF8": "1"}
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    # 0 — тесты собраны, 5 — не собрано ни одного (это проверяется ниже); остальное — ошибка сбора
    if result.returncode not in (0, 5):
        print(result.stdout + result.stderr)
        raise SystemExit(f"❌ pytest не смог собрать тесты (код {result.returncode}) для -m {markexpr!r}")
    return {line.strip() for line in result.stdout.splitlines() if "::" in line}


def main(args: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # эмодзи и кириллица в консоли Windows
    expressions = tuple(args) if args else DEFAULT_EXPRESSIONS
    if len(expressions) < 2:
        print("❌ Нужно минимум два выражения -m")
        return 2

    everything = collect(None)
    parts = {expr: collect(expr) for expr in expressions}
    ok = True

    print(f"Всего тестов: {len(everything)}")
    for expr, tests in parts.items():
        print(f"  -m {expr!r}: {len(tests)}")
        if not tests:
            print(f"❌ Выражение {expr!r} не отобрало ни одного теста")
            ok = False

    exprs = list(parts)
    for i, first in enumerate(exprs):
        for second in exprs[i + 1 :]:
            common = parts[first] & parts[second]
            if common:
                ok = False
                print(f"❌ Тесты попадают и в {first!r}, и в {second!r} ({len(common)}):")
                for test in sorted(common):
                    print(f"     {test}")

    union = set().union(*parts.values())
    for title, diff in (("не попали ни в один job", everything - union), ("лишние", union - everything)):
        if diff:
            ok = False
            print(f"❌ Тесты {title} ({len(diff)}):")
            for test in sorted(diff):
                print(f"     {test}")

    total = sum(len(tests) for tests in parts.values())
    if ok:
        print(f"✅ Разбиение дополняющее: {' + '.join(str(len(t)) for t in parts.values())} = {total}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
