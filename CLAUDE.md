# CLAUDE.md — правила проекта для Claude Code

Учебный фреймворк автотестов (UI + API) для веб-приложения IlCarro (аренда машин): Python 3.14
локально, 3.12 в Docker; pytest, Selenium, Playwright, Allure, Docker, Selenoid, GitHub Actions.
UI: https://icarro-v1.netlify.app, API: https://ilcarro-backend.herokuapp.com.
Сейчас используется Selenoid, Jenkins нет. Подробности — в README.md.

## Безопасность (обязательно)

- **Никогда не читай и не выводи `.env`** — там реальные учётные данные. Нужен список настроек —
  смотри `.env.example`. Изменения в `.env` пользователь вносит сам.
- **Не выводи переменные окружения никаким способом:** ни `env`, ни `printenv`, ни печать `os.environ`.
- **`../QA3553_Phonebook` — только для чтения**, как образец. Его `.env` не читай, ничего там не меняй.
- **Коммит `1ce0030` не открывай:** там старая выгрузка с отозванными секретами.
- **Не делай `git push`, не создавай PR и не сливай ветки** — это делает пользователь вручную.
  Коммитить в текущую рабочую ветку можно.
- Не коммить секреты, токены, пароли, файлы из `.gitignore`.
- Файлы пиши в UTF-8 без BOM. Не дописывай в файлы через PowerShell (`>>`, `Out-File`, `Set-Content`):
  он портит кодировку.

## Команды

Локально без Selenoid (переменные окружения перекрывают `.env`, сам `.env` не трогай; полный список
настроек — `.env.example`, читает их только `config.py`):

```bash
USE_SELENOID=false ENABLE_CONSOLE_LOGS=false pytest tests/ -n 2 --browser_name=chrome -rfEsxX
pytest -m api                                # только API-тесты
pytest --collect-only -q                     # сколько тестов собирается
```

Если `USE_SELENOID=true`, а Selenoid не запущен, Selenium-тесты сразу падают с ERROR и подсказкой
(проверка хаба — один раз на воркер); API- и Playwright-тесты идут как обычно.

Docker (Selenoid), подробности — в `commands.md`:

```bash
docker compose up --build --exit-code-from qa-framework
BROWSER=firefox docker compose up --build --exit-code-from qa-framework
TEST_MARKER=smoke docker compose up --build --exit-code-from qa-framework
```

Маркеры (из `pytest.ini`): `smoke`, `regression`, `ui`, `api`, `hybrid`, `playwright`, `security`,
`contract`, `mutation`.

## Соглашения проекта

- **Переменные окружения читаются только в `config.py`** (там же `load_dotenv()`); остальной код
  импортирует `from config import settings`. Новая настройка — поле в `Settings` и строка в `.env.example`.
- **Комментарии, docstring'и, сообщения в assert'ах и логах — на русском.** Комментарий объясняет,
  ПОЧЕМУ код такой, а не пересказывает его.
- **Коммиты — Conventional Commits** (`feat`, `fix`, `refactor`, `test`, `ci`, `build`, `chore`, `docs`),
  заголовок на английском, без даты.
- **Ожидаемый результат теста берётся из источников по убыванию силы:** 1) Swagger
  (`docs/requirements/api-docs.json`), 2) HTTP RFC и OWASP, 3) код фронтенда (бандл на
  icarro-v1.netlify.app), 4) исследование фактического поведения. В тесте источник указывается
  тегом `@allure.tag` с ID из `docs/requirements/requirements.md` (`REQ-…`, `DISC-…`, `OBS-…`);
  если подходящего ID нет — не придумывай, сообщи пользователю.
  Если ни один источник не задаёт поведение, тест его не утверждает — сообщи об этом пользователю.
  Подробности — в `docs/requirements/README.md`.
- **Папка `research/` — исследовательские скрипты, не тесты;** `pytest` их не собирает.
  Результат их работы — `docs/requirements/research-log.md`.
- **Реестра известных багов пока нет:** новые `xfail` не добавляй, существующие не трогай без задачи.
- **Каждому тесту — свой временный пользователь** (`temp_user`). Постоянный аккаунт из `.env`
  тестам не нужен.
- **Бэкенд общий и внешний:** созданные тестом машины удаляй за собой.

## Как работать над задачей

- Работай в той ветке, на которой ты запущен; если это `main` и задача не велит создать ветку — остановись и спроси.
- **Упавшие тесты и XPASS не «чини» навешиванием xfail и не ослабляй проверки.** Собери данные
  (тест, браузер, текст ошибки, воспроизводится ли повторно) и сообщи — решение принимает пользователь.
- Инфраструктурные проблемы (Docker, Selenoid, зависимости) можно чинить самостоятельно, но каждое
  изменение объясни в отчёте.
- В конце задачи — короткий отчёт: что сделано, результаты прогонов (passed / xfailed / failed /
  XPASS), все изменения сверх задачи, открытые вопросы.
