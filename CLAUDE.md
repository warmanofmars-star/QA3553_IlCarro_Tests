# CLAUDE.md — правила проекта для Claude Code

Учебный фреймворк автотестов (UI + API) для веб-приложения IlCarro (аренда машин): Python —
совместимость 3.12+ (ruff `py312`), запуск на 3.14 локально и в Docker (`python:3.14.9-slim-trixie`,
тег точный — меняется вручную); pytest, Selenium, Playwright, Allure, Docker, Selenium Grid 4, GitHub Actions,
Jenkins. UI: https://icarro-v1.netlify.app, API: https://ilcarro-backend.herokuapp.com.
Браузеры в Docker — через Selenium Grid 4. Подробности — в README.md.

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
машин — `logs/car_factory.jsonl`, журнал зарегистрированных пользователей — `logs/registered_users.jsonl`
(`utils/user_journal.py`; итог — одной строкой в конце прогона). Регистрации через API-клиент и «сырые»
запросы пишутся в журнал сами; **тест, который регистрирует пользователя через UI, сам пишет в журнал**
(`record_registration(email, UI_FORM)` сразу после проверки успеха) — page object побочных эффектов
не имеет. `ENABLE_CONSOLE_LOGS=true` включает живые логи в консоли (без `-n`).

Docker (Selenium Grid), подробности — в `commands.md`. Браузер задают две переменные с одинаковым
значением: `COMPOSE_PROFILES` (какие узлы запустить) и `BROWSER` (в чём гонять тесты). Порт Grid
на хосте — `GRID_HOST_PORT` (по умолчанию 4444), Grid UI — http://localhost:4444/ui/.

```bash
COMPOSE_PROFILES=chrome docker compose up --build --exit-code-from qa-framework
COMPOSE_PROFILES=firefox BROWSER=firefox docker compose up --build --exit-code-from qa-framework
COMPOSE_PROFILES=chrome TEST_MARKER=smoke docker compose up --build --exit-code-from qa-framework
```

Маркеры (из `pytest.ini`): `smoke`, `regression`, `ui`, `api`, `hybrid`, `security`, `contract`,
`mutation`. Плюс `selenium` и `playwright` — их ставит хук `pytest_collection_modifyitems` в `conftest.py`
по фикстурам: `selenium` — тестам с `driver`/`authenticated_driver`, `playwright` — тестам с `page`;
вручную их не расставляй.

## Качество кода (ruff, pre-commit, gitleaks)

Инструменты — в `requirements-dev.txt` (в Docker-образ не попадают), настройки ruff — `pyproject.toml`
(`py312`, строка 120; `research/`, `scripts/`, `merge_code.py` проверяются тоже).

```bash
pip install -r requirements-dev.txt && pre-commit install   # один раз после клонирования
pre-commit run --all-files                                  # все хуки на всех файлах
ruff check .            # линтер;  ruff check --fix .  — исправить исправимое
ruff format .           # форматирование;  ruff format --check .  — только проверить
```

- **Перед каждым коммитом — `pre-commit run --all-files`, все хуки зелёные.** Хук, исправивший
  файл, тоже «Failed»: проверь изменения, `git add`, повтори.
- **`git commit --no-verify` запрещён**, как и любой другой обход хуков. Хук мешает законному коду —
  чини настройку (`pyproject.toml`, `.gitleaks.toml`, `.pre-commit-config.yaml`) и сообщи пользователю.
- Замечание ruff, которое требует изменить логику теста или ослабить проверку, не исправляй — сообщи.
  `# noqa` — только с указанием правила и причиной рядом.
- gitleaks: свои правила — `.gitleaks.toml` (`env-style-password` — пароли в формате `.env`),
  признанные исторические находки — `.gitleaksignore` (отпечаток + комментарий: что это, когда
  отозвано). Новую находку в ignore не добавляй сам: секрет сначала отзывают — решает пользователь.
- Окончания строк — `.gitattributes` (LF; `.bat`/`.cmd`/`.ps1` — CRLF).
- Секреты в отчёте Allure — `scripts/scan_report_secrets.py`: JWT и незамаскированные параметры
  с `password`/`token`/`secret` в имени; печатает файл, поле и количество, без значений; код 1 —
  найдено, 2 — нечего проверять. Запускается в CI и Jenkins до публикации отчёта; локально —
  `python scripts/scan_report_secrets.py allure-results`. Находку не обходи: убери секрет из кода.
