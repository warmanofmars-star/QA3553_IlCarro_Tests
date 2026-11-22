<!-- summary-of: docs/requirements/research-log.md sha256:1625fe12cf3e -->
# IlCarro research log: English summary

> Summary of the Russian original: [research-log.md](research-log.md) *(in Russian)*. Not a translation: it retells
> the main facts; tables, response bodies and details are in the original under the same Q-… IDs or section titles.

## What was researched and why

The research log records the actual behaviour of IlCarro, plus one question about the test framework itself: what was
sent and what came back, without assessments (two places are the exception, see below); assessments
are made later from higher-ranked sources. Backend questions are Q-API-01 … Q-API-21, web UI questions
Q-UI-01 … Q-UI-43. The backend is shared: data that other users change, such as car counts, varies
(Q-API-02, Q-API-12).

## How

- Research scripts, not tests: `research/explore_api.py` (Q-API-01 … Q-API-18), `research/explore_ui.py`
  (Q-UI-01 … Q-UI-14), `research/explore_ui_interception.py` (Q-UI-15 … Q-UI-19), `research/explore_ui_rest.py`
  (Q-UI-20 … Q-UI-26), `research/explore_ui_faults.py` (Q-UI-27 … Q-UI-40), `research/probe_logout_navigation.py`
  (Q-UI-41); helpers in `research/common.py`. Q-API-19 and Q-API-20 come from a session-token probe
  (`python research/probe_session_tokens.py --run 1`), which also prints the Swagger operations for Q-API-21.
  Q-API-21 is read from Swagger, Q-UI-37 from Swagger and the frontend code, both without requests. Q-UI-42 and
  Q-UI-43 record two CI failures.
- The main scripts were run twice (`--run 1`, `--run 2`) with logs matching line by line except for the run time and
  the key order of one error body (Q-API-07). The failure probes were also run twice, with the same behaviour
  (Q-UI-28 … Q-UI-35); Q-UI-38 … Q-UI-40 were added in the second run.
- Only temporary users: `probe_<uuid>@example.com` and, for the failure probes of step 7a, one
  `fault_<uuid>@example.com`; tokens are replaced with `<hidden>`. Users cannot be deleted and remain; created cars
  were deleted (Q-API-01 … Q-API-18, Q-UI-01 … Q-UI-14). From Q-UI-15 on, requests that change data were intercepted
  (`page.route`) and did not reach the backend, except one car request with a garbage token, answered 401
  (Q-UI-15 … Q-UI-40, Q-UI-34). Screenshots and logs go to `research/evidence/`, which is not stored in git.

## Key observations: API

**Registration and login**
- Registering an email with capitals returns 200, but login with the same capitals returns 401
  `"Login or Password incorrect"`; login in lower case succeeds; registering the lower-case email again returns 400
  `"User already exists"` (Q-API-06).
- Wrong password, unknown user and `{}` on login return 401 with the same message; an empty body returns 400
  `"Wrong format Credential Object"` (Q-API-07). Registration validation errors are 400 with `message` as an object of
  field errors (a weak password returns the password rules); `password` = `""` returns 400 without a `message` field
  (Q-API-07, Q-API-16); none of the Q-API-16 requests created a user (Q-API-16).
- The registration token and the tokens of two later logins are all accepted at once (Q-API-19). Token lifetime is
  600000 s, about 6 days 22 hours; acceptance after `exp` was not checked (Q-API-20). Swagger has no profile, password
  change or logout operations (Q-API-21).

**Cars**
- `GET /v1/cars/cities` returns 37 cities (only the `cities` key; items with `city`, `lat`, `lng`), the frontend list
  has 54, 22 are common (Q-API-03, Q-API-15). A car in the frontend-only city `Acre` is rejected with 400; in the
  API-only city `Beer Sheva` it is created (Q-API-03).
