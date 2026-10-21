# 🚗 Шпаргалка по командам проекта IlCarro (Cheatsheet)

## 🏃‍♂️ Запуск тестов локально (Без Docker)
Перед локальным запуском убедись, что в `.env` стоит `USE_SELENOID=false`.

**Запуск всех тестов параллельно (в 3 потока) с видео и отчетом:**
`pytest tests/ -n 3 --video=on --clean-alluredir --alluredir=allure-results`

**Запуск с выбором конкретного браузера (`chrome`, `firefox`, `edge`):**
`pytest tests/ -n 3 --browser_name=firefox --clean-alluredir --alluredir=allure-results`

**Быстрый прогон только API-слоя (без браузеров и UI-ожиданий):**
`pytest -m "api" -v`

**Запуск проверок безопасности и BOLA:**
`pytest -m "security" -v`

**Запуск по связке маркеров (логическое И / ИЛИ / НЕ):**
`pytest -m "api and security" -v`
`pytest -m "smoke and not hybrid" -v`
`pytest -m "hybrid" -v`

**Запуск конкретного файла (например, мутации или секьюрити):**
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

**Полный запуск (Сборка образа -> Запуск Selenoid -> Прогон в Chrome -> Выход):**
`docker compose up --build --exit-code-from qa-framework`

**Запуск в изолированном Firefox через Docker Compose:**
- В PowerShell (Windows):
  `$env:BROWSER="firefox"; docker compose up --build --exit-code-from qa-framework`
- В Bash / Linux:
  `BROWSER=firefox docker compose up --build --exit-code-from qa-framework`

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

**Точечно обновить образы VNC-браузеров для Selenoid:**
`docker pull selenoid/vnc_chrome:128.0`
`docker pull selenoid/vnc_firefox:125.0`
`docker pull selenoid/video-recorder:latest-release`

---

## 🐙 Полезные команды Git и документации
**Сгенерировать актуальный README.md из скрипта:**
`python make_readme.py`

**Заставить Git "забыть" файл, но оставить его на жестком диске (например, `.env` или `logs/`):**
`git rm --cached <путь_к_файлу>`

**Обновить файл зависимостей проекта:**
`pip freeze > requirements.txt`