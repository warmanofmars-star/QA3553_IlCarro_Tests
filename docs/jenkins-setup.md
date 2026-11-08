# Настройка Jenkins для IlCarro

Пошаговая инструкция: как подключить IlCarro к уже работающему Jenkins из Phonebook.
Как устроен сам пайплайн — в [`commands.md`](../commands.md), раздел «CI: Jenkins».

## 0. Что уже должно быть

Jenkins — тот же, что для Phonebook: контейнер `jenkins-master` (Jenkins 2.580.2), запущен из
репозитория Phonebook командой `docker compose -f docker-compose.jenkins.yml up -d --build`.
Отдельный Jenkins для IlCarro не нужен: второй контейнер с именем `jenkins-master` и портами
8080/50000 не запустится рядом с первым.

Проверь:

- http://localhost:8080 открывается, job `Phonebook_Docker_Tests` на месте;
- у Jenkins **2 исполнителя** (Manage Jenkins → Nodes → Built-In Node → Configure → Number of executors):
  сборки IlCarro и Phonebook могут идти одновременно;
- Docker внутри Jenkins видит Docker хоста. В Script Console ничего запускать не нужно: это проверит
  первая сборка — в логе стадии `Prepare` будет вывод `docker compose version`.
  Нужен Docker Compose **2.24.4 или новее** (`docker-compose.jenkins-build.yml` использует теги
  `!reset` и `!override`). Образ Jenkins из Phonebook ставит compose из официального репозитория
  Docker при сборке образа — если версия старая, пересобери его (команда выше).

## 1. Плагины

Те же, что использует Jenkinsfile Phonebook, кроме Telegram-части (Credentials Binding для
`TG_BOT_TOKEN`/`TG_CHAT_ID` IlCarro не нужен). Manage Jenkins → Plugins → Installed plugins — все должны
быть включены:

| Плагин | Зачем |
|---|---|
| **Pipeline** (`workflow-aggregator`) | Declarative Pipeline: `pipeline { … }`, `catchError`, `unstable`, `withEnv` |
| **Git** (`git`) | Pipeline script from SCM: Jenkins сам клонирует репозиторий |
| **GitHub** (`github`) | Триггер «GitHub hook trigger for GITScm polling» и приём вебхука на `/github-webhook/` |
| **Allure Jenkins Plugin** (`allure-jenkins-plugin`) | Шаг `allure(...)`: отчёт и график трендов на странице сборки |

Плагины ставит «Install suggested plugins» при первом запуске Jenkins, кроме Allure. Раз Phonebook
собирается с отчётом Allure, всё это уже установлено.

**Allure Commandline:** Manage Jenkins → Tools → Allure Commandline installations — должна быть
установка (для Phonebook она уже есть). Jenkinsfile не указывает её по имени и берёт имеющуюся.

## 2. Создать job

1. Dashboard → **New Item** → имя, например `IlCarro_Docker_Tests` → тип **Pipeline** → OK.
   Имя войдёт в имя compose-проекта сборки (`ilcarro-jenkins-ilcarro-docker-tests-<номер>`),
   ограничений на него нет — Jenkinsfile сам приводит его к допустимому виду.
2. Раздел **Triggers** — поставь галочку **GitHub hook trigger for GITScm polling**.
3. Раздел **Pipeline**:
   - Definition: **Pipeline script from SCM**;
   - SCM: **Git**;
   - Repository URL: `https://github.com/warmanofmars-star/QA3553_IlCarro_Tests.git`;
   - Credentials: **- none -** — репозиторий публичный;
   - Branch Specifier: `*/main`;
   - Script Path: `Jenkinsfile`;
   - Lightweight checkout — можно оставить включённым.
4. **Save**.

Параметры `BROWSER` и `TEST_MARKER` вручную не заводи: Jenkins прочитает их из Jenkinsfile
во время первой сборки. До неё кнопка называется **Build Now**, после — **Build with Parameters**.

## 3. Первая сборка

