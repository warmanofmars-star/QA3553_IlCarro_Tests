"""
Проверка результатов Allure на секреты перед генерацией и публикацией отчёта.

Отчёт IlCarro публикуется на GitHub Pages, то есть публичен. Раньше в него попадали пароли
временных аккаунтов: параметр шага @allure.step с паролем, repr dataclass в трассе xfail.
Источники закрыты в коде, а этот скрипт не даёт им вернуться незаметно: CI (job Allure report)
и Jenkins запускают его до генерации отчёта, находка — красный job, отчёт не публикуется.

Что ищет (в каталогах allure-results, включая вложения):
  1. JWT — то же регулярное выражение, что в research/common.py. Ищется во всех файлах, в том
     числе бинарных (скриншоты, видео): токен мог попасть куда угодно.
  2. Параметр теста или шага (в том числе шагов фикстур в *-container.json), чьё имя содержит
     password / token / secret, с незамаскированным значением. Замаскированным считается значение
     из одних звёздочек или пустое. Режим MASKED сам по себе не считается: allure-pytest при нём
     всё равно пишет настоящее значение в result.json (см. фикстуру _mask_secret_params в conftest.py).
     Правило имён то же, что у фикстуры, — меняешь здесь, меняй и там.
  3. Пароль в repr dataclass: password='…' — в любом текстовом поле результата (statusDetails.trace,
     message, имена шагов) и в текстовых вложениях. См. комментарий к REPR_PASSWORD.

Значения найденного НЕ печатаются: только файл, поле и количество.

Запуск:
    python scripts/scan_report_secrets.py allure-results
    python3 scripts/scan_report_secrets.py allure-results-*      # как в CI: несколько каталогов
Коды выхода: 0 — чисто, 1 — найдены секреты, 2 — нечего проверять (нет каталога или файлов
результатов): пустая проверка не должна выглядеть как «секретов нет».
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

JWT = re.compile(rb"eyJ[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]*")
SECRET_PARAM_NAME = re.compile(r"password|token|secret", re.IGNORECASE)
# Пароль, напечатанный repr dataclass: User(..., password='Abc#123') — так pytest выводит аргументы
# теста в трассе. Ловится именно repr-формат с ОДИНАРНЫМИ кавычками: строки исходника в трассе
# (password="abc123" в вызове генератора) не ловятся, потому что ruff format приводит строки кода
# к двойным кавычкам. Пустое значение и звёздочки — не секрет. Ограничение: repr берёт двойные
# кавычки, если в значении есть одинарная, — такой пароль правило пропустит (генератор паролей
# проекта кавычек не использует)
REPR_PASSWORD = re.compile(r"password='(?!\**')[^']*'", re.IGNORECASE)
# Нормализованный путь поля: индексы списков заменены на [], чтобы одинаковые находки складывались
_INDEX = re.compile(r"\[\d+\]")


def _is_masked(value) -> bool:
    text = str(value if value is not None else "").strip().strip("'\"")
    return text == "" or set(text) == {"*"}


def _secret_params(node, path: str):
    """Пути к незамаскированным параметрам-секретам во всём дереве JSON результата."""
    if isinstance(node, dict):
        for i, param in enumerate(node.get("parameters") or []):
            if not isinstance(param, dict):
                continue
            if SECRET_PARAM_NAME.search(str(param.get("name", ""))) and not _is_masked(param.get("value")):
                yield f"{path}.parameters[{i}] (имя: {param.get('name')})"
        for key, value in node.items():
            if key != "parameters" and isinstance(value, (dict, list)):
                yield from _secret_params(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from _secret_params(item, f"{path}[{i}]")


def _strings(node, path: str):
    """(путь, строка) для всех строковых значений JSON."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from _strings(item, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def scan(directories: list[Path]) -> tuple[int, Counter]:
    """Возвращает число просмотренных файлов и находки {(файл, поле, тип): количество}."""
    files = [f for d in directories if d.is_dir() for f in sorted(d.rglob("*")) if f.is_file()]
    findings: Counter = Counter()
    for f in files:
        raw = f.read_bytes()
        jwt_count = len(JWT.findall(raw))
        if jwt_count:
            findings[(str(f), "(содержимое файла)", "JWT")] += jwt_count
        if f.name.endswith(("-result.json", "-container.json")):
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                findings[(str(f), "(файл)", "не разбирается как JSON — проверить вручную")] += 1
                continue
            for field_path in _secret_params(data, ""):
                findings[(str(f), _INDEX.sub("[]", field_path), "секретный параметр без маски")] += 1
            for field_path, text in _strings(data, ""):
                count = len(REPR_PASSWORD.findall(text))
                if count:
                    findings[(str(f), _INDEX.sub("[]", field_path), "пароль в repr (password='…')")] += count
            continue
        # Текстовые вложения (логи, JSON ответов); бинарные (скриншоты, видео) — только JWT выше
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        count = len(REPR_PASSWORD.findall(text))
        if count:
            findings[(str(f), "(текст вложения)", "пароль в repr (password='…')")] += count
    return len(files), findings


def main(argv: list[str]) -> int:
    directories = [Path(a) for a in argv] or [Path("allure-results")]
    missing = [str(d) for d in directories if not d.is_dir()]
    if missing:
        print(f"Нет каталогов результатов: {', '.join(missing)}")
        return 2
    total, findings = scan(directories)
    results = sum(1 for d in directories for _ in d.rglob("*-result.json"))
    if results == 0:
        print(f"В {', '.join(map(str, directories))} нет ни одного *-result.json — проверять нечего")
        return 2
    for (file, field_path, kind), count in sorted(findings.items()):
        print(f"НАЙДЕНО: {kind}: {file}: {field_path} — {count} раз")
    print(f"Файлов просмотрено: {total} (результатов тестов: {results}); находок: {sum(findings.values())}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