- Хук `coverage-matrix` (local, `language: system`) — `python scripts/coverage_matrix.py --check` при
  изменениях в `tests/`, `data/`, `docs/requirements/`, `README.md`, `conftest.py`. Ему нужны зависимости
  проекта: коммить из окружения, где они установлены.
- Версии ruff и gitleaks согласованы в трёх местах: `requirements-dev.txt`, `.pre-commit-config.yaml`
  и job `lint` в `.github/workflows/tests.yml`. Меняешь одно — меняй все.

## CI (GitHub Actions, `.github/workflows/tests.yml`)

Запуск: PR в `main`, push в `main`, ручной (`workflow_dispatch`, поле `test_marker`). Новый запуск
PR отменяет предыдущий запуск того же PR; запуски на `main` не отменяются, а ждут в очереди. Jobs:

- `lint` — ruff check, ruff format --check, gitleaks по всей истории, `scripts/coverage_matrix.py --check`
  (матрица трассируемости; ради сбора тестов ставятся зависимости проекта, Python 3.14); от тестов
  не зависит, идёт параллельно с ними;
- `split-check` — `scripts/check_ci_split.py`: отборы `selenium` и `not selenium` не пусты,
  не пересекаются, в сумме дают весь набор;
- `api-and-playwright` — `-m "not selenium"`, один раз, Docker без Grid;
- `selenium` — `-m "selenium"`, матрица chrome / firefox / edge через Grid;
- `report` (`!cancelled()`) — склейка `scripts/merge_allure_results.py`, проверка на секреты
  `scripts/scan_report_secrets.py` (находка — job красный, отчёт не генерируется и не публикуется),
  история с опубликованного отчёта, генерация, артефакт `allure-report`;
- `deploy` — только `main` (push или ручной запуск): `actions/deploy-pages`;
- `notify-report` — Telegram после успешной выкладки; `notify-failure` — Telegram, если что-то упало
  (включая `lint`). Оба — только для `main`; отправка — `scripts/send_telegram.sh` (curl к Bot API).

Отбор передаётся в контейнер через `PYTEST_ADDOPTS`; маркер ручного запуска добавляется как
`(маркер) and selenium` — скобки обязательны. Пустой отбор (код pytest 5) валит job, кроме ручного
запуска с маркером. Упавший тест — красный job, `continue-on-error` не используется.
Environment для Allure пишет `pytest_sessionfinish` в `conftest.py`, а не workflow.
Отдельный job вручную: `test_marker=selenium` (только матрица) или `test_marker=not selenium`
(только API и Playwright); подробности и локальные аналоги — в `commands.md`.
После изменения маркеров или фикстур браузера проверь разбиение: `python scripts/check_ci_split.py`.

## CI (Jenkins, `Jenkinsfile`)

Jenkins общий с Phonebook (контейнер `jenkins-master`, localhost:8080, Docker хоста через
`docker.sock`); настраивает его пользователь по `docs/jenkins-setup.md`, сам к Jenkins не обращайся.
Запуск: вебхук GitHub через ngrok на push в `main` или **Build with Parameters**. Параметры:
`BROWSER` (chrome / firefox / edge) и `TEST_MARKER` (пусто — все тесты). Стадии:

- `Prepare` — проверка браузера, очистка `allure-results` workspace, параметры в лог и в описание сборки;
- `API and Playwright` — `-m "not selenium"`, `up --no-deps qa-framework`;
- `Selenium (Grid)` — `-m "selenium"`, хаб и узлы выбранного браузера; части идут друг за другом,
  сбой одной не отменяет другую (`catchError`). Маркер — `(маркер) and …`, как в GitHub Actions;
  пустой отбор без маркера — ошибка.