1. Нажми **Build Now**. Первая сборка идёт с параметрами по умолчанию: `chrome`, все тесты.
   Первый раз она дольше обычного: собирается образ с тестами, скачиваются образы Selenium Grid.
2. Открой сборку → **Console Output** и проверь:
   - в стадии `Prepare` — блок «Параметры сборки» (браузер, маркер, имя compose-проекта
     `ilcarro-jenkins-…`) и строка `Docker Compose version …` — версия не ниже 2.24.4;
   - в каждой части — строка `Отбор: -m "not selenium" | браузер: chrome | …` и `-m "selenium"`;
   - после каждой части — `Параметры в контейнере подтверждены: SeleniumBrowser=chrome, MarkerFilter=…`;
   - в конце — уборка: `docker compose down` удаляет контейнеры, сеть, том и образ **только**
     с префиксом `ilcarro-jenkins-…`.
3. Цвет сборки: синяя/зелёная — все тесты прошли; **жёлтая (UNSTABLE)** — есть упавшие тесты
   (известные баги в отчёте — xfailed, они сборку не красят); **красная (FAILURE)** — сбой запуска
   или не дошедший до контейнера параметр.
4. На странице сборки — ссылка **Allure Report**. В блоке **Environment** — `JenkinsBrowser`
   и `SeleniumBrowser` с одинаковым значением, `JenkinsBuild`, `MarkerFilter`
   (`not selenium; selenium` для полного прогона).
5. Проверь, что после сборки не осталось контейнеров: `docker ps -a --filter "name=ilcarro-jenkins"` —
   пусто.
6. Теперь **Build with Parameters** → `BROWSER=firefox` → в отчёте и логе должно быть `firefox`.
   Это защита от урока Phonebook, где выбор браузера однажды молча игнорировался.

## 4. Вебхук GitHub

Туннель ngrok — тот же, что для Phonebook (`ngrok http 8080`). Если он уже запущен, новый
не нужен: один адрес принимает вебхуки обоих репозиториев, а Jenkins сам находит job по адресу
репозитория.

1. Скопируй HTTPS-адрес из консоли ngrok, например `https://abcd-1234.ngrok-free.app`.
2. GitHub → репозиторий IlCarro → **Settings → Webhooks → Add webhook**:
   - Payload URL: `https://abcd-1234.ngrok-free.app/github-webhook/` (косая черта в конце обязательна);
   - Content type: `application/json`;
   - Secret: пусто;
   - Which events: **Just the push event**;
   - Active: ✓ → **Add webhook**.
3. GitHub сразу шлёт пробный ping: в списке вебхуков у него должна быть зелёная галочка
   (Recent Deliveries → ответ 200).
4. Проверка: после следующего push в `main` (например, слияния PR) в job появится новая сборка
   с причиной «Started by GitHub push». Push в другие ветки тоже доходит до Jenkins, но сборку
   не запускает: job следит только за `main`.

Бесплатный адрес ngrok меняется при каждом перезапуске туннеля — тогда обнови Payload URL
в вебхуках **обоих** репозиториев (IlCarro и Phonebook).

## 5. Если что-то пошло не так

| Симптом | Где смотреть |
|---|---|
| `yaml: unknown tag !reset` / `!override` | старый Docker Compose в образе Jenkins — пересобери образ (раздел 0) |
| `Cannot connect to the Docker daemon` | контейнер Jenkins запущен без `/var/run/docker.sock` или не от root — compose-файл Jenkins в Phonebook |
| `Параметр BROWSER=… не дошёл до контейнера` | сборка красная намеренно: тесты шли не в том браузере — пришли лог сборки |
| `не отобрано ни одного теста` | ошибка в выражении отбора; с заданным маркером пустая часть допустима |
| Нет ссылки Allure Report | плагин Allure или установка Allure Commandline (раздел 1) |
| Сборка не стартует от push | Recent Deliveries вебхука в GitHub, жив ли туннель ngrok, галочка триггера в job |
| Остались контейнеры после сборки | `docker ps -a --filter "name=ilcarro-jenkins"`; команда уборки — в `commands.md` |
