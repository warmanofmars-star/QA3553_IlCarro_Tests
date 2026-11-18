<!-- translation-of: docs/requirements/requirements.md sha256:b736477609af -->
# Reconstructed IlCarro requirements

Draft v9, 2026-11-15. Change history — in the [Russian original](requirements.md).
The Russian original is authoritative; this file is its English translation.

IlCarro has no SRS, so the requirements are reconstructed from the sources listed below. Facts about the
application's behaviour are in `research-log.md` (references like `Q-API-01`).

## How to read this document

**Sources**, ranked by strength:

| Code | Source | Where |
|---|---|---|
| SW | Swagger (OpenAPI 3.0.1) | `docs/requirements/api-docs.json` |
| RFC | RFC 9110 HTTP Semantics | https://www.rfc-editor.org/rfc/rfc9110 |
| OWASP | OWASP API Security Top 10 (2023), ASVS 4.0.3 | https://owasp.org/API-Security/ |
| FE | Frontend code (the icarro-v1.netlify.app bundle, file name given) | build of 2026-11-05 |
| EXP | Research of the actual behaviour | `docs/requirements/research-log.md` |

**Applicability rule.** The frontend code (FE) is a source only for the behaviour of the interface. For the API
only SW, RFC and OWASP apply. So the form rule “price ≥ 1” does not make it an error that the API
accepts a price of 0: this is a discrepancy between sources (the DISC section), not a violation of an API requirement.

**The “Actual behaviour” column** is a snapshot of 2026-11-05 with a reference to a research question:

- *met* — the behaviour matches the requirement;
- *partly* — the checked part is met, the rest is not verified (stated what exactly);
- *violated* — the behaviour contradicts the requirement; a candidate for the known bug registry;
- *not verified* — the research did not touch this item, a test will check it;
- *not verifiable* — another violation blocks the check (stated which one).

**Basis of the fact.** A `Q-…` reference is an entry in `research-log.md`, reproducible by a script.
“Probe 2a” is a manual request made while analysing the sources; it is not part of the log. “From the code” is a
conclusion from the frontend code, not checked on screen. “Baseline run” is the result of the existing tests
before the refactoring (2026-11-05). Such items are confirmed by tests in step 3.
“From the code” with a build date — the item was added later and checked against the build of that date.

**Three categories of findings** (as in Phonebook):

1. A violation of a requirement `REQ-…` or a discrepancy between sources `DISC-…` → a known bug; the registry
   entry references the ID.
2. An observation `OBS-…` → bad behaviour for which there is no requirement; the source of the expectation is named explicitly.
3. A requirement that is met → an ordinary passing test that protects the good behaviour.

**Tag in tests:** `@allure.tag("REQ-BOOK-01")`, `@allure.tag("DISC-02")`, `@allure.tag("OBS-04")`.

Frontend file names contain the build hash (`Register-CYJGzX27.js`) and change with every new deployment.
Below they are given without the hash: `Register`, `Login`, `LetCarWork`, `Search`, `CityAutocomplete`,
`CarDetails`, `Profile`, `cars` (API calls), `index` (authorization, interceptors, routes),
`default` (price display).

---

## 1. API

### 1.1 Registration and login (AUTH)

| ID | Requirement | Source | Actual behaviour |
|---|---|---|---|
| REQ-AUTH-01 | Registration with valid data returns 200 and an `accessToken`. | SW: `/v1/user/registration/usernamepassword` → 200 `TokenDto` | met (Q-API-06) |
| REQ-AUTH-02 | The fields `username`, `password`, `firstName`, `lastName` are required: without them or with empty values — 400. | SW: `RegistrationBodyDto.required`, response 400 | met (Q-API-07, Q-API-16: each field missing or empty — 400; with `password` = `""` the response has no `message` field) |
| REQ-AUTH-03 | Registration password: at least 8 characters, contains a digit, a lowercase and an uppercase Latin letter and a special character from `@$#^&*!`; otherwise 400. | SW: `RegistrationBodyDto.password.pattern` | met (Q-API-07: `abc123`, `Abcdefg1` rejected) |
| REQ-AUTH-04 | Registering the same `username` again is rejected with 400. | SW: response 400 (409 is not described in the contract) | met (Q-API-06, Q-API-07) |
| REQ-AUTH-05 | Login with valid credentials returns 200 and an `accessToken`. | SW: `/v1/user/login/usernamepassword` → 200 `TokenDto` | met (Q-API-06) |
| REQ-AUTH-06 | Login with a wrong password or as a non-existent user — 401. | SW: response 401 | met (Q-API-07) |
| REQ-AUTH-07 | The login body is validated against the contract: without required fields or with a password that does not match the pattern — 400. | SW: `AuthenticationBodyDto.required` and `pattern`, response 400 | **violated**: 401 (Q-API-07: `{}`, `abc123`) |