Изоляция: compose-проект `ilcarro-jenkins-<job>-<номер>` на сборку; `COMPOSE_FILE` добавляет
`docker-compose.jenkins-build.yml` — порт хаба на хост не публикуется, `allure-results` не монтируется
(результаты — `docker cp` из остановленного контейнера). Образ с тестами — общий для сборок job:
`QA_IMAGE` = `ilcarro-jenkins-<job>-qa-framework` с меткой `ilcarro.jenkins.image` (кэш слоёв между
сборками). Уборка в `post { always }` — `docker compose down -v --remove-orphans` только этого проекта
и удаление безымянных старых версий образа по метке `ilcarro.jenkins.image=$QA_IMAGE`; `prune`
и глобальные удаления в Jenkinsfile запрещены. Статус: упавшие тесты — `UNSTABLE`, сбой запуска — `FAILURE`.
Отчёт — плагин Allure; перед публикацией — `scripts/scan_report_secrets.py` в образе `QA_IMAGE`
(Python в образ Jenkins не ставится — `Dockerfile.jenkins` в Phonebook; результаты — через `docker cp`), находка — `FAILURE` без отчёта.
Environment дополняет Jenkinsfile (`JenkinsBrowser`, `JenkinsMarker`,
`JenkinsBuild`). Защита от «молча проигнорированного» параметра: Jenkinsfile сверяет `SeleniumBrowser`
и `MarkerFilter` из `environment.properties` контейнера с параметрами; расхождение — `FAILURE`.
Ловушка: Jenkins экспортирует параметры в окружение, и `TEST_MARKER` через `docker-compose.yml` перебил бы
`-m` части — поэтому при запуске compose он обнуляется. Telegram из Jenkins не шлётся.

## Соглашения проекта

- **Переменные окружения читаются только в `config.py`** (там же `load_dotenv()`); остальной код
  импортирует `from config import settings`. Новая настройка — поле в `Settings` и строка в `.env.example`.
- **Комментарии, docstring'и, сообщения в assert'ах и логах — на русском.** Комментарий объясняет,
  ПОЧЕМУ код такой, а не пересказывает его.
- **Логи — только стандартный `logging`, без `print`:** в модуле `logger = logging.getLogger(__name__)`.
  Обработчики, форматы и уровни настраивают `pytest.ini` и `pytest_configure` в `conftest.py`;
  свои обработчики и логгеры-фикстуры не заводи. `print` допустим только в консольных скриптах
  (`merge_code.py`, `research/`, `scripts/`).
- **Ожидания — по состоянию, без фиксированных пауз:** `WebDriverWait`/`expected_conditions` в Selenium,
  `expect()` и автоожидания локаторов в Playwright (элемент появился или исчез, поле заполнено, URL
  сменился, запрос ушёл). `time.sleep` и `page.wait_for_timeout` запрещены; в синхронном Playwright
  `time.sleep` недопустим вообще. Исключение — пауза, у которой нет наблюдаемого состояния: только
  с комментарием «почему» рядом (пример — 1,5 с перед закрытием браузера Grid в `conftest.py`).
- **Пароли и токены не попадают в отчёт:** не передавай их аргументами функциям с `@allure.step`
  (декоратор пишет все аргументы в параметры шага) — шаг с секретом делай через
  `with allure.step(...)` внутри функции, как `IlCarroAPI.login`/`register`. Поле с секретом
  в dataclass — `field(repr=False)` (repr аргументов теста попадает в трассу). Параметры
  параметризации с `password`/`token`/`secret` в имени маскирует автофикстура `_mask_secret_params`
  в `conftest.py` — имя параметра с секретом должно содержать одно из этих слов; метке сценария
  такое имя не давай (`registration_case`, `auth_case`, а не `password_strategy`), иначе она
  скроется в отчёте. Заведомо неверные пароли негативных тестов (`invalid_value` в
  `test_registration_negative_fields` и подобные) не маскируются: это отклонённые данные,
  а не учётные данные аккаунта, и в отчёте они нужны, чтобы понять сценарий.
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
- **Какого пользователя брать тесту — по тому, меняет ли он состояние пользователя НА СЕРВЕРЕ.**
  Пользователей API удалить нельзя: каждый `temp_user` навсегда остаётся на общем бэкенде, поэтому
  свежих регистрируем только там, где без этого нельзя. Постоянный аккаунт из `.env` тестам не нужен.
  - Свежий `temp_user` — тест меняет или проверяет состояние пользователя на сервере: выход
    (отзыв токена), профиль, число машин пользователя, вход как предмет проверки.
  - Общий `shared_user` (scope `session`, один на воркер xdist; фикстуры `shared_api`,
    `shared_create_car`, `shared_car_cleanup`) — меняется только состояние браузера (localStorage),
    ответы бэкенда подменены, или тесту нужен только токен и свои данные он находит по serialNumber.
    Залогиненный браузер такому тесту дают токеном в localStorage (`PwBasePage.restore_session`),
    без запроса входа.
  - Проверкам «свой — чужой» — пара на модуль `user_pair` (у каждого теста своя очистка машин).
  Машины по-прежнему удаляет фабрика или очистка после каждого теста.
