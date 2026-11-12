# IlCarro — Test Automation Framework

[![IlCarro Tests](https://github.com/warmanofmars-star/QA3553_IlCarro_Tests/actions/workflows/tests.yml/badge.svg)](https://github.com/warmanofmars-star/QA3553_IlCarro_Tests/actions/workflows/tests.yml)
**Live Allure report:** [warmanofmars-star.github.io/QA3553_IlCarro_Tests](https://warmanofmars-star.github.io/QA3553_IlCarro_Tests/)

UI and API test automation for **IlCarro**, a training car-rental web application:
**51 tests** (19 API, 32 UI) in Python + pytest, Selenium and Playwright. They run locally,
in Docker with Selenium Grid 4 (Chrome, Firefox, Edge), in GitHub Actions and in a self-hosted Jenkins.

- UI: <https://icarro-v1.netlify.app>
- API: <https://ilcarro-backend.herokuapp.com> (Swagger: `/v3/api-docs`)

This is a learning project from a QA automation course. It was later reworked step by step:
first the requirements were reconstructed, then the tests were made to check them honestly.

Project documentation other than this README is written in Russian; such links are marked *(in Russian)*.

---

## What is tested

| Area | Examples | Tests |
|---|---|---:|
| **API** | registration and login, adding and deleting cars, booking, dictionaries (cities) | 19 (`-m api`) |
| **API security** | missing / invalid token, BOLA (deleting another user's car), mass assignment of `owner` and `bookedPeriods`, unsupported method and content type | 15 (`-m security`, some UI form checks included) |
| **UI (Selenium)** | registration, login, adding a car, search, the date picker | 26 (`-m selenium`) |
| **UI (Playwright)** | login, adding a car, search with a mocked backend response (`page.route`) | 6 (`-m playwright`) |
| **Hybrid** | data prepared via API (a user, a car), the scenario runs in the UI | 3 (`-m hybrid`) |

Counts come from `pytest --collect-only -q -m <marker>`; areas overlap, so the column does not add up to 51.
The `selenium` and `playwright` markers are set automatically by a hook in [`conftest.py`](conftest.py)
from the fixtures a test uses (`driver` / `authenticated_driver` and `page`), not by hand.

## What makes this project interesting

- **Requirements reconstructed without an SRS.** IlCarro has no specification. Expected results are
  taken from sources ranked by strength: the Swagger contract, HTTP RFC 9110 and OWASP, the frontend
  code, and — weakest — observed behaviour. The result is
  [`docs/requirements/requirements.md`](docs/requirements/requirements.md) *(in Russian)*: every item has an ID
  (`REQ-…` requirement, `DISC-…` discrepancy between sources, `OBS-…` observation), a source and a dated
  "actual behaviour" column. The facts behind it are in
  [`research-log.md`](docs/requirements/research-log.md) *(in Russian)*, produced by the scripts in
  [`research/`](research/README.md) *(in Russian)*. Tests reference these IDs with `@allure.tag`.
- **Known bugs and observations live in registries.** Expected failures are declared only through
  [`data/known_bugs.py`](data/known_bugs.py) (`@known_bug("KEY")`, references to `REQ-…` / `DISC-…`) and
  [`data/observations.py`](data/observations.py) (`@observation("KEY")`, reference to `OBS-…`).
  References are checked against `requirements.md` when the module is imported: a typo or an ID that
  does not exist breaks test collection. Plain `pytest.mark.xfail` and `pytest.skip` are not used in tests.
- **A traceability matrix generated from the tests.** Nobody writes it by hand:
  [`scripts/coverage_matrix.py`](scripts/coverage_matrix.py) collects the `@allure.tag` IDs and the registries and
  produces [`docs/requirements/traceability.md`](docs/requirements/traceability.md) *(in Russian)*. Every ID
  either has a test or a recorded reason why it has none; CI fails if the matrix is out of date
  (see [Requirements traceability](#requirements-traceability)).
- **Tests check the state of the data, not only the response.** For example, booking answers
  `200 "Car booked successfully!"`, and the test then reads the car back and finds that nothing was saved.
  Helpers: [`utils/car_state.py`](utils/car_state.py).
- **Preconditions are not assertions.** Setup steps use `require()` from
  [`utils/preconditions.py`](utils/preconditions.py), so a broken environment fails as an error instead of
  hiding behind a known bug.
- **Clean test data on a shared backend.** Every test registers its own temporary user; cars created
  by a test are deleted after it ([`utils/car_cleanup.py`](utils/car_cleanup.py), journal in
  `logs/car_factory.jsonl`).
- **CI with a test split and a browser matrix**, plus a Jenkins pipeline, and code-quality checks
  (ruff, gitleaks, pre-commit) — see below.

## Main defects found

The application is not maintained, so defects stay. A selection — full lists are in the registries and in
`requirements.md`:

| What happens | IDs | Covered by |
|---|---|---|
| Booking answers 200 "Car booked successfully!" but saves nothing: the car's `bookedPeriods` stays empty. Booking a non-existent car also "succeeds". | REQ-BOOK-01, REQ-BOOK-02, DISC-06 | test (`BOOKING_NOT_PERSISTED`) for REQ-BOOK-01; research log Q-API-01 |
| The frontend offers 54 cities, the API knows 37, only 22 match. Adding a car in a non-matching city fails with "Failed to submit car"; search there is silently empty. | DISC-02 | test (`CITIES_MISMATCH`); research log Q-UI-03, Q-UI-12 |
| The registration form accepts a password that the API rejects (different password rules), and the error dialog shows `[object Object]`. | DISC-01, REQ-UI-REG-03 | test (`PASSWORD_RULES_MISMATCH`) |
| The car page (`/cars/{serial}`) never loads: the frontend calls endpoints that exist neither in Swagger nor on the backend. | REQ-UI-CARPAGE-01, DISC-05 | tests (`CAR_PAGE_NOT_LOADED`, `FRONTEND_CALLS_UNDOCUMENTED_ENDPOINTS`) |
| Status codes contradict the contract and RFC 9110: no token → 403 instead of 401; unknown car on delete → 400 instead of 404; wrong type in a field and `text/plain` body → 500. | REQ-SEC-01, REQ-CAR-10, REQ-CAR-03, REQ-SEC-04 | tests (`NO_AUTH_403`, `NOT_FOUND_400`, `WRONG_TYPE_500`, `WRONG_CONTENT_TYPE_500`) |

## Current results

```bash
pytest --collect-only -q                                                          # 51 tests collected
USE_GRID=false ENABLE_CONSOLE_LOGS=false pytest tests/ -n 2 --browser_name=chrome # 40 passed, 11 xfailed
```

**xfail in this project means "a documented defect is still there"**, not "a flaky or unfinished test".
Of the 11: 10 are known bugs (8 registry entries, some cover several tests or parameters) and 1 is an
observation (`NONSENSE_CAR_VALUES`, OBS-03: the API saves a car with a negative price).
All xfails are strict and expect only `AssertionError`:

- if a "known bug" test suddenly passes, the run fails with `XPASS` — the behaviour changed and the
  registry entry has to be reviewed;
- a timeout, a network error or a failed precondition stays a normal failure and is not counted as
  the known bug.

Results depend on an external backend (see [Known limitations](#known-limitations)) and are a snapshot
at the time of writing; the published Allure report shows the latest run on `main`.

## Requirements traceability

Each of the 72 items in `requirements.md` (53 `REQ`, 8 `DISC`, 11 `OBS`) is either referenced by a test
or listed in [`data/coverage_exceptions.py`](data/coverage_exceptions.py) with a category and a reason.
The table is generated — do not edit it by hand:

<!-- coverage:start -->
| Status | REQ | DISC | OBS | Total |
|---|---:|---:|---:|---:|
| ✅ Covered by a passing test | 30 | 0 | 0 | 30 |
| 🟡 Partly covered by a passing test, the rest is planned | 4 | 0 | 0 | 4 |
| 🐞 Covered, the test hits a known bug (strict xfail) | 13 | 6 | 0 | 19 |
| 👁 Covered as an observation (strict xfail) | 0 | 0 | 2 | 2 |
| ⚪ No test — exception with a recorded reason | 3 | 1 | 0 | 4 |
| 🕓 No test yet — planned | 3 | 1 | 9 | 13 |
| **Total** | 53 | 8 | 11 | 72 |

Exceptions: the check would harm the shared backend — 1; blocked by another defect — 1; the feature is unreachable — 2. Planned: 0 in step 6.2 (API), 0 in step 6.3a (UI: request interception and session), 13 in step 6.3b (UI: the rest and observations). The rest of the partly covered items: 0 in step 6.2, 0 in step 6.3a, 5 in step 6.3b.
All 111 tests reference at least one ID (a test without one fails the check).
<!-- coverage:end -->

The full matrix — every ID with its tests, registry key and status, plus the list of exceptions and
planned tests with reasons — is [`docs/requirements/traceability.md`](docs/requirements/traceability.md)
*(in Russian)*. It shows what the suite checks, not the result of a run: tests are only collected.

```bash
python scripts/coverage_matrix.py           # regenerate the matrix and the table above
python scripts/coverage_matrix.py --check   # what CI and the pre-commit hook run
```

`--check` fails if the matrix or the table above is out of date, if a test has no requirement ID or
references an ID that does not exist, if an ID has neither a test nor an exception (or has both), and if a test marked as a known
bug or an observation does not carry exactly the IDs of its registry entry.

## Tech stack

| | |
|---|---|
| Language | Python 3.14 (locally and in the Docker image `python:3.14.9-slim-trixie`); code compatible with 3.12+ (ruff target `py312`) |
| Test runner | pytest 9.1, pytest-xdist (parallel workers), pytest-rerunfailures |
| UI | Selenium 4.49 (Chrome, Firefox, Edge), Playwright 1.63 (sync API, Chromium) |
| API | requests, jsonschema |
| Test data | dataclasses (`Car`, `User`), Faker |
| Infrastructure | Docker, Docker Compose, Selenium Grid 4 (`selenium/hub` and nodes `4.51.0-20261010`, video recording on nodes) |
| Reporting | Allure (allure-pytest 2.16) with screenshots and videos |
| CI | GitHub Actions, GitHub Pages, Jenkins, Telegram notifications |
| Code quality | ruff, pre-commit, gitleaks |

Exact versions: [`requirements.txt`](requirements.txt), [`requirements-dev.txt`](requirements-dev.txt),
[`docker-compose.yml`](docker-compose.yml), [`Dockerfile`](Dockerfile).

## Project structure

```text
api/            API client (requests.Session)
data/           test data generator; registries: known bugs, observations, coverage exceptions
docs/           reconstructed requirements, traceability matrix, Swagger, research log, Jenkins setup (in Russian)
drivers/        WebDriver factory: local browsers or Selenium Grid, Grid readiness check, session video
models/         Car and User dataclasses with API payload serialization
pages/          Page Objects for Selenium and Playwright
research/       research scripts (not tests): produce docs/requirements/research-log.md
schemas/        JSON Schemas for API responses
scripts/        CI helpers: test split check, traceability matrix, Allure results merge, report secrets scan, Telegram
tests/          all tests: API, security, mutations, Selenium, Playwright, hybrid
utils/          preconditions, data state checks, car cleanup, registered users journal, validators,
                request interception for Playwright, Swagger operations, WebDriver listener
conftest.py     fixtures (temporary users, drivers, cleanup), markers hook, Allure environment
```

## Running the tests

### Locally

Requires Python 3.14 (3.12+ should work).

```bash
git clone https://github.com/warmanofmars-star/QA3553_IlCarro_Tests.git
cd QA3553_IlCarro_Tests
python -m venv .venv
.venv\Scripts\activate              # Windows; on Linux / macOS: source .venv/bin/activate
pip install -r requirements-dev.txt # requirements.txt + ruff and pre-commit
pip check                           # "No broken requirements found."
playwright install chromium
cp .env.example .env                # Windows: copy .env.example .env
```

All settings are listed in [`.env.example`](.env.example) and read only by [`config.py`](config.py).
No permanent account is needed: every test registers its own user. To run browsers locally,
set `USE_GRID=false` (in `.env` or in the environment):

```bash
USE_GRID=false pytest tests/ -n 2 --browser_name=chrome   # the whole suite, 2 parallel workers
pytest -m api                                             # API tests only, no browser
pytest -m "smoke and ui" --browser_name=firefox
pytest --alluredir=allure-results && allure serve allure-results
```

Markers (from [`pytest.ini`](pytest.ini)): `smoke`, `regression`, `ui`, `api`, `hybrid`, `security`,
`contract`, `mutation`, plus the automatic `selenium` and `playwright`. Logs go to `logs/`.

### In Docker (Selenium Grid 4)

The browser is selected by two variables with the same value — `chrome`, `firefox` or `edge`:
`COMPOSE_PROFILES` starts the browser nodes, `BROWSER` tells the tests which browser to use.

```bash
COMPOSE_PROFILES=chrome docker compose up --build --exit-code-from qa-framework
COMPOSE_PROFILES=firefox BROWSER=firefox docker compose up --build --exit-code-from qa-framework
COMPOSE_PROFILES=chrome TEST_MARKER=smoke docker compose up --build --exit-code-from qa-framework
```

The stack is a hub and three nodes of the selected browser; tests run in 3 pytest workers. Each node records
its sessions, and the video is attached to the Allure report. Grid UI: <http://localhost:4444/ui/>
(host port is `GRID_HOST_PORT`, default 4444). If the Grid is not reachable, Selenium tests fail with an
error that says so, while API and Playwright tests run as usual.

More commands: [`commands.md`](commands.md) *(in Russian)*.

### GitHub Actions

[`.github/workflows/tests.yml`](.github/workflows/tests.yml) runs on pull requests to `main`, on push to `main`
and manually (`workflow_dispatch` with an optional `test_marker`). Jobs:

| Job | What it does |
|---|---|
| `lint` | `ruff check`, `ruff format --check`, gitleaks over the whole git history, and [`scripts/coverage_matrix.py --check`](scripts/coverage_matrix.py): the traceability matrix is consistent and up to date; runs in parallel with the tests |
| `split-check` | [`scripts/check_ci_split.py`](scripts/check_ci_split.py): the `selenium` and `not selenium` selections are non-empty, do not overlap and together cover all tests (26 + 25 = 51) |
| `api-and-playwright` | `-m "not selenium"` once, in Docker without the Grid |
| `selenium` | `-m "selenium"`, matrix chrome / firefox / edge, each in Docker Compose with the Grid |
| `report` | merges the results ([`scripts/merge_allure_results.py`](scripts/merge_allure_results.py)), checks them for secrets ([`scripts/scan_report_secrets.py`](scripts/scan_report_secrets.py); a finding fails the job and nothing is generated or published), takes the trend history from the published report, generates the Allure report and keeps it as an artifact |
| `deploy` | publishes the report to GitHub Pages — only from `main` |
| `notify-report` / `notify-failure` | Telegram message after a successful deploy, or when any job failed — only for `main` |

So every test runs in exactly one job: 25 once plus 26 × 3 browsers = 103 test runs per pipeline
instead of 51 × 3 = 153. An empty selection fails the job (except for a manual run with a marker);
a failed test fails the job, `continue-on-error` is not used. A new run of a pull request cancels the previous one;
runs on `main` wait in a queue.

### Jenkins

[`Jenkinsfile`](Jenkinsfile): parameters `BROWSER` (chrome / firefox / edge) and `TEST_MARKER`; stages
`Prepare` → `API and Playwright` → `Selenium (Grid)`, the same split as in GitHub Actions. Each build gets
its own Docker Compose project and is cleaned up afterwards. Failed tests mark the build `UNSTABLE`,
infrastructure errors `FAILURE`; the report is published by the Allure plugin after the same secrets check
(a finding marks the build `FAILURE` and the report is not published). The build also fails if the
browser or marker that actually reached pytest differs from the build parameters. Triggered by a GitHub
webhook (through ngrok) on push to `main` or by **Build with Parameters**.
Setup: [`docs/jenkins-setup.md`](docs/jenkins-setup.md) *(in Russian)*.

## Code quality

- **ruff** — linter and formatter, configured in [`pyproject.toml`](pyproject.toml) (target `py312`, line length 120).
- **pre-commit** ([`.pre-commit-config.yaml`](.pre-commit-config.yaml)) runs before every commit: file
  hygiene (trailing whitespace, end of file, YAML and TOML syntax, merge-conflict markers, large files),
  `ruff-check`, `ruff-format` and **gitleaks**. Besides the built-in gitleaks rules, a custom rule in
  [`.gitleaks.toml`](.gitleaks.toml) catches `.env`-style passwords. Acknowledged historical findings
  (revoked secrets) are listed in [`.gitleaksignore`](.gitleaksignore).
  A local hook, [`scripts/check_links.py`](scripts/check_links.py), checks that relative links in changed
  Markdown files point to existing files and headings. Another one runs `scripts/coverage_matrix.py --check`
  when tests, registries, requirements or the README change (it needs the project's Python environment).
- The same ruff and gitleaks versions run in the CI `lint` job; gitleaks there scans the whole history.
- `pip check` runs during the Docker image build, so incompatible package versions fail the build.
- **No secrets in the public report.** Steps that handle a password do not take it as an `@allure.step`
  argument, `User.password` is excluded from `repr` (tracebacks), and parametrize arguments named like
  `password`, `token` or `secret` are masked by an autouse fixture in [`conftest.py`](conftest.py).
  [`scripts/scan_report_secrets.py`](scripts/scan_report_secrets.py) checks the results for JWTs and
  unmasked secret parameters before the report is published in GitHub Actions and Jenkins.

```bash
pre-commit install            # once after cloning
pre-commit run --all-files    # check the whole project
```

## Known limitations

- **Shared external backend.** The frontend and the backend (Heroku) are not part of this repository and
  are used by other people. If they are down or slow, tests fail; absolute numbers (e.g. cars in a city)
  cannot be asserted. Search for large cities returns tens of megabytes (Tel Aviv — about 18 MB).
- **Users cannot be deleted.** The API has no such endpoint, so every run leaves temporary users behind.
  Cars are deleted.
- **Jenkins is a local learning setup.** It runs in a Docker container (shared with the author's Phonebook
  project), runs as root and uses the host Docker socket — effectively root on the host. The webhook reaches it through ngrok; the free ngrok address changes on every restart
  and the webhook URL has to be updated.
- **Videos are attached only in Docker.** Grid nodes write them to a Docker volume that a local run cannot read.
- **Frontend file names contain build hashes**, so references to frontend code in `requirements.md` are valid
  for the build of 2026-11-05.

## Plans

Not done yet:

- **Step 6.2 — API tests**, **step 6.3a — UI tests with request interception and the session** and
  **step 6.3b — the rest of the UI tests and observations** for the items marked as planned in the
  [traceability matrix](docs/requirements/traceability.md) (step 6.1, the matrix itself, is done).
- **Step 7 — UI resilience tests:** how the UI behaves when the backend fails (network interception in Playwright).

## How the project is developed

The project is developed together with an AI coding agent (Claude Code). Its rules are in
[`CLAUDE.md`](CLAUDE.md) *(in Russian)*: security (never read `.env`, never push), conventions (registries,
`require()`, waits by state, logging) and the source hierarchy for expected results.
The process is "plan in chat → the agent implements it in a branch → review through a pull request": the agent
commits only to a working branch, the author pushes and merges. The history so far — 12 merged pull requests.

## License

[Apache License 2.0](LICENSE)