### 1.2 Cars (CAR)

| ID | Requirement | Source | Actual behaviour |
|---|---|---|---|
| REQ-CAR-01 | An authorized user adds a car: 200 and `message`; the car appears in the owner's `/v1/cars/my`. | SW: `POST /v1/cars` → 200 `ResponseMessageDto`; “Get User cars” | met (Q-API-04, Q-API-05) |
| REQ-CAR-02 | Required `CarDto` fields (`serialNumber`, `manufacture`, `model`, `year`, `fuel`, `seats`, `carClass`, `pricePerDay`, `city`): without them or with an empty value — 400. | SW: `CarDto.required`, response 400 | met for all nine fields: a field missing or empty — 400, the car is not created (Q-API-17) |
| REQ-CAR-03 | A value of the wrong type (for example, `seats` as a string) — 400, not a server error. | SW: `CarDto` field types, response 400; RFC 9110 §15.6 (5xx — a server failure) | **violated**: 500 (baseline run, test `test_api_car_mutations[seats]`; not part of the research log) |
| REQ-CAR-04 | The car owner is determined by the token; `owner` and `bookedPeriods` from the request body are ignored. | OWASP API3:2023 (Broken Object Property Level Authorization) | met (Q-API-04) |
| REQ-CAR-05 | `serialNumber` is unique across the whole system: a duplicate — 400. | SW: `serialNumber` is the car identifier in the paths `/v1/cars/{serialNumber}` | met: a duplicate by the same owner and by another user — 400, the car is not overwritten (Q-API-13) |
| REQ-CAR-06 | The car's city must be in the `/v1/cars/cities` list; otherwise — 400. | EXP: we record the behaviour — SW ties a car to a city and serves the list of supported cities | met (Q-API-03) |
| REQ-CAR-07 | `/v1/cars/my` returns only the cars of the token owner. | SW: “Get User cars”; OWASP API1:2023 | met (Q-API-04) |
| REQ-CAR-08 | The owner deletes their car: 200; after that the car is not in `/v1/cars/my`. | SW: `DELETE /v1/cars/{serialNumber}` → 200 | met (Q-API-10) |
| REQ-CAR-09 | Another user's car cannot be deleted: the car stays with its owner. | OWASP API1:2023 (BOLA) | met (Q-API-10) |
| REQ-CAR-10 | A non-existent or another user's car on delete — 404. For another user's car, 404 does not reveal that the car exists. | RFC 9110 §15.5.5 | **violated**: 400 (Q-API-10) |

### 1.3 Search (SEARCH)

| ID | Requirement | Source | Actual behaviour |
|---|---|---|---|
| REQ-SEARCH-01 | Search is available without authorization. | SW: `/v1/cars/search` has no `security` | met (Q-API-02: search requests were made without a token) |
| REQ-SEARCH-02 | Search returns only cars of the given city. | SW: “Search Car by city and period” | met (Q-API-14: in the Sderot results every car has `city` = Sderot) |
| REQ-SEARCH-03 | A car whose booking period overlaps the requested one is not returned. | SW: “Search Car by city and period”; `CarDto.bookedPeriods` | **not verifiable**: bookings are not saved (REQ-BOOK-01), no car in the system has `bookedPeriods` filled in (Q-API-12: 37 cities, 13,305 cars) |

### 1.4 Booking (BOOK)

