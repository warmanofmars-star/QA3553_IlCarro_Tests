import os

# Исключаем мусорные папки
IGNORE_DIRS = ['.venv', '.git', '__pycache__', '.pytest_cache', 'assets', 'screenshots']

with open('full_project_for_ai_ilcaro.txt', 'w', encoding='utf-8') as outfile:
    for root, dirs, files in os.walk('.'):
        # Убираем ненужные папки из обхода
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            # Берем только код, конфиги и ридми
            if file.endswith(('.py', '.yml', '.env', '.md')):
                filepath = os.path.join(root, file)

                outfile.write(f"\n\n{'=' * 60}\n")
                outfile.write(f"📄 FILE: {filepath}\n")
                outfile.write(f"{'=' * 60}\n\n")

                try:
                    with open(filepath, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f"Ошибка чтения файла: {e}\n")

print("Готово! Файл full_project_for_ai_ilcaro.txt создан.")
