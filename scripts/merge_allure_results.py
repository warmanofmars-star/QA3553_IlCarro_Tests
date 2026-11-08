"""
Подготовка результатов Allure из нескольких jobs CI к одному общему отчёту.

В GitHub Actions Selenium-тесты идут в матрице браузеров (chrome, firefox, edge), а API-
и Playwright-тесты — один раз в отдельном job. Каждый job сохраняет папку
allure-results-<метка>: allure-results-chrome, allure-results-api-playwright и т. д.
Скрипт запускается перед `allure generate` и:

  1. Уникализирует Selenium-тесты по браузеру. Один и тот же тест в Chrome и Firefox имеет
     одинаковые historyId и testCaseId — Allure счёл бы их одним тестом с «ретраем» и показал
     бы один результат. К идентификаторам дописывается браузер, к имени и сьюту — [CHROME] и т. п.
     Папки не браузеров (тесты, которые идут один раз) не трогаются: так их имена остаются
     чистыми, а история — та же, что в локальном отчёте.
  2. Склеивает environment.properties всех папок в один (Allure читает только один такой
     файл; пишет их pytest_sessionfinish в conftest.py): разные значения ключа — через «; ».
  3. Пишет executor.json — блок Executors и ссылки из графика трендов на прогон CI.
  4. Считает итог (passed / xfailed / failed / broken / skipped) и, если запущен в GitHub
     Actions, отдаёт его в выходы шага (GITHUB_OUTPUT) для уведомления в Telegram.

Запуск:
    python scripts/merge_allure_results.py allure-results-api-playwright allure-results-chrome ...
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

# Те же браузеры, что в матрице workflow и SUPPORTED_BROWSERS в drivers/factory.py.
# Не импортируем оттуда: job отчёта не ставит зависимости проекта (Selenium и т. д.)
BROWSERS = ("chrome", "firefox", "edge")

ENV_SEPARATOR = "; "  # не запятая: в значениях (например, в выражении -m) она встречается сама


def read_properties(path: Path) -> dict[str, str]:
    """Простой парсер .properties: строки КЛЮЧ=ЗНАЧЕНИЕ."""
    if not path.exists():
        return {}
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def result_files(folder: Path) -> list[Path]:
    return sorted(folder.glob("*-result.json"))


def tag_results_with_browser(folder: Path, browser: str) -> int:
    """Дописывает браузер к идентификаторам и именам тестов. Возвращает число файлов."""
    label = browser.upper()
    files = result_files(folder)
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))

        # Идентификаторы, по которым Allure склеивает тесты и строит историю
        for key in ("historyId", "testCaseId"):
            if key in data:
                data[key] = f"{data[key]}-{browser}"

        # Человекочитаемые имена
        for key in ("name", "fullName"):
            if key in data:
                data[key] = f"{data[key]} [{label}]"
        for item in data.get("labels", []):
            if item.get("name") == "suite":
                item["value"] = f"{item['value']} ({label})"

        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return len(files)


def merge_environment(folders: list[Path]) -> dict[str, str]:
    """Объединяет environment.properties: разные значения одного ключа — через ENV_SEPARATOR."""
    merged: dict[str, list[str]] = {}
    for folder in folders:
        for key, value in read_properties(folder / "environment.properties").items():
            values = merged.setdefault(key, [])
            if value not in values:
                values.append(value)

    environment = {key: ENV_SEPARATOR.join(values) for key, values in merged.items()}

    # Данные о прогоне CI (переменные GITHUB_* задаёт сам GitHub Actions)
    if os.getenv("GITHUB_ACTIONS"):
        environment["CI"] = "GitHub Actions"
        environment["Event"] = os.getenv("GITHUB_EVENT_NAME", "")
        environment["Branch"] = os.getenv("GITHUB_REF_NAME", "")
        environment["Commit"] = os.getenv("GITHUB_SHA", "")[:7]
        environment["Run"] = os.getenv("GITHUB_RUN_NUMBER", "")
    return environment


def write_executor(folder: Path) -> None:
    """executor.json: блок Executors и ссылки из графика трендов на конкретные прогоны."""
    if not os.getenv("GITHUB_ACTIONS"):
        return
    run_url = (
        f"{os.getenv('GITHUB_SERVER_URL')}/{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}"
    )
    executor = {
        "name": "GitHub Actions",
        "type": "github",
        "buildName": f"#{os.getenv('GITHUB_RUN_NUMBER')} ({os.getenv('GITHUB_REF_NAME')})",
        "buildOrder": int(os.getenv("GITHUB_RUN_NUMBER", "0")),
        "buildUrl": run_url,
    }
    (folder / "executor.json").write_text(json.dumps(executor), encoding="utf-8")


def outcome(data: dict) -> str:
    """Итог одного результата в терминах pytest.

    Allure не различает xfail и skip: оба получают статус skipped. allure-pytest пишет
    в statusDetails.message для xfail текст, начинающийся с XFAIL, — по нему и отличаем.
    Строгий XPASS у allure-pytest — failed, его отдельно не выделяем: это тоже красный тест.
    """
    status = data.get("status", "unknown")
    if status == "skipped" and data.get("statusDetails", {}).get("message", "").startswith("XFAIL"):
        return "xfailed"
    return status


def summarize(folders: list[Path]) -> Counter:
    counts: Counter = Counter()
    for folder in folders:
        for path in result_files(folder):
            counts[outcome(json.loads(path.read_text(encoding="utf-8")))] += 1
    return counts


def write_github_outputs(counts: Counter) -> None:
    output = os.getenv("GITHUB_OUTPUT")
    if not output:
        return
    keys = ("passed", "xfailed", "failed", "broken", "skipped")
    with open(output, "a", encoding="utf-8") as fh:
        for key in keys:
            fh.write(f"{key}={counts.get(key, 0)}\n")
        fh.write(f"total={sum(counts.values())}\n")


def main(args: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # эмодзи и кириллица в консоли Windows
    folders = [Path(arg) for arg in args if Path(arg).is_dir()]
    for arg in args:
        if not Path(arg).is_dir():
            # Например, job упал до сохранения результатов
            print(f"⚠ Папка {arg} не найдена — пропускаю")
    if not folders:
        print("❌ Нет ни одной папки с результатами")
        return 1

    for folder in folders:
        label = folder.name.removeprefix("allure-results-")
        if label in BROWSERS:
            count = tag_results_with_browser(folder, label)
            print(f"✅ {folder}: помечено результатов: {count} ({label})")
        else:
            print(f"✅ {folder}: результатов: {len(result_files(folder))} (без пометки браузера)")

    # Общий environment и executor кладём в первую папку, из остальных убираем дубли
    environment = merge_environment(folders)
    for folder in folders[1:]:
        (folder / "environment.properties").unlink(missing_ok=True)
    (folders[0] / "environment.properties").write_text(
        "".join(f"{key}={value}\n" for key, value in environment.items()), encoding="utf-8"
    )
    write_executor(folders[0])
    print("✅ Environment:", environment)

    counts = summarize(folders)
    print("✅ Итог:", dict(counts))
    write_github_outputs(counts)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