| ID | Requirement | Source | Actual behaviour |
|---|---|---|---|
| REQ-BOOK-01 | A successful booking (200) is saved: the period with the booker's email appears in the car's `bookedPeriods`. | SW: “Booking car”; `CarDto.bookedPeriods` of type `BookedDto {email, startDate, endDate}` | **violated**: `bookedPeriods` stays `[]` (Q-API-01) |
| REQ-BOOK-02 | Booking a non-existent car — 404. | RFC 9110 §15.5.5 | **violated**: 200 “Car booked successfully!” (Q-API-01) |
| REQ-BOOK-03 | Booking requires authorization. | SW: `security: Bearer Authentication` | met: refused without a token (Q-API-01); the response code — see REQ-SEC-01 |

### 1.5 Cities (CITY)

| ID | Requirement | Source | Actual behaviour |
|---|---|---|---|
| REQ-CITY-01 | `/v1/cars/cities` is available without authorization and returns a list of `{city, lat, lng}`. | SW: “Get All Cities”, `CitiesDto` | met: the list of cities — Q-API-03; without a token — 200, every element is `{city, lat, lng}` — Q-API-15 |

### 1.6 Security and protocol (SEC)

| ID | Requirement | Source | Actual behaviour |
|---|---|---|---|
| REQ-SEC-01 | A request to a protected endpoint without a token — 401. | SW: response 401; RFC 9110 §15.5.2 | **violated**: 403 with an empty body (Q-API-09) |
| REQ-SEC-02 | An invalid token — 401. | SW; RFC 9110 §15.5.2 | met (Q-API-09) |
| REQ-SEC-03 | An error text does not reveal implementation details. | OWASP API8:2023; ASVS 4.0.3 V7.4.1 | **violated**: `message` contains JWT parser texts (“Malformed JWT JSON…”, “JWT strings must contain exactly 2 period characters”) (Q-API-09) |
| REQ-SEC-04 | An unsupported `Content-Type` — 415, not a server error. | RFC 9110 §15.5.16 | **violated**: 500 (Q-API-11) |
| REQ-SEC-05 | An unknown path — 404; an unsupported method — 405. | RFC 9110 §15.5.5, §15.5.6 | **violated**: 403 with an empty body (Q-API-08) |
| REQ-SEC-06 | Logging out invalidates the token. | ASVS 4.0.3 V3.3.1 | **violated**: the token is accepted after “Log out” (Q-UI-14); the API has no server-side logout |
| REQ-SEC-07 | The size of accepted and returned data is limited. | OWASP API4:2023 (Unrestricted Resource Consumption) | **violated**: a 1.4 MB image in base64 is accepted and stored (Q-UI-06); search returns all cars of a city without pagination — about 18 MB for Tel Aviv (Q-API-02) |

---

## 2. Interface

### 2.1 Registration (UI-REG)

| ID | Requirement | Source | Actual behaviour |
|---|---|---|---|
| REQ-UI-REG-01 | The fields are validated before submission: Name, Last name, Email (format), Password (at least 6, a letter and a digit), consent to the terms. Error texts — from the code. The button is disabled while the form is invalid. | FE: `Register` | not verified by the research; covered by the existing UI tests |
| REQ-UI-REG-02 | After a successful registration — the “Registered” / “You are logged in success” dialog; the user is logged in. | FE: `Register`, `index` | met (Q-UI-09) |
| REQ-UI-REG-03 | On a 400 response the “Registration failed” dialog shows the server's error text. | FE: `Register` | **violated** for an object response: `"[object Object]"` (Q-UI-07); met for a string (Q-UI-08). Cause — DISC-01 |
| REQ-UI-REG-04 | A guest sees a “Sign up” link in the navigation; it leads to the registration form `/register`. | FE: `index` (guest navigation: links “Sign up” → `/register` and “Log in” → `/login`; route `/register`) | from the code (build of 2026-11-11) |
| REQ-UI-REG-05 | On a 401 or 500 response to registration and on a dropped connection — a `role=alert` message “Registration failed. Try again”. | FE: `Register` (the “any other error” branch: not 400 with `message` and not 409) | met: 401, 500 and a dropped connection, the response body is empty (Q-UI-31) |

### 2.2 Login (UI-LOGIN)

