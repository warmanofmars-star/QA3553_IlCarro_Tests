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