- Extra fields are ignored: `owner` becomes the creator, `bookedPeriods` an empty list (Q-API-04). Stored as sent:
  `seats` 0, `pricePerDay` 0 and −5, `year` `'abc'` and `'2999'`, `fuel` `'banana'`, `about` of 600 characters;
  a blank `model` or `city` returns 400 `"must not be blank"` (Q-API-05). Each of the nine required fields, missing
  or empty, returns 400 and no car is saved (Q-API-17).
- A repeated serial number returns 400 for the owner and for another user; the original car is unchanged (Q-API-13).
  Deleting another user's car or a non-existent one returns 400 `"Car with serial number <serial> not found"` and the
  owner's car stays; deleting one's own car returns 200, a repeat 400 (Q-API-10).
- `POST /v1/cars` with `Content-Type: text/plain` returns 500 and creates nothing (Q-API-11).

**Search and booking**
- Dates do not change the result: future, past, reversed, missing and `null` dates give the same number of cars,
  including the test car (Q-API-02, Q-API-18). The city is case-sensitive: `tel aviv` and `TEL AVIV` find 0 cars
  (Q-API-02). The `page` and `size` query parameters did not change the number of cars (Q-API-02, Q-API-14). A Tel Aviv
  search returned about 18 MB; search works without a token (Q-API-02).
- Every booking attempt with a token returned 200 with the same message: overlapping, past and reversed dates,
  a non-existent car, the owner's own car. `bookedPeriods` stayed empty and the car was still found for the booked
  dates; without a token the answer is 403 (Q-API-01, Q-API-18). A scan of all 37 cities found 13305 cars, none with
  non-empty `bookedPeriods` (Q-API-12).

**Authentication and authorization**
- Without a token, protected operations return 403 with an empty body and no `Content-Type`; a garbage token returns
  401 `"Malformed JWT JSON: …"`, the `Basic` scheme returns 401
  `"JWT strings must contain exactly 2 period characters. Found: 0"`; no car is created (Q-API-09).
- Routes outside Swagger (`GET /v1/cars/{serial}`, `GET /v1/user/profile`, `PUT /v1/cars`) return 403 with and
  without a token, as does the non-existent `GET /v1/nonexistent` (Q-API-08).

## Key observations: UI

**Forms and pages**
- Car form: `gear`, `wheelsDrive` and `doors` are not sent, `fuel` goes in lower case (Q-UI-05, Q-UI-15), a photo
  file as a base64 data URL (Q-UI-06, Q-UI-16). Client-side checks show `Required` and minimum-value messages, but
  a cleared City leaves Submit enabled (Q-UI-20) and the request fails with “Failed to submit car” (Q-UI-04), as with
  a frontend-only city (Q-UI-03). After a (substituted) 200 response Make is emptied, with no success message
  (Q-UI-15, Q-UI-26).
- Registration with a weak password shows “Registration failed” with the text `"[object Object]"`, with the real
  response and with its recorded body (Q-UI-07, Q-UI-40); a repeated email shows `"User already exists"` (Q-UI-08).
  An email typed with capitals is sent as typed on registration and in lower case on login (Q-UI-09). The login
  dialog shows `"Login or Password incorrect"` for 400, 401, 500 and a dropped connection (Q-UI-10, Q-UI-30).
- The car page does not load: the browser aborts `GET /v1/cars/<serial>` (`net::ERR_FAILED`), the page shows
  «Не удалось загрузить машину» (“Failed to load the car”), so “Rent now” is unreachable (Q-UI-01, Q-UI-02, Q-UI-19).
- The profile page shows «Не удалось загрузить профиль» (“Failed to load the profile”): the response is blocked by
  CORS (Q-UI-18, Q-UI-27). With a substituted profile, after «Сохранить» (“Save”) the page sends
  `PUT /v1/user/profile` (intercepted, answered 200 by the probe) and a browser alert shows
  «Профиль обновлён» (“Profile updated”) (Q-UI-18).

