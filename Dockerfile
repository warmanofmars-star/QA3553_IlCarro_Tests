FROM python:3.12-slim

# Устанавливаем системные зависимости, необходимые для Playwright и Allure
RUN apt-get update && apt-get install -y wget gnupg ffmpeg

WORKDIR /app

# Копируем список зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем браузеры для Playwright
RUN playwright install chromium
RUN playwright install-deps

# Копируем весь проект внутрь контейнера
COPY . .

# Папка для видео с теми же владельцем и правами, что /videos в образах узлов Grid
# (пользователь seluser = 1200, группа 0, права 775). Пустой общий том video-data Docker заполняет
# по папке того контейнера, который смонтирует его первым. Без этой строки /app/video создавал
# Docker от root, и если qa-framework стартовал раньше узлов, рекордеру узла не хватало прав
# (ffmpeg: Permission denied). С одинаковым владельцем порядок старта не важен.
RUN mkdir -p /app/video && chown 1200:0 /app/video && chmod 775 /app/video