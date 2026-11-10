"""
Склеивает файлы проекта в один текстовый файл, чтобы отдать его ИИ на ревью.

Защита от утечки секретов работает в два слоя:
  1. Файлы с секретами (.env и его варианты) вообще не попадают в выгрузку.
  2. Если секрет всё-таки окажется в каком-то файле в формате КЛЮЧ=значение,
     значение будет заменено на ***REDACTED*** (страховка на случай ошибки).
"""

import os
import re
import sys

OUTPUT_FILE = "full_project_for_ai_ilcaro.txt"

# Папки, которые не нужны для ревью (окружение, кэши, отчёты, IDE)
IGNORE_DIRS = {
    ".venv",
    ".git",
    ".idea",
    "__pycache__",
    ".pytest_cache",
    "assets",
    "screenshots",
    "allure-results",
    "allure-report",
    "logs",
    # Настройки и рабочие копии Claude Code: личные настройки, а в .claude/worktrees —
    # полные копии проекта, которые задвоили бы выгрузку и могут содержать свой .env
    ".claude",
}

# Отдельные файлы, которые пропускаем всегда
IGNORE_FILES = {
    OUTPUT_FILE,  # не склеиваем сами себя
    "exported_contacts.json",  # реальные данные контактов
    "valid_users.jsonl",  # логины/пароли сгенерированных пользователей
}

# Файлы с секретами: .env, .env.local, .env.prod и т.п.
# Исключение — шаблон .env.example: в нём нет секретов, и ИИ полезно его видеть.
SECRET_FILE_PATTERN = re.compile(r"^\.env(\.(?!example$).+)?$")

# .sh — скрипты CI (scripts/send_telegram.sh): их вызывает workflow, без них ревью неполное
VALID_EXTENSIONS = (".py", ".yml", ".yaml", ".md", ".ini", ".json", ".csv", ".txt", ".toml", ".sh")

# Файлы без расширения или с нестандартным именем, которые тоже важны для ревью.
# Раньше Jenkinsfile и Dockerfile.* не попадали в выгрузку.
VALID_EXACT_NAMES = {
    "Dockerfile",
    "Dockerfile.jenkins",
    "Jenkinsfile",
    ".gitignore",
    ".dockerignore",
}

# Страховка: строки вида DB_PASSWORD=..., TG_BOT_TOKEN=..., API_SECRET=...
# (ключ БЕЗ пробелов вокруг "=", как в .env-файлах) — значение маскируем.
SECRET_LINE_PATTERN = re.compile(
    r"^([A-Z0-9_]*(PASSWORD|TOKEN|SECRET)[A-Z0-9_]*=).+$",
    flags=re.MULTILINE,
)


def read_text(filepath: str) -> str:
    """Читает файл, перебирая кодировки.

    Нужно, например, для requirements.txt, сохранённого PowerShell в UTF-16.
    """
    for encoding in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            with open(filepath, encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "[!] Не удалось прочитать файл ни в одной из кодировок\n"


def should_include(filename: str) -> bool:
    """Решает, попадает ли файл в выгрузку."""
    if filename in IGNORE_FILES or SECRET_FILE_PATTERN.match(filename):
        return False
    return filename.endswith(VALID_EXTENSIONS) or filename in VALID_EXACT_NAMES


def main() -> None:
    # Консоль Windows (и Git Bash при выводе в канал) пишет в cp1251, где нет эмодзи: print упал бы
    # с UnicodeEncodeError уже после записи выгрузки. Символ, которого нет в кодировке консоли,
    # заменяется на «?», а сама выгрузка всегда в UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    included = 0

    with open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
        for root, dirs, files in os.walk("."):
            # Изменяем dirs "на месте", чтобы os.walk не заходил в игнорируемые папки.
            # sorted() — чтобы порядок файлов в выгрузке был одинаковым от запуска к запуску.
            dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS)

            for filename in sorted(files):
                if not should_include(filename):
                    continue

                filepath = os.path.join(root, filename)
                content = SECRET_LINE_PATTERN.sub(r"\1***REDACTED***", read_text(filepath))

                outfile.write(f"\n\n{'=' * 60}\n")
                outfile.write(f"📄 FILE: {filepath}\n")
                outfile.write(f"{'=' * 60}\n\n")
                outfile.write(content)
                included += 1

    print(f"✅ Готово! В {OUTPUT_FILE} собрано файлов: {included}. Файлы .env исключены.")


if __name__ == "__main__":
    main()
