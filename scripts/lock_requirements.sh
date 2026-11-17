#!/usr/bin/env bash
# Пересобирает lock-файлы зависимостей из исходников:
#   requirements.in     -> requirements.txt      (всё дерево пакетов тестов)
#   requirements-dev.in -> requirements-dev.txt  (ruff, pre-commit и их зависимости)
# Запуск — только в контейнере с образом из строки FROM в Dockerfile (команда — в commands.md):
#   docker run --rm -v "${PWD}:/src" -w /src <образ из FROM> bash scripts/lock_requirements.sh
# Дополнительные аргументы уходят в оба вызова pip-compile, например:
#   bash scripts/lock_requirements.sh --upgrade-package requests
#
# Режим проверки (единственный аргумент; так его запускает job Lint):
#   bash scripts/lock_requirements.sh --check
# компилирует оба *.in во временный каталог и сравнивает пины «имя==версия» с закоммиченными
# lock-файлами (scripts/compare_lock_pins.py): код 0 — совпадают, 1 — расходятся (печатается,
# что добавится, исчезнет и изменится) или запуск не в том окружении, 2 — ошибка аргументов
# или разбора lock-файла; сбой pip-compile — его код. Рабочее дерево не меняется.
# Сравниваются пины, а не текст: шапка и пометки «# via» зависят от версии pip-tools.
#
# Почему только в контейнере: pip-compile разрешает зависимости для текущей платформы и версии
# Python. На Windows в дерево попали бы пакеты только для Windows (colorama и др.), на другой
# версии Python — другие версии пакетов, и lock-файл разошёлся бы с тем, что ставит образ.
#
# Без --upgrade: пакеты, уже записанные в lock-файле, остаются на своих версиях, пока исходник
# их допускает (обновление — осознанно, через --upgrade-package или Dependabot).
# Без хэшей: цель — воспроизводимое дерево версий; хэши мешали бы слоям (requirements-dev.txt
# поверх requirements.txt) и обновлениям Dependabot.
set -euo pipefail

# Версия pip-tools — наша, с версией Dependabot её не сверяем: у Dependabot своя
# (dependabot-core, python/helpers/requirements.txt), и он меняет её сам. Расхождение не мешает:
# job Lint сравнивает пины, а не текст, а шапку lock-файла Dependabot после пересборки
# возвращает исходную. pip и click не закреплены — в venv остаётся pip из образа, click ставится
# последний: по changelog pip-tools 7.6.1 поддерживает pip 26.2, а 7.6.2 совместим с click 8.5
# и больше не дописывает в шапку --no-index, которого не передавали.
PIP_TOOLS_VERSION=7.6.2

usage() {
    echo "Использование: bash scripts/lock_requirements.sh [аргументы pip-compile] | --check" >&2
    exit 2
}

check_mode=false
for arg in "$@"; do
    if [ "$arg" = "--check" ]; then
        # --check сравнивает с закоммиченным состоянием — аргументы pip-compile (например,
        # --upgrade-package) сделали бы сравнение бессмысленным
        [ "$#" -eq 1 ] || usage
        check_mode=true
    fi
done

cd "$(dirname "$0")/.."

# --- Охрана: Linux и та же версия Python (major.minor), что в образе из Dockerfile ---
docker_image=$(sed -n 's/^FROM[[:space:]]\{1,\}\([^[:space:]]\{1,\}\).*/\1/p' Dockerfile | head -n 1)
want_python=$(printf '%s\n' "$docker_image" | sed -n 's/^python:\([0-9]\{1,\}\.[0-9]\{1,\}\).*/\1/p')
if [ -z "$want_python" ]; then
    echo "Не удалось разобрать версию Python из строки FROM в Dockerfile: '$docker_image'" >&2
    exit 1
fi
have_python=$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null || true)
if [ "$(uname -s)" != "Linux" ] || [ "$have_python" != "$want_python" ]; then
    echo "lock_requirements.sh работает только на Linux с Python $want_python (образ $docker_image)," >&2
    echo "а здесь: $(uname -s), Python ${have_python:-не найден}. Запусти в контейнере (см. commands.md):" >&2
    echo "  docker run --rm -v \"\${PWD}:/src\" -w /src $docker_image bash scripts/lock_requirements.sh" >&2
    exit 1
fi

# --- pip-tools во временном venv: не смешивается с пакетами проекта и не остаётся после запуска ---
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT
venv_dir="$work_dir/venv"
python3 -m venv "$venv_dir"
"$venv_dir/bin/python" -m pip install --quiet --disable-pip-version-check "pip-tools==$PIP_TOOLS_VERSION"
# Версии в лог: pip и click не закреплены, при сбое видно, с какими шёл запуск
"$venv_dir/bin/python" - <<'PY'
from importlib.metadata import version
print("pip-tools", version("pip-tools"), "| pip", version("pip"), "| click", version("click"))
PY

if [ "$check_mode" = false ]; then
    # Порядок важен: requirements-dev.in ссылается на requirements.txt через -c
    "$venv_dir/bin/pip-compile" --quiet --strip-extras -o requirements.txt requirements.in "$@"
    "$venv_dir/bin/pip-compile" --quiet --strip-extras -o requirements-dev.txt requirements-dev.in "$@"
    exit 0
fi

# --- Проверка: пересборка во временный каталог и сравнение пинов с закоммиченными ---
# Текущие lock-файлы копируются туда же: pip-compile берёт записанные в выходном файле версии
# как предпочтение — так же, как при обычной пересборке. requirements-dev.in ссылается через -c
# на закоммиченный requirements.txt (путь — относительно самого .in): его и проверяем.
out_dir="$work_dir/out"
mkdir "$out_dir"
cp requirements.txt requirements-dev.txt "$out_dir/"
"$venv_dir/bin/pip-compile" --quiet --strip-extras -o "$out_dir/requirements.txt" requirements.in
"$venv_dir/bin/pip-compile" --quiet --strip-extras -o "$out_dir/requirements-dev.txt" requirements-dev.in
# Код сравнения (0 / 1 / 2) — код всего скрипта
python3 scripts/compare_lock_pins.py . "$out_dir"
