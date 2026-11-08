#!/usr/bin/env bash
# Отправляет сообщение в Telegram через Bot API (sendMessage). Вызывается из job'ов уведомлений
# в .github/workflows/tests.yml:  bash scripts/send_telegram.sh
#
# Всё берётся из окружения: TELEGRAM_TOKEN (токен бота), TELEGRAM_TO (id чата),
# TELEGRAM_TEXT (текст). Workflow кладёт туда секреты через env, а не вклеивает в команду.
# TELEGRAM_API_URL — адрес Bot API (по умолчанию https://api.telegram.org); переопределяется,
# чтобы проверить скрипт на локальной заглушке.
#
# Тело запроса — JSON, который собирает python3 (json.dumps) прямо из переменных окружения,
# и curl отправляет его файлом (--data-binary @файл). Раньше текст передавался через
# curl --variable '%TELEGRAM_TEXT=' (импорт с пустым значением по умолчанию), и в curl 8.5.0
# с ubuntu-24.04 это давало пустой text: при наличии «=» curl ищет переменную окружения
# с именем «TELEGRAM_TEXT=» (имя не обрезано до «=», исправлено в 8.10), не находит её
# и подставляет значение по умолчанию — пустую строку. Telegram отвечал
# «Bad Request: message text is empty». json.dumps не зависит от версии curl, кириллица
# и переносы строк уходят как есть (экранирование \uXXXX — штатный JSON).
#
# Почему токен не утечёт:
#   * его нет в командной строке: curl сам читает переменную окружения (--variable %ИМЯ,
#     без значения по умолчанию — эта форма в 8.5 работает) и подставляет её в URL ({{ИМЯ}}).
#     В аргументах процесса (ps, /proc) и в трассировке set -x видно только имя переменной;
#   * в тело запроса токен не попадает: python читает только TELEGRAM_TO и TELEGRAM_TEXT;
#   * проверка «секрет задан» тоже не раскрывает значение (см. ниже);
#   * curl без -v: URL с токеном не печатается, а в ответе Bot API токена нет;
#   * GitHub дополнительно маскирует значения секретов в логе.
# Нужен curl 8.3+ (--variable, --expand-*); на ubuntu-24.04 — 8.5.
#
# Сбой отправки (ответ "ok":false или ошибка curl) — красный job (exit 1) с ответом в логе.
# Раньше это было лишь предупреждение, и job оставался зелёным, хотя сообщение не ушло:
# сбой скрывался (в первом прогоне на main Telegram отклонил пустой текст, а job был зелёным).
# Краснить можно без вреда: уведомление — последний job, тесты, отчёт и выкладка
# к этому моменту уже завершены, и его провал на них не влияет.
# Не заданные секреты — по-прежнему только предупреждение: это осознанная настройка (например,
# форк без секретов), а не сбой.

set -uo pipefail
{ set +x; } 2>/dev/null  # трассировку выключаем, даже если её включили снаружи

api_url="${TELEGRAM_API_URL:-https://api.telegram.org}"

# ${ИМЯ:+x} раскрывается в «x» или в пустоту: проверка не подставляет значение секрета в команду,
# и даже при set -x в трассировке будет «[ -z x ]», а не токен
if [ -z "${TELEGRAM_TOKEN:+x}" ] || [ -z "${TELEGRAM_TO:+x}" ]; then
  echo "::warning::Секреты Telegram (токен бота и id чата) не заданы — уведомление не отправлено"
  exit 0
fi

body=$(mktemp)
trap 'rm -f "$body"' EXIT

# Пустой текст — ошибка вызывающего (сломан шаблон в workflow), а не сбой Telegram:
# отправлять нечего, job должен покраснеть. Текст из одних пробелов Telegram тоже считает пустым
python3 - "$body" <<'PY'
import json
import os
import sys

text = os.environ.get("TELEGRAM_TEXT", "")
if not text.strip():
    sys.exit(3)
payload = {
    "chat_id": os.environ["TELEGRAM_TO"],
    "text": text,
    "disable_web_page_preview": True,
}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write(json.dumps(payload))
PY
rc=$?
# Отдельный код 3 — чтобы не выдать за «пустой текст» отсутствие python3 или иной сбой сборки
if [ "$rc" -eq 3 ]; then
  echo "::error::Текст уведомления (TELEGRAM_TEXT) пуст — сообщение не отправлено"
  exit 1
elif [ "$rc" -ne 0 ]; then
  echo "::error::Не удалось собрать тело запроса к Telegram (код python3 $rc) — сообщение не отправлено"
  exit 1
fi

response=$(curl -sS --max-time 30 --retry 3 \
  --variable '%TELEGRAM_TOKEN' \
  --expand-url "${api_url}/bot{{TELEGRAM_TOKEN}}/sendMessage" \
  -H 'Content-Type: application/json' \
  --data-binary "@${body}")
code=$?

# Bot API отвечает JSON {"ok":true,...}; при ошибке — {"ok":false,"description":"..."} без токена
if [ "$code" -eq 0 ] && printf '%s' "$response" | grep -q '"ok":true'; then
  echo "Уведомление в Telegram отправлено"
  exit 0
fi
echo "::error::Уведомление в Telegram не отправлено (код curl $code): $response"
exit 1
