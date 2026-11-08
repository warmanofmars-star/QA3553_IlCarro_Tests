#!/usr/bin/env bash
# Отправляет сообщение в Telegram через Bot API (sendMessage). Вызывается из job'ов уведомлений
# в .github/workflows/tests.yml:  bash scripts/send_telegram.sh
#
# Всё берётся из окружения: TELEGRAM_TOKEN (токен бота), TELEGRAM_TO (id чата),
# TELEGRAM_TEXT (текст). Workflow кладёт туда секреты через env, а не вклеивает в команду.
#
# Почему токен не утечёт:
#   * его нет в командной строке: curl сам читает переменную окружения (--variable %ИМЯ)
#     и подставляет её в URL ({{ИМЯ}}). В аргументах процесса (ps, /proc) и в трассировке
#     set -x видно только имя переменной. Поэтому не используем "...bot${TELEGRAM_TOKEN}/..."
#     в тексте команды: так значение раскрыл бы shell, и оно попало бы в аргументы и в set -x;
#   * проверка «секрет задан» тоже не раскрывает значение (см. ниже);
#   * curl без -v: URL с токеном не печатается, а в ответе Bot API токена нет;
#   * GitHub дополнительно маскирует значения секретов в логе.
# Нужен curl 8.3+ (--variable, --expand-*); на ubuntu-24.04 — 8.5.
#
# Сбой отправки — предупреждение, а не ошибка: недоступный Telegram не должен краснить запуск,
# у которого тесты и выкладка прошли.

set -uo pipefail
{ set +x; } 2>/dev/null  # трассировку выключаем, даже если её включили снаружи

# ${ИМЯ:+x} раскрывается в «x» или в пустоту: проверка не подставляет значение секрета в команду,
# и даже при set -x в трассировке будет «[ -z x ]», а не токен
if [ -z "${TELEGRAM_TOKEN:+x}" ] || [ -z "${TELEGRAM_TO:+x}" ]; then
  echo "::warning::Секреты Telegram (токен бота и id чата) не заданы — уведомление не отправлено"
  exit 0
fi

response=$(curl -sS --max-time 30 --retry 3 \
  --variable '%TELEGRAM_TOKEN' \
  --variable '%TELEGRAM_TO' \
  --variable '%TELEGRAM_TEXT=' \
  --expand-url 'https://api.telegram.org/bot{{TELEGRAM_TOKEN}}/sendMessage' \
  --expand-data-urlencode 'chat_id={{TELEGRAM_TO}}' \
  --expand-data-urlencode 'text={{TELEGRAM_TEXT}}' \
  --data-urlencode 'disable_web_page_preview=true')
code=$?

# Bot API отвечает JSON {"ok":true,...}; при ошибке — {"ok":false,"description":"..."} без токена
if [ "$code" -eq 0 ] && printf '%s' "$response" | grep -q '"ok":true'; then
  echo "Уведомление в Telegram отправлено"
else
  echo "::warning::Уведомление в Telegram не отправлено (код curl $code): $response"
fi
exit 0