**Search**
- The city list is built into the frontend (54 cities), suggestions follow its order (Q-UI-21, Q-UI-27); a city typed
  in another case is sent as typed and finds 0 cars (Q-UI-23). An empty result has no “nothing found” message
  (Q-UI-12, Q-UI-24). Rows per page offers 10, 20 and 50, Next opens the remaining cards (Q-UI-22); `size=500` in the
  URL shows all cards (Q-UI-12). The calendar disables days before today; paging forward stops at November 2027,
  where 5 days are available and 25 disabled (Q-UI-11; today + 365 days = 2027-11-05).

**Session**
- Logout is client-side only: `token` is removed, `tokenType=Bearer` stays, and the token saved before logout is still
  accepted by `GET /v1/cars/my` (Q-UI-14). Logout navigates to `/` first, then to `/search`, so an immediate
  `page.url` read can see `/` (Q-UI-41).
- A guest can open the car form; submitting it gets 403 (Q-UI-13). A shared interceptor reacts to any 401 by removing
  `token` and saving `postLoginRedirect`, without redirecting to login; “Log out” stays in the navigation
  (Q-UI-13, Q-UI-17, Q-UI-36, Q-UI-39). After a 401 on the profile page, only a reload leads to `/login` (Q-UI-33).

**Backend failures** (an error status with an empty body, dropped connection, 5 s and 35 s delays, an nginx 502 page)
- Search: no message for any failure; after a failed search the previous results stay even when the form and URL show
  another city and dates, and a card shows neither its city nor dates (Q-UI-28, Q-UI-29, Q-UI-38).
- Registration: 409 shows “User with that email already exists”; 401, 500 and a dropped connection show “Registration
  failed. Try again”; 400 with an empty body shows `"Request failed with status code 400"` (Q-UI-31). Car form:
  “Failed to submit car”, the form data is kept; a real 401 server text is not shown (Q-UI-32, Q-UI-34).
- The HTTP client has no timeout (axios default `timeout: 0`): during a delay the search and login buttons show
  “Loading...” for the whole wait (Q-UI-27, Q-UI-35). The code reads only `message` from an error body, and only on
  registration with 400; Swagger declares no 409, 403 or 502 (Q-UI-37).

**CI failures investigated** (causes not established, not reproduced)
- After OK on the login dialog, loading of the `/search` document did not start within 30 s; navigation diagnostics
  were added (Q-UI-42). Chrome lost the connection to its renderer while opening `/login` (Q-UI-43).

## Framework: concurrent journal writes

The section «Фреймворк: одновременная запись журналов прогона» (“Framework: concurrent writes of the run journals”)
is about the test framework, not the application. A local run with `-n 2` on Windows failed with
`JSONDecodeError: Extra data` while parsing `logs/car_factory.jsonl`.
- `research/race_journal_append.py`: 4 processes start at once and each writes 5000 records to each journal with the
  project's own functions. With one shared file per journal in append mode, three runs lost 1243, 1471 and 1377 of
  20000 car-factory records and 1145, 1361 and 1326 of 20000 user records, and had 1, 4 and 1 broken lines (empty
  lines inside the file; no glued records).
- With a file per process, written through `utils/run_journal.py`, the same three-run check lost 0 records and had
  0 broken lines.

## From facts to requirements

The log records facts, with two exceptions. The section «Шаг 7a: кандидаты в требования» (“Step 7a: requirement
candidates”) holds proposals, not decisions, some of them worded as assessments; Q-UI-42 also states that the
test's wait was correct. The decisions are in
[requirements.en.md](requirements.en.md), whose “Actual behaviour” column links back to these Q-… IDs.

## How to reproduce

Run the scripts as described in [research/README.md](../../research/README.md) *(in Russian)*: each takes a run
label (`--run 1`) and writes its log and, where taken, screenshots to `research/evidence/`; counts of cars may differ
(Q-API-02).