| ID | Requirement | Source | Actual behaviour |
|---|---|---|---|
| REQ-UI-LOGIN-01 | Email is required and validated for format, the password is required; before submission the email is converted to lowercase. | FE: `Login` | partly: converting the email to lowercase is met (Q-UI-09); required fields and the email format are not verified |
| REQ-UI-LOGIN-02 | After login — the “You are logged in success” dialog, “Log out” in the navigation. | FE: `index` | met (Q-UI-09) |
| REQ-UI-LOGIN-03 | On 401 — the “Login failed” dialog with the text “Login or Password incorrect”; on any other error — “Login failed. Try again”. | FE: `Login` (the `authError` value) | **violated**: on 500, 400 and a network drop the same text “Login or Password incorrect” — it is hard-coded in the dialog, and `authError` is not shown (Q-UI-10) |

### 2.3 Adding a car (UI-CAR)

| ID | Requirement | Source | Actual behaviour |
|---|---|---|---|
| REQ-UI-CAR-01 | The fields marked with `*` are validated before submission: City, Make, Model, Year, Fuel, Seats (≥ 1), Car class, Car registration number, Price (≥ 1). | FE: `LetCarWork` (the `*` markers and the validation schema) | **violated** for City: the `*` marker is there, but the validation schema has no such field — Submit is enabled, the form is sent with `city: ""` (Q-UI-04, Q-UI-20). The other fields are met: empty — Submit is disabled, “Required” under the field; Seats and Price below 1 — Submit is disabled (Q-UI-20) |
| REQ-UI-CAR-02 | A successful submission — “Car submitted successfully” and the form is cleared; an error — “Failed to submit car”. | FE: `LetCarWork` | partly: “Failed to submit car” on an error is met (a 400 response — Q-UI-03, Q-UI-04; 500 and a dropped connection — Q-UI-32); after a 200 response the form is cleared, but the text “Car submitted successfully” does not appear on screen (Q-UI-15, the response was substituted) |
| REQ-UI-CAR-03 | The Fuel value is sent to the API in lowercase: `petrol`, `diesel`, `hybrid`, `electric`. | FE: `LetCarWork` | met (Q-UI-05, Q-UI-15: all four values) |
| REQ-UI-CAR-04 | The photo — as a link or as a file; a file is sent in the `image` field as a data URL (base64). | FE: `LetCarWork` | met (a file — Q-UI-06, Q-UI-16; a link goes to `image` as entered — Q-UI-16); consequences — REQ-SEC-07 |
| REQ-UI-CAR-05 | On a 401 response to the car form submission, the UI does not show the user the error text from the server response. | OWASP: ASVS 4.0.3 V7.4.1 (Error Handling: a generic message on error); FE: `LetCarWork` | met: a real 401 response with a JWT parser text — only “Failed to submit car” on screen (Q-UI-34) |

### 2.4 Search (UI-SEARCH)

| ID | Requirement | Source | Actual behaviour |
|---|---|---|---|
| REQ-UI-SEARCH-01 | “Yalla!” is enabled only when the city and both dates are filled in. | FE: `Search` | partly: with the fields filled in the button is enabled (Q-UI-12); that it is disabled with empty fields is not verified |
| REQ-UI-SEARCH-02 | In the calendar, days before today and after “today + 365 days” are unavailable. | FE: `Search` (`minDate`, `maxDate`) | met (Q-UI-11) |
| REQ-UI-SEARCH-03 | The city autocomplete shows up to 8 options from the frontend's list; the city can be typed in manually. | FE: `CityAutocomplete` | met: up to 8 options from the frontend's list, in its order (Q-UI-21); typing the city manually (Q-UI-12, Q-UI-23) |
| REQ-UI-SEARCH-04 | Pagination of the results is client-side: `page` and `size` in the URL, 10, 20 or 50 cards per page. | FE: `Search` | met: `page` and `size` in the URL, “Rows per page” options 10, 20, 50, Next — the next page (Q-UI-22); `size` in the URL changes the number of cards (Q-UI-12) |
| REQ-UI-SEARCH-05 | The price on a card is shown with one decimal place. | FE: `default` (`toFixed(1)`) | met (Q-UI-12); consequences — OBS-08 |
| REQ-UI-SEARCH-06 | The dates field is read-only: dates are picked in a calendar that opens on a click on the field and closes on a click outside the calendar. | FE: `Search` (the `#dates` field with `readOnly`; a click on the field toggles the calendar; a `mousedown` handler outside the calendar closes it) | from the code (build of 2026-11-11) |
| REQ-UI-SEARCH-07 | The search calendar shows the standard react-date-range interface: months are switched with arrow buttons within `minDate`…`maxDate` (REQ-UI-SEARCH-02), today is marked (class `rdrDayToday`). | FE: the react-date-range default, the application does not override it. `Search` passes to the `DateRange` calendar only `ranges`, `onChange`, `rangeColors`, `minDate`, `maxDate`, `moveRangeOnFirstSelection`; in the react-date-range chunk that `Search` loads: `showMonthArrow: true` in `defaultProps`, a day with `isToday` gets the class `rdrDayToday` | the react-date-range default, the application does not override it (build of 2026-11-11); that “back” does nothing in the current month — OBS-10 |

