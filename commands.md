# 🚗 Шпаргалка по командам проекта IlCarro (Cheatsheet)

## 🏃‍♂️ Запуск тестов локально (Без Docker)
Перед локальным запуском убедись, что в `.env` стоит `USE_SELENOID=false`[cite: 22].

**Запуск всех тестов параллельно (в 3 потока) с генерацией отчета и видео для Playwright:**
`pytest tests/ -n 3 --video=on --clean-alluredir --alluredir=allure-results`

**Запуск конкретного файла (например, тесты добавления машины):**
`pytest tests/test_playwright_add_car.py --clean-alluredir --alluredir=allure-results`

**Запуск Playwright тестов в видимом (Headed) режиме для дебага:**
`pytest tests/test_playwright_add_car.py -s --headed`[cite: 22]

---

## 📊 Работа с Allure Report
**Сгенерировать и открыть красивый HTML-отчет в браузере:**
`allure serve allure-results`[cite: 22]

**Сгенерировать отчет в статичную папку (без открытия браузера):**
`allure generate allure-results -o allure-report --clean`[cite: 22]

---

## 🐳 Запуск через Docker Compose (Изолированная среда)
Перед запуском убедись, что в `.env` стоит `USE_SELENOID=true`[cite: 22].

**Полный запуск (Сборка образа -> Запуск Селеноида -> Прогон тестов -> Выход):**
`docker compose up --build --exit-code-from qa-framework`[cite: 22]

**Остановка и удаление контейнеров (после завершения работы):**
`docker compose down`[cite: 22]

---

## 🧹 Очистка и обслуживание Docker (Если что-то зависло)
**Убить все активные контейнеры проекта и удалить сети:**
`docker compose down -v`[cite: 22]

**Удалить зависшие "сироты" (orphans) контейнеры:**
`docker compose down --remove-orphans`[cite: 22]

**ГЛОБАЛЬНАЯ ОЧИСТКА ДОКЕРА (Осторожно! Удалит все неиспользуемые контейнеры, образы и кэш на ПК):**
`docker system prune -a --volumes`[cite: 22]

**Точечно обновить образ браузера для Селеноида (если вышла новая версия Chrome):**
`docker pull selenoid/chrome:128.0`[cite: 22]

---

## 🐙 Полезные команды Git
**Заставить Git "забыть" файл, но оставить его на жестком диске (например, `.env` или `logs/`):**
`git rm --cached <путь_к_файлу>`[cite: 22]

**Обновить файл зависимостей проекта:**
`pip freeze > requirements.txt`[cite: 22]