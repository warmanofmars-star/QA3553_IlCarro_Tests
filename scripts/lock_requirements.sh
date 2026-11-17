#!/usr/bin/env bash
# Пересобирает lock-файлы зависимостей из исходников:
#   requirements.in     -> requirements.txt      (всё дерево пакетов тестов)
#   requirements-dev.in -> requirements-dev.txt  (ruff, pre-commit и их зависимости)
# Запуск — только в контейнере с образом из строки FROM в Dockerfile (команда — в commands.md):
#   docker run --rm -v "${PWD}:/src" -w /src <образ из FROM> bash scripts/lock_requirements.sh
# Дополнительные аргументы уходят в оба вызова pip-compile, например:
#   bash scripts/lock_requirements.sh --upgrade-package requests
#
# Почему только в контейнере: pip-compile разрешает зависимости для текущей платформы и версии
# Python. На Windows в дерево попали бы пакеты только для Windows (colorama и др.), на другой
# версии Python — другие версии пакетов, и lock-файл разошёлся бы с тем, что ставит образ.
# Job Lint запускает этот же скрипт и требует пустой git diff: lock-файл соответствует исходнику.
#
# Без --upgrade: пакеты, уже записанные в lock-файле, остаются на своих версиях, пока исходник
# их допускает (обновление — осознанно, через --upgrade-package или Dependabot).
# Без хэшей: цель — воспроизводимое дерево версий; хэши мешали бы слоям (requirements-dev.txt
# поверх requirements.txt) и обновлениям Dependabot.
set -euo pipefail

# Совпадает с версией pip-compile, которую поддерживает Dependabot (документация GitHub
# «Supported ecosystems and repositories», строка pip-compile): Dependabot пересобирает
# эти же lock-файлы, и шапки и формат у них должны совпадать с нашими.
PIP_TOOLS_VERSION=7.5.3
# pip в venv с pip-tools. pip-tools работает с внутренним API pip, и новый pip его ломает:
# с pip 26.2 из образа 7.5.3 падает (ImportError: stdlib_pkgs). По changelog pip-tools 7.5.3
# совместим с pip 26.0, поддержка 26.2 появилась только в 7.6.1 — берём последний выпуск 26.0.
# Меняется вместе с PIP_TOOLS_VERSION (по её changelog)
PIP_VERSION=26.0.1
# click — по той же причине: с click 8.5 pip-compile 7.5.3 дописывает в шапку lock-файла
# --no-index, которого не передавали (changelog pip-tools 7.6.2: исправлено вместе
# с совместимостью с click 8.5). Последний выпуск click до 8.5
CLICK_VERSION=8.4.2

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
venv_dir=$(mktemp -d)
trap 'rm -rf "$venv_dir"' EXIT
python3 -m venv "$venv_dir"
"$venv_dir/bin/python" -m pip install --quiet --disable-pip-version-check     "pip==$PIP_VERSION" "click==$CLICK_VERSION" "pip-tools==$PIP_TOOLS_VERSION"

# Порядок важен: requirements-dev.in ссылается на requirements.txt через -c
"$venv_dir/bin/pip-compile" --quiet --strip-extras -o requirements.txt requirements.in "$@"
"$venv_dir/bin/pip-compile" --quiet --strip-extras -o requirements-dev.txt requirements-dev.in "$@"