### 2.5 Car page (UI-CARPAGE)

| ID | Requirement | Source | Actual behaviour |
|---|---|---|---|
| REQ-UI-CARPAGE-01 | A click on a card opens `/cars/{serial}` with the car's data. | FE: `Search`, `CarDetails` | **violated**: «Не удалось загрузить машину» (“Failed to load the car”) (Q-UI-01, Q-UI-19). Cause — DISC-05 |
| REQ-UI-CARPAGE-02 | “Rent now!!”: a guest is sent to login with a return to the car page; a logged-in user sees the message «Бронирование пока не реализовано в API» (“Booking is not implemented in the API yet”). | FE: `CarDetails` | **not verifiable**: the page does not open (Q-UI-02) |

### 2.6 Session (UI-SESSION)

| ID | Requirement | Source | Actual behaviour |
|---|---|---|---|
| REQ-UI-SESSION-01 | On a 401 response the frontend removes `token` and stores `postLoginRedirect`. | FE: `index` (the response interceptor) | met (Q-UI-13, Q-UI-17; the car form — Q-UI-32, search as a logged-in user — Q-UI-39; summary — Q-UI-36) |
| REQ-UI-SESSION-02 | “Log out” removes the token and navigates to `/search`. | FE: `index` | met (Q-UI-14) |
| REQ-UI-SESSION-03 | A failed login or registration attempt — an error response or a dropped connection — does not create a session: there is no `token` in localStorage and no “Log out” in the navigation. | OWASP: the Fail securely principle (OWASP Developer Guide, secure design principles); ASVS 4.0.3 V4.1.5 (Access Control: access fails securely, including on exceptions; applied to the client-side session state) | met: login — 401, 500, a dropped connection (Q-UI-30); registration — 400, 401, 500, a dropped connection (Q-UI-31), 400 with the body of a real response (Q-UI-40) |

---

## 3. Discrepancies between sources (DISC)

The sources contradict each other. A discrepancy is a defect of the system or of the requirements; the bug
registry references it by ID.

| ID | Issue | Sources | Consequence |
|---|---|---|---|
| DISC-01 | Password rules: the frontend — at least 6, a letter and a digit; Swagger and the API — at least 8, an uppercase letter, a lowercase letter, a digit, a special character is required; the API error text says a special character “may” be used (Can contain). | FE: `Register`; SW; EXP (Q-API-07) | The form accepts a password that the API rejects; the user sees `"[object Object]"` (Q-UI-07) |
| DISC-02 | Cities: 54 in the frontend, 37 in the API, 22 in common. Different spellings: `Beersheba` / `Beer Sheva`, `Kiryat …` / `Qiryat …`, `Ra'anana` / `Raanana`. | FE: `CityAutocomplete`; EXP (Q-API-03) | A car cannot be added in 32 cities from the autocomplete — “Failed to submit car” (Q-UI-03); search in them is silently empty (Q-UI-12); 15 API cities are unreachable from the interface |
| DISC-03 | Email case inside the API: registration converts the email to lowercase (a repeat with a different case — “User already exists”), login does not (an email with capital letters — 401). | EXP (Q-API-06) | Through the API a user cannot log in with the same email they registered with. The interface hides this by converting the email to lowercase on login (Q-UI-09) |
| DISC-04 | The car form fields Gear, WD, Doors (and `features` in the form state) are missing from `CarDto`; the frontend collects them and does not send them. | FE: `LetCarWork`; SW: `CarDto` | What the user entered is silently lost (Q-UI-05, Q-UI-15) |
| DISC-05 | The frontend calls endpoints that exist neither in Swagger nor on the backend: `GET /v1/cars/{id}`, `GET /v1/user/profile`. | FE: `cars`, `CarDetails`, `Profile`; SW; EXP (Q-API-08) | The car page does not work (Q-UI-01). `GET /v1/cars/{id}` and `GET /v1/user/profile` answer 403 (Q-API-08); in the browser the car and profile requests end with `net::ERR_FAILED` (Q-UI-01, Q-UI-18, Q-UI-19). `PUT /v1/user/profile` — DISC-10 |
| DISC-06 | Booking: Swagger describes the endpoint; the frontend considers it not implemented: «Бронирование пока не реализовано в API» (“Booking is not implemented in the API yet”); the API answers with success and saves nothing. | SW; FE: `CarDetails`; EXP (Q-API-01) | See REQ-BOOK-01, REQ-BOOK-02 |
| DISC-07 | Car field bounds: the frontend requires Seats ≥ 1 and Price ≥ 1; Swagger has no limits; the API accepts 0 and negative values. | FE: `LetCarWork`; SW; EXP (Q-API-05) | By the applicability rule this is not an API bug; the API behaviour — OBS-03 |
| DISC-08 | Pagination: the frontend passes `page` and `size` to search; Swagger has no such parameters; the API ignores them. | FE: `cars`; SW; EXP (Q-API-02) | Pagination works only on the client; the response is not limited — REQ-SEC-07 |
| DISC-09 | The car page reads fields that `CarDto` does not have: `make`, `car_class`, `image_url`, `imageUrl`, `price_per_day`, `engine`, `gear`, `wheels_drive`, `fuel_consumption`, `doors`, `address`, `distance_included`, `description`. The `CarDto` fields with the same data are named differently (`manufacture`, `carClass`, `image`, `pricePerDay`, `about`) or do not exist. | FE: `CarDetails` (build of 2026-11-12); SW: `CarDto` | From the code: even with a response in the `CarDto` format the page would not show the make, class, photo and description. Not verifiable on screen: the page does not open — its request is not described in the contract (DISC-05; Q-UI-01, Q-UI-19) |
| DISC-10 | The frontend sends `PUT /v1/user/profile` to save the profile; Swagger has no such operation. | FE: `Profile`; SW | From the frontend code. `PUT` is sent only after the profile has loaded successfully, and `GET /v1/user/profile` always ends in a failure (Q-UI-27, Q-UI-33): unreachable in the application |
| DISC-11 | A repeated email on registration: the frontend handles a 409 response — `role=alert` “User with that email already exists”; Swagger does not declare 409 (registration has the responses 200, 400, 401, 500); the server answers a repeated email with 400 `"User already exists"`. | FE: `Register`; SW; EXP (Q-API-07) | The frontend's 409 branch is unreachable: on a real repeated email the UI shows the “Registration failed” dialog with the server text “User already exists” (Q-UI-08), not its own message about a taken email; the message of the 409 branch is visible only with a substituted response (Q-UI-31). The responses in Swagger and what the code reads — Q-UI-37 |

---

## 4. Observations (OBS)

There is no requirement; the source of the expectation is named explicitly. They go to the observation registry,
not to the bug registry.

