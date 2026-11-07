# CLAUDE.md — правила проекта для Claude Code

Учебный фреймворк автотестов (UI + API) для веб-приложения IlCarro (аренда машин): Python 3.14
локально, 3.12 в Docker; pytest, Selenium, Playwright, Allure, Docker, Selenium Grid 4, GitHub Actions.
UI: https://icarro-v1.netlify.app, API: https://ilcarro-backend.herokuapp.com.
Браузеры в Docker — через Selenium Grid 4, Jenkins нет. Подробности — в README.md.

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

Локально без Grid (переменные окружения перекрывают `.env`, сам `.env` не трогай; полный список
настроек — `.env.example`, читает их только `config.py`):

```bash
USE_GRID=false ENABLE_CONSOLE_LOGS=false pytest tests/ -n 2 --browser_name=chrome -rfEsxX
pytest -m api                                # только API-тесты
pytest --collect-only -q                     # сколько тестов собирается
```

Если `USE_GRID=true`, а Grid не запущен, Selenium-тесты падают с ERROR и подсказкой
(хаб ждём до 10 с, узел нужного браузера — до 60 с, один раз на воркер; остальные тесты воркера
падают сразу); API- и Playwright-тесты идут как обычно. Создание браузера и проверка Grid —
`drivers/factory.py`.

Логи: обычный запуск → `logs/pytest.log`, воркеры xdist → `logs/pytest_gw0.log`, `pytest_gw1.log`…
(главный процесс xdist файла не пишет; файлы прошлого прогона удаляются при старте). Журнал фабрики
машин — `logs/car_factory.jsonl`. `ENABLE_CONSOLE_LOGS=true` включает живые логи в консоли (без `-n`).

Docker (Selenium Grid), подробности — в `commands.md`. Браузер задают две переменные с одинаковым
значением: `COMPOSE_PROFILES` (какие узлы запустить) и `BROWSER` (в чём гонять тесты). Порт Grid
на хосте — `GRID_HOST_PORT` (по умолчанию 4444), Grid UI — http://localhost:4444/ui/.

```bash
COMPOSE_PROFILES=chrome docker compose up --build --exit-code-from qa-framework
COMPOSE_PROFILES=firefox BROWSER=firefox docker compose up --build --exit-code-from qa-framework
COMPOSE_PROFILES=chrome TEST_MARKER=smoke docker compose up --build --exit-code-from qa-framework
```

Маркеры (из `pytest.ini`): `smoke`, `regression`, `ui`, `api`, `hybrid`, `playwright`, `security`,
`contract`, `mutation`.

## Соглашения проекта

- **Переменные окружения читаются только в `config.py`** (там же `load_dotenv()`); остальной код
  импортирует `from config import settings`. Новая настройка — поле в `Settings` и строка в `.env.example`.
- **Комментарии, docstring'и, сообщения в assert'ах и логах — на русском.** Комментарий объясняет,
  ПОЧЕМУ код такой, а не пересказывает его.
- **Логи — только стандартный `logging`, без `print`:** в модуле `logger = logging.getLogger(__name__)`.
  Обработчики, форматы и уровни настраивают `pytest.ini` и `pytest_configure` в `conftest.py`;
  свои обработчики и логгеры-фикстуры не заводи. `print` допустим только в консольных скриптах
  (`merge_code.py`, `make_readme.py`, `research/`, `scripts/`).
- **Ожидания — по состоянию, без фиксированных пауз:** `WebDriverWait`/`expected_conditions` в Selenium,
  `expect()` и автоожидания локаторов в Playwright (элемент появился или исчез, поле заполнено, URL
  сменился, запрос ушёл). `time.sleep` и `page.wait_for_timeout` запрещены; в синхронном Playwright
  `time.sleep` недопустим вообще. Исключение — пауза, у которой нет наблюдаемого состояния: только
  с комментарием «почему» рядом (пример — 1,5 с перед закрытием браузера Grid в `conftest.py`).
- **Пользователь теста — `TempUser`** (dataclass из `conftest.py`, поля `user` и `api`); у
  `second_user` есть ещё `cleanup`. Обращение — атрибутами: `temp_user.user.email`, `second_user.api`,
  а не `temp_user["user"]`.
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
- **Известные баги — только через реестр `data/known_bugs.py`** и маркер `@known_bug("KEY")`
  (строгий xfail, `raises=AssertionError`). У записи есть `refs` — ID `REQ-…` или `DISC-…` из
  `docs/requirements/requirements.md`; ссылки проверяются при импорте модуля. Нет подходящего ID —
  это не баг: не придумывай ID и не ставь xfail, сообщи пользователю. Тест с маркером получает
  `@allure.tag` с теми же ID (для параметра — через `marks=[known_bug(...), allure.tag(...)]`).
- **Наблюдения — через реестр `data/observations.py`** и маркер `@observation("KEY")`: плохое поведение
  без требования, `ref` — только `OBS-…`. Это не нарушение требования, а ожидание, источник которого
  записан в `requirements.md`. Тег теста — `@allure.tag("OBS-…")`.
- **Прямые `pytest.mark.xfail`, `pytest.xfail` и `pytest.skip` в тестах запрещены** — только реестры.
  Упавший тест или XPASS не «чини» маркером: собери данные и сообщи.
- **Предусловия проверяются через `require()`** (`utils/preconditions.py`), а не через `assert`:
  регистрация временного пользователя, создание машины «пререквизитом», доступность API в подготовке.
  В тесте под `known_bug` или `observation` через `assert` остаётся только проверка, ради которой стоит
  xfail; всё остальное — `require()`. Иначе посторонний сбой спрячется за известным багом.
- **Каждому тесту — свой временный пользователь** (`temp_user`). Постоянный аккаунт из `.env`
  тестам не нужен.
- **Бэкенд общий и внешний:** созданные тестом машины удаляй за собой.

## Как работать над задачей

- Работай в той ветке, на которой ты запущен; если это `main` и задача не велит создать ветку — остановись и спроси.
- **Упавшие тесты и XPASS не «чини» навешиванием xfail и не ослабляй проверки.** Собери данные
  (тест, браузер, текст ошибки, воспроизводится ли повторно) и сообщи — решение принимает пользователь.
- Инфраструктурные проблемы (Docker, Selenium Grid, зависимости) можно чинить самостоятельно, но каждое
  изменение объясни в отчёте.
- В конце задачи — короткий отчёт: что сделано, результаты прогонов (passed / xfailed / failed /
  XPASS), все изменения сверх задачи, открытые вопросы.