- **Бэкенд общий и внешний:** созданные тестом машины удаляй за собой.
- **Перехват запросов — только Playwright и только через `utils/network_faults.py`.** Тест, который
  подменяет пишущий запрос, запрашивает фикстуру `backend_write_guard` до своих `page.route`: она
  обрывает любой не-GET запрос к API мимо подмен (опечатка в шаблоне не создаст данных на бэкенде).
  Перед проверкой содержимого или реакции на подмену — `require_intercepted`.

## Трассируемость требований

Матрица `docs/requirements/traceability.md` и сводка в `README.md` (между `<!-- coverage:start -->`
и `<!-- coverage:end -->`) **генерируются, руками их не правят.** Источник правды — теги тестов и реестры.

```bash
python scripts/coverage_matrix.py           # пересобрать матрицу и сводку в README.md
python scripts/coverage_matrix.py --check   # проверить: это запускают job Lint и хук pre-commit
```

- **Тег — это утверждение «assert этого теста проверяет пункт».** Тест (или параметр, если случаи
  проверяют разное: `pytest.param(..., marks=allure.tag(...))`) несёт `@allure.tag` с ID всех пунктов,
  которые проверяет своим assert. Решай по смыслу проверки, а не по имени теста.
- **Не тег:** то, что проверено через `require()` (предусловие); то, чем тест только пользуется
  (например, `size` в URL, чтобы показать всю выдачу); следствие, которое assert не различает
  (общий текст «Failed to submit car» не доказывает код 400).
- **Тест под `known_bug` / `observation` несёт теги ровно своих refs** — не меньше и не больше:
  под xfail остаётся одна проверка, остальное проверяет отдельный тест.
- **Каждый тест несёт хотя бы один тег** — тест без тега валит `--check`. Нет подходящего ID —
  не придумывай его и не ставь «ближайший»: найди поведение в источниках (Swagger, RFC/OWASP, код
  фронтенда) и сообщи пользователю — пункт в `requirements.md` добавляет он или с его согласия.
- **Пункт без теста записан в `data/coverage_exceptions.py`:** ID → категория и причина.
  Категории: `harms_shared_env` (проверка вредит общему бэкенду), `blocked` (мешает другой дефект,
  `blocked_by` — его ID), `unreachable` (функциональность недостижима), `planned` (тест будет,
  `pr` — шаг плана: `6.2` API, `6.3a` UI: перехват запросов и сессия, `6.3b` UI: остальное
  и наблюдения). Новую запись категории исключения (не `planned`) согласуй с пользователем.
- **Тест проверяет пункт не целиком — запись `partial`** в том же реестре: в `reason` — что НЕ покрыто,
  в `pr` — шаг плана, который доберёт остальное. `partial` — единственная категория, которая стоит
  вместе с тестом; `partial` без теста — ошибка `--check` (без теста это `planned`).
- **Написал тест на запланированный пункт — убери его запись из реестра исключений** в том же
  коммите: ID одновременно с тестом и с записью любой категории, кроме `partial`, — ошибка `--check`.
  Добрал непокрытую часть `partial`-пункта — убери запись `partial`.
- **После изменения тегов, реестров или `requirements.md` — перегенерируй матрицу** и закоммить её
  вместе с изменением. `--check` падает (код 2 — данные не согласованы, код 1 — файлы устарели):
  тест без тегов; тег с несуществующим ID; ID без теста и без записи в исключениях; ID и с тестом, и с записью
  (кроме `partial`); `partial` без теста;
  тест под `known_bug` / `observation` без тега своих refs или с лишним тегом; xfail не из реестров;
  устаревшие `traceability.md` или сводка в `README.md`. Проверку не обходи: исправь теги или реестр.
- Статусы в матрице — о том, что проверяет набор, а не о результате прогона. «Покрыт» — пункт
  проверен так, как записан; проверена часть — «частично» (`partial`). Колонка «Факт»
  в `requirements.md` — снимок исследования.

## Как работать над задачей

- Работай в той ветке, на которой ты запущен; если это `main` и задача не велит создать ветку — остановись и спроси.
- **Упавшие тесты и XPASS не «чини» навешиванием xfail и не ослабляй проверки.** Собери данные
  (тест, браузер, текст ошибки, воспроизводится ли повторно) и сообщи — решение принимает пользователь.
- Инфраструктурные проблемы (Docker, Selenium Grid, зависимости) можно чинить самостоятельно, но каждое
  изменение объясни в отчёте.
- В конце задачи — короткий отчёт: что сделано, результаты прогонов (passed / xfailed / failed /
  XPASS), все изменения сверх задачи, открытые вопросы.
