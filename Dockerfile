# Python в образе тот же, что локально (3.14): «локально работает, в Docker падает» из-за версии
# не бывает. Тег точный — патч-версия и Debian (trixie, Debian 13, как у прежнего python:3.12-slim;
# Playwright ставит под него системные зависимости). Плавающий тег (3.14-slim) менял бы образ
# без изменения в репозитории. Новую патч-версию берём осознанно, не раньше чем через две недели
# после выхода.
FROM python:3.14.9-slim-trixie

# Системные пакеты отдельно не ставим: библиотеки браузера ставит playwright install-deps (сам
# вызывает apt), скачивает браузеры playwright install без wget и gnupg. ffmpeg тоже не нужен:
# видео Selenium пишут узлы Grid (ffmpeg в их образах), а Playwright пишет видео своим ffmpeg,
# который скачивает playwright install вместе с браузером
WORKDIR /app

# Сначала только зависимости: эти слои пересобираются лишь при изменении requirements.txt,
# правка теста их не трогает
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Браузеры для Playwright
RUN playwright install chromium
RUN playwright install-deps

# Код проекта — последним слоем (что не копируется, см. .dockerignore)
COPY . .

# Папка для видео с теми же владельцем и правами, что /videos в образах узлов Grid
# (пользователь seluser = 1200, группа 0, права 775). Пустой общий том video-data Docker заполняет
# по папке того контейнера, который смонтирует его первым. Без этой строки /app/video создавал
# Docker от root, и если qa-framework стартовал раньше узлов, рекордеру узла не хватало прав
# (ffmpeg: Permission denied). С одинаковым владельцем порядок старта не важен.
RUN mkdir -p /app/video && chown 1200:0 /app/video && chmod 775 /app/video
