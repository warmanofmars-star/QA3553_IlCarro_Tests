<!-- translation-of: docs/requirements/README.md sha256:c1647dada281 -->
# IlCarro requirements

> Russian original: [README.md](README.md)

IlCarro has no SRS and no STD. This folder is the source of expected results for the tests. The files here
are kept in git: this is our own work, not course material (unlike Phonebook).

## Contents

| File | What it is |
|------|---------|
| `api-docs.json` | Swagger (OpenAPI 3.0.1) of the IlCarro backend, `info.version` = `v1.0.0` |
| `requirements.md` | Reconstructed requirements: each has an ID, a source and an “Actual behaviour” column (a snapshot of the behaviour on the date it was checked) |
| `requirements.en.md` | English translation of `requirements.md`; checked against the original by `scripts/check_translations.py` |
| `changelog.md` | Version history of `requirements.md`; a working document, not translated |
| `research-log.md` | Research log: what was sent and what came back, without judgements. Questions `Q-API-NN` and `Q-UI-NN`; the “Actual behaviour” column refers to them |
| `traceability.md` | Traceability matrix: for each ID — the tests, the registry key and the coverage status. **Generated** by `scripts/coverage_matrix.py`, never edited by hand |
| `traceability.en.md` | The same matrix in English. **Generated** by `scripts/coverage_matrix.py` together with `traceability.md`, not a translation |

The log is produced by the scripts in `research/` (how to run them is described in `research/README.md`).
Requirements are derived from the sources below; judgements are made in `requirements.md`, not in the log.

## Categories of findings and test tags

Every finding in `requirements.md` gets an ID of one of three categories:

| Category | What it is | What the test does |
|-----------|---------|-----------------|
| `REQ-…` | A requirement from a source (Swagger, RFC, OWASP, frontend code). A violation is a candidate known bug | checks the requirement |
| `DISC-…` | A discrepancy between sources (for example, the frontend and Swagger) | refers to the discrepancy |
| `OBS-…` | An observation: bad behaviour for which there is no requirement; the source of the expectation is stated explicitly | records the observation |

A test is tagged with an ID from `requirements.md`:

```python
@allure.tag("REQ-BOOK-01")
def test_booking_is_saved(...): ...
```

If there is no suitable ID, nobody makes one up: it is first added to `requirements.md` (the user decides).

## Traceability matrix

`traceability.md` answers the question “which test checks which item”. It is built by
`scripts/coverage_matrix.py` from the test tags (pytest only collects the tests, it does not run them),
the registries `data/known_bugs.py` and `data/observations.py` and the registry `data/coverage_exceptions.py`.

Tag rule: a test carries the ID of an item if its assert checks that item. A test without a single tag is
a check error: every test must have an item it exists for. Whatever is checked through `require()` is
a precondition, not coverage. A test under `known_bug` or `observation` carries the tags of exactly its refs.

Each item has one of these statuses:

| Status | What it means |
|--------|------------|
| Covered by a passing test | there is a test, it passes and checks the item as it is written |
| Partly covered by a passing test, the rest is planned | there is a test and it passes, but it checks part of the item; what is not covered and in which plan step it will appear — a `partial` entry in `data/coverage_exceptions.py` |
| Covered, the test hits a known bug (strict xfail) | there is a test and it runs into a defect from `data/known_bugs.py` (strict xfail) |
| Covered as an observation (strict xfail) | the test records behaviour from `data/observations.py` (strict xfail) |
| No test — exception with a recorded reason | there is no test: the check would harm the shared backend, is blocked by another defect or the feature is unreachable — the category and the reason are recorded in `data/coverage_exceptions.py` |
| No test yet — planned | there is no test yet; `data/coverage_exceptions.py` names the plan step in which it will appear |

The statuses “partly covered” and “planned” are not allowed after step 6.3b: a `partial` or `planned` entry
in `data/coverage_exceptions.py` is a check error with the item ID (the matrix is closed, it has no debts).

Every exception records a revisit condition, `revisit_when` (in the matrix — the “Revisit when”
column); those based on a defect also record the defect ID: `blocked_by` for the `blocked` category, `basis` for `unreachable`
(for “the check would harm the shared backend” the basis is the backend itself, there is no ID). The check requires every such ID
to be among the refs of the entries in `data/known_bugs.py`. A defect is fixed — its strict xfail gives XPASS — the entry is removed
from the known bug registry — the check names the exceptions that rested on it, and they are revisited.

An item with no test and no entry in the exception registry is a check error of `python scripts/coverage_matrix.py --check`
(the Lint job in CI and a pre-commit hook). It also fails if the matrix is out of date: after a change to the tags, the registries
or `requirements.md` the matrix is rebuilt with `python scripts/coverage_matrix.py`.

A status is about the test suite, not about the application: whether a requirement is met is shown by the “Actual behaviour” column
(as of the research date) and by the Allure report (as of the run date).

## Where the Swagger file comes from

- URL: https://ilcarro-backend.herokuapp.com/v3/api-docs
- Download date: 2026-11-05
- The file is formatted with `python -m json.tool --indent 2`. The content was not changed, only the indentation:
  this way future changes to the Swagger show up in the diff.

Updating: download it again, format it the same way, look at `git diff`, update the date in this file.

## Hierarchy of sources of expected results

From strongest to weakest. In a conflict the higher source wins.

1. **Swagger** (`api-docs.json`) — the API contract: paths, methods, schemas, response codes.
2. **HTTP RFC and OWASP** — general rules of the protocol and of security (status codes, idempotency,
   authorization checks, no leaks in errors).
3. **Frontend code** — the bundle on https://icarro-v1.netlify.app: form validation rules, message
   texts, UI behaviour.
4. **Research of the actual behaviour** — the weakest source. The application's behaviour by itself does not
   prove that it is correct: it can be used as a hypothesis, but not as a reference.

If no source defines a behaviour, the test does not assert it, and the question is raised with the user.