| ID | Issue | Source of the expectation | Actual behaviour |
|---|---|---|---|
| OBS-01 | Search is case-sensitive to the city: `tel aviv` — 0 cars. | general search principles | Q-API-02 |
| OBS-02 | Search and booking accept past dates and an end before the start. | domain logic; Swagger sets no limits | Q-API-01, Q-API-02, Q-API-18. Missing dates are not part of the item: in Swagger `SearchDto` and `BookingPeriodDto` have no required fields — the contract allows a request without dates |
| OBS-03 | The API accepts meaningless car values: `seats` 0, a price of 0 and −5, `year` “abc” and “2999”, `fuel` “banana”. | domain logic; see DISC-07 | Q-API-05 |
| OBS-04 | An empty search result is not indicated in any way: there is no “nothing found” message. | general UX principles. Criterion: the empty result is announced by a message — a `role=status` or `role=alert` element, the way the frontend shows its other messages (the car submission result: `role=status` / `role=alert`, Q-UI-26; FE: `LetCarWork`); the message text is not specified | Q-UI-12, Q-UI-24; FE: `Search` |
| OBS-05 | After a 401 there is no redirect to the login page; “Log out” stays in the navigation although the token has been removed. | general UX principles | Q-UI-13, Q-UI-17; search as a logged-in user — Q-UI-39 |
| OBS-06 | The add-car form opens for a guest; the submission ends with “Failed to submit car”. The frontend has a route guard mechanism, but it is applied only to `/profile`. | general UX principles | Q-UI-13; FE: `index` |
| OBS-07 | “Failed to submit car” does not explain the cause: an unsupported city, an empty city, no authorization — the text is the same. | general UX principles | Q-UI-03, Q-UI-04, Q-UI-13 |
| OBS-08 | The price on screen is rounded: 1234.56 is shown as “1234.6”. The amount on screen differs from the stored one. | general principles of displaying money amounts | Q-UI-12 |
| OBS-09 | After registration the URL stays `/register`. | general UX principles | Q-UI-09 |
| OBS-10 | The “previous month” button in the calendar is enabled but does nothing. | general UX principles | Q-UI-11 |
| OBS-11 | The interface is in English, but the car and profile pages show Russian texts: «Не удалось загрузить машину» (“Failed to load the car”), «Загрузка...» (“Loading...”), «Мой профиль» (“My profile”). | a single interface language | «Не удалось загрузить машину» (“Failed to load the car”) — Q-UI-01; the other texts — from the code (`CarDetails`, `Profile`) |
| OBS-12 | A failed search request — an error response (500), a dropped connection, a proxy page (502) — is not indicated on screen in any way: there are no messages, the button says “Yalla!” again. | general UX principles. Criterion: after a failed search there is a message on screen — a `role=status` or `role=alert` element, as in OBS-04; the message text is not specified | Q-UI-24, Q-UI-28; FE: `Search` (on an error only `console.error`, Q-UI-27) |
| OBS-13 | After a failed search the screen keeps the results of the previous successful search, including those for another city and dates, without any mark: the form and the URL already show the new city and dates, while the cards do not show their city and dates. | general UX principles. Criterion: after a failed search either there are no cards of the previous results on screen, or there is a message — a `role=status` or `role=alert` element | Q-UI-29, Q-UI-38; FE: `Search` (the list of cars changes only on a successful response) |
| OBS-14 | Login has no limit on waiting for the response: 35 s after the form is submitted the button says “Loading...”, there is no message, the frontend does not abort the request. | general UX principles: waiting without a limit and without feedback. Criterion: 35 s after the login is submitted at least one of these holds — the submit button is not “Loading...”; there is a message (`role=status`, `role=alert` or a `role=dialog` dialog — the way the login screen shows errors, Q-UI-30); the frontend aborted the request | Q-UI-35 (a 35 s delay); from the code: the HTTP client has no timeout and no request cancellation (Q-UI-27) |
| OBS-15 | On a 400 response without a `message` field the registration dialog shows the library's internal text “Request failed with status code 400”. The server returns such a response for an empty password, which the form does not send (Q-API-16). | general UX principles: an error text for the user, not a library's internal message. Criterion: the dialog text does not contain “Request failed with status code” | Q-UI-31, Q-API-16; FE: `Register` |

---

## 5. Environment constraints

- **Users cannot be deleted:** the API has no such endpoint. Every test run leaves
  temporary users behind.
- **The backend is shared:** other users add and delete cars. Absolute numbers (for example,
  the number of cars in a city) must not be used in tests.
- **The search response for large cities weighs tens of megabytes** (Tel Aviv — about 18 MB). For search
  tests, cities with few cars are a better choice.
- **Frontend file hashes change with every new build.** References to the frontend code are valid
  for 2026-11-05.
