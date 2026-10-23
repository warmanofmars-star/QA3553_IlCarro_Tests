# 🚗 Шпаргалка по командам проекта IlCarro (Cheatsheet)

## 🏃‍♂️ Запуск тестов локально (Без Docker)
Перед локальным запуском убедись, что в `.env` стоит `USE_SELENOID=false`.

**Запуск всех тестов параллельно (в 3 потока) с видео и отчетом:**
`pytest tests/ -n 3 --video=on --clean-alluredir --alluredir=allure-results`

**Запуск с выбором конкретного браузера (`chrome`, `firefox`, `edge`):**
`pytest tests/ -n 3 --browser_name=firefox --clean-alluredir --alluredir=allure-results`

**Запуск по категориям (9 маркеров из `pytest.ini`):**
- `pytest -m "smoke" -n 3` — критический путь (13 тестов: 9 UI + 4 API)
- `pytest -m "regression" -n 3` — полный регресс (39 тестов: 24 UI + 15 API)
- `pytest -m "api" -v` — все API-тесты без запуска браузеров (19 тестов)
- `pytest -m "ui" -n 3` — все браузерные тесты Selenium и Playwright (33 теста)
- `pytest -m "playwright" -v` — только быстрые UI-тесты на Playwright (5 тестов)
- `pytest -m "hybrid" -v` — гибридные тесты API + UI (3 теста)
- `pytest -m "security" -v` — проверки безопасности, BOLA и защит форм (15 тестов)
- `pytest -m "contract" -v` — валидация JSON Schema и словарей (3 теста)
- `pytest -m "mutation" -v` — негативные DDT лямбда-мутации (6 тестов)

**Комбинированная фильтрация (логическое И / ИЛИ / НЕ):**
`pytest -m "smoke and api" -v`
`pytest -m "api and security" -v`
`pytest -m "ui and not playwright" -n 3`
`pytest -m "smoke and not hybrid" -v`

**Сухая проверка сбора тестов по маркеру (без реального запуска):**
`pytest -m "smoke" --collect-only`
`pytest -m "regression" --collect-only`

**Запуск конкретного тестового файла:**
`pytest tests/test_api_mutations.py -v`
`pytest tests/test_api_security.py -v`
`pytest tests/test_playwright_add_car.py --clean-alluredir --alluredir=allure-results`

**Запуск Playwright тестов в видимом (Headed) режиме для визуального дебага:**
`pytest tests/test_playwright_add_car.py -s --headed`

---

## 📊 Работа с Allure Report
**Сгенерировать и открыть красивый HTML-отчет в браузере:**
`allure serve allure-results`

**Сгенерировать отчет в статичную папку (без открытия браузера):**
`allure generate allure-results -o allure-report --clean`

---

## 🐳 Запуск через Docker Compose (Изолированная среда)
Перед запуском убедись, что в `.env` стоит `USE_SELENOID=true`.

**Полный запуск (Сборка образа -> Запуск Selenoid -> Прогон всех тестов в Chrome -> Выход):**
`docker compose up --build --exit-code-from qa-framework`

**Запуск в изолированном Firefox через Docker Compose:**
- В PowerShell (Windows):
  `$env:BROWSER="firefox"; docker compose up --build --exit-code-from qa-framework`
- В Bash / Linux:
  `BROWSER=firefox docker compose up --build --exit-code-from qa-framework`

**Запуск только определенной категории (например, `smoke` или `api`) в Docker Compose:**
- В PowerShell (Windows):
  `$env:TEST_MARKER="smoke"; docker compose up --build --exit-code-from qa-framework`
- В Bash / Linux:
  `TEST_MARKER=smoke docker compose up --build --exit-code-from qa-framework`

**Сбросить переменные окружения в PowerShell после кастомного прогона (чтобы вернуть дефолты):**
`Remove-Item Env:\BROWSER -ErrorAction SilentlyContinue`
`Remove-Item Env:\TEST_MARKER -ErrorAction SilentlyContinue`

**Остановка и удаление контейнеров (после завершения работы):**
`docker compose down`

---

## 🧹 Очистка и обслуживание Docker (Если что-то зависло)
**Убить все активные контейнеры проекта и удалить виртуальные тома:**
`docker compose down -v`

**Удалить зависшие "сироты" (orphans) контейнеры:**
`docker compose down --remove-orphans`

**ГЛОБАЛЬНАЯ ОЧИСТКА ДОКЕРА (Осторожно! Удалит все неиспользуемые контейнеры, образы и кэш):**
`docker system prune -a --volumes`

**Точечно обновить образы VNC-браузеров и видеорекордера для Selenoid:**
`docker pull selenoid/vnc_chrome:128.0`
`docker pull selenoid/vnc_firefox:125.0`
`docker pull selenoid/video-recorder:latest-release`

---

## 🐙 Полезные команды Git и утилит проекта
**Сгенерировать актуальный `README.md` из скрипта:**
`python make_readme.py`

**Собрать весь код проекта в единый текстовый файл для ревью:**
`python merge_code.py`

**Заставить Git "забыть" файл, но оставить его на жестком диске (например, `.env` или `logs/`):**
`git rm --cached <путь_к_файлу>`

**Отключить предупреждение Git о замене LF на CRLF в Windows:**
`git config --global core.safecrlf false`

**Обновить файл зависимостей проекта:**
`pip freeze > requirements.txt`