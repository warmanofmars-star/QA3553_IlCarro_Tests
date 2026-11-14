# Матрица трассируемости требований

> **Файл сгенерирован `scripts/coverage_matrix.py`, руками не править.**
> Пункты и формулировки — из [`requirements.md`](requirements.md) (здесь — первое предложение пункта),
> покрытие — теги `@allure.tag` на тестах, маркеры `known_bug` и `observation`, отсутствие теста —
> реестр `data/coverage_exceptions.py`. Обновить: `python scripts/coverage_matrix.py`.
> CI и pre-commit проверяют актуальность: `python scripts/coverage_matrix.py --check`.

Матрица показывает, что проверяет набор тестов, а не результат прогона. Колонка «Факт»
в `requirements.md` — снимок исследования, а не статус автоматизации.

Статусы:

- ✅ **покрыт** — на пункт есть тест, и он проходит;
- 🟡 **частично** — тест есть и проходит, но проверяет не весь пункт:
  что не покрыто и в каком PR это появится — в колонке «Статус» (реестр
  `data/coverage_exceptions.py`, категория `partial`);
- 🐞 **покрыт как известный баг** — тест есть и упирается в дефект из `data/known_bugs.py`
  (строгий xfail); ключ записи — в колонке «Реестр»;
- 👁 **покрыт как наблюдение** — тест фиксирует поведение из `data/observations.py`
  (строгий xfail);
- ⚪ **исключение** — теста нет и не будет, пока не изменится приложение;
- 🕓 **запланирован** — теста пока нет, указан PR, в котором он появится.

«Покрыт» значит, что assert хотя бы одного теста проверяет пункт так, как он записан
в `requirements.md`; если проверена только часть, пункт записан как частично покрытый.

## Сводка

| Статус | REQ | DISC | OBS | Всего |
|---|---:|---:|---:|---:|
| ✅ покрыт | 37 | 0 | 0 | 37 |
| 🟡 частично | 0 | 0 | 0 | 0 |
| 🐞 покрыт как известный баг | 15 | 7 | 0 | 22 |
| 👁 покрыт как наблюдение | 0 | 0 | 11 | 11 |
| ⚪ исключение | 3 | 2 | 0 | 5 |
| 🕓 запланирован | 0 | 0 | 0 | 0 |
| **Всего** | 55 | 9 | 11 | 75 |

- **Исключения по категориям:** вредит общему бэкенду — 1; заблокировано другим дефектом — 2; функциональность недостижима — 2.
- **Запланировано:** PR 6.2 (API) — 0; PR 6.3a (UI: перехват запросов и сессия) — 0; PR 6.3b (UI: остальное и наблюдения) — 0.
- **Покрыто частично, доработка:** PR 6.2 (API) — 0; PR 6.3a (UI: перехват запросов и сессия) — 0; PR 6.3b (UI: остальное и наблюдения) — 0.
- **Известные баги:** 21 в реестре `data/known_bugs.py`; **наблюдения:** 11 в реестре `data/observations.py`.
- **Автотесты:** 160, у каждого есть тег хотя бы одного пункта.

## Требования и тесты

### 1.1 Регистрация и вход (AUTH)

| ID | Формулировка | Тесты | Реестр | Статус |
|---|---|---|---|---|
| REQ-AUTH-01 | Регистрация с корректными данными возвращает 200 и `accessToken`. | `test_api_auth.py::test_api_registration_success` | — | ✅ покрыт |
| REQ-AUTH-02 | Поля `username`, `password`, `firstName`, `lastName` обязательны: без них или с пустыми значениями — 400. | `test_api_auth.py::test_api_registration_required_fields` | — | ✅ покрыт |
| REQ-AUTH-03 | Пароль при регистрации: не короче 8 символов, есть цифра, строчная и заглавная латинские буквы и спецсимвол из `@$#^&*!`; иначе 400. | `test_api_auth.py::test_api_registration_password_pattern` | — | ✅ покрыт |
| REQ-AUTH-04 | Повторная регистрация того же `username` отклоняется с 400. | `test_api_auth.py::test_api_registration_existing_user` | — | ✅ покрыт |
| REQ-AUTH-05 | Вход с верными данными возвращает 200 и `accessToken`. | `test_api_auth.py::test_api_login_success` | — | ✅ покрыт |
| REQ-AUTH-06 | Вход с неверным паролем или несуществующим пользователем — 401. | `test_api_auth.py::test_api_login_rejected` | — | ✅ покрыт |
| REQ-AUTH-07 | Тело входа проверяется по контракту: без обязательных полей или с паролем не по шаблону — 400. | `test_api_auth.py::test_api_login_body_not_by_contract` | `LOGIN_BODY_NOT_VALIDATED` | 🐞 покрыт как известный баг |

### 1.2 Машины (CAR)

| ID | Формулировка | Тесты | Реестр | Статус |
|---|---|---|---|---|
| REQ-CAR-01 | Авторизованный пользователь добавляет машину: 200 и `message`; машина появляется в `/v1/cars/my` владельца. | `test_api_car.py::test_api_add_car_success`<br>`test_api_car.py::test_api_car_lifecycle` | — | ✅ покрыт |
| REQ-CAR-02 | Обязательные поля `CarDto` (`serialNumber`, `manufacture`, `model`, `year`, `fuel`, `seats`, `carClass`, `pricePerDay`, `city`): без них или с пустым значением — 400. | `test_api_mutations.py::test_api_car_mutations` — `[lambda_mutation-400-Удаление обязательного поля (manufacture)-False]`; `[lambda_mutation-400-Пустая строка вместо значения (model)-False]`; `[lambda_mutation-400-Null вместо строки (carClass)-False]`<br>`test_api_mutations.py::test_api_car_required_field` | — | ✅ покрыт |
| REQ-CAR-03 | Значение неверного типа (например, `seats` строкой) — 400, а не ошибка сервера. | `test_api_mutations.py::test_api_car_mutations` — `[lambda_mutation-400-Строка вместо числа (seats)-True]` | `WRONG_TYPE_500` | 🐞 покрыт как известный баг |
| REQ-CAR-04 | Владелец машины определяется по токену; `owner` и `bookedPeriods` из тела запроса игнорируются. | `test_api_mutations.py::test_api_car_mass_assignment` | — | ✅ покрыт |
| REQ-CAR-05 | `serialNumber` уникален во всей системе: повтор — 400. | `test_api_car.py::test_api_car_duplicate_serial` | — | ✅ покрыт |
| REQ-CAR-06 | Город машины должен быть в списке `/v1/cars/cities`; иначе — 400. | `test_api_car.py::test_api_car_unsupported_city` | — | ✅ покрыт |
| REQ-CAR-07 | `/v1/cars/my` возвращает только машины владельца токена. | `test_api_car.py::test_api_my_cars_only_own` | — | ✅ покрыт |
| REQ-CAR-08 | Владелец удаляет свою машину: 200; после этого машины нет в `/v1/cars/my`. | `test_api_car.py::test_api_car_lifecycle` | — | ✅ покрыт |
| REQ-CAR-09 | Чужую машину удалить нельзя: машина остаётся у владельца. | `test_api_security.py::test_api_security_bola_delete` | — | ✅ покрыт |
| REQ-CAR-10 | Несуществующая или чужая машина при удалении — 404. | `test_api_security.py::test_api_security_bola_delete_status`<br>`test_api_security.py::test_api_idempotency_delete` | `NOT_FOUND_400` | 🐞 покрыт как известный баг |

### 1.3 Поиск (SEARCH)

| ID | Формулировка | Тесты | Реестр | Статус |
|---|---|---|---|---|
| REQ-SEARCH-01 | Поиск доступен без авторизации. | `test_api_search.py::test_api_search_without_token` | — | ✅ покрыт |
| REQ-SEARCH-02 | Поиск возвращает только машины указанного города. | `test_api_search.py::test_api_search_only_requested_city` | — | ✅ покрыт |
| REQ-SEARCH-03 | Машина, период бронирования которой пересекается с искомым, не возвращается. | — | — | ⚪ исключение: заблокировано другим дефектом (REQ-BOOK-01) |

### 1.4 Бронирование (BOOK)

| ID | Формулировка | Тесты | Реестр | Статус |
|---|---|---|---|---|
| REQ-BOOK-01 | Успешное бронирование (200) сохраняется: период с email бронирующего появляется в `bookedPeriods` машины. | `test_api_car.py::test_api_car_booking_flow` | `BOOKING_NOT_PERSISTED` | 🐞 покрыт как известный баг |
| REQ-BOOK-02 | Бронирование несуществующей машины — 404. | `test_api_car.py::test_api_book_nonexistent_car` | `BOOKING_UNKNOWN_CAR_200` | 🐞 покрыт как известный баг |
| REQ-BOOK-03 | Бронирование требует авторизации. | `test_api_car.py::test_api_book_without_token` | — | ✅ покрыт |

### 1.5 Города (CITY)

| ID | Формулировка | Тесты | Реестр | Статус |
|---|---|---|---|---|
| REQ-CITY-01 | `/v1/cars/cities` доступен без авторизации и возвращает список `{city, lat, lng}`. | `test_dictionaries.py::test_api_cities_list` | — | ✅ покрыт |

### 1.6 Безопасность и протокол (SEC)

| ID | Формулировка | Тесты | Реестр | Статус |
|---|---|---|---|---|
| REQ-SEC-01 | Запрос к защищённому эндпоинту без токена — 401. | `test_api_car.py::test_api_add_car_unauthorized`<br>`test_api_security.py::test_api_security_auth_tokens` — `[empty-401-Пустой токен (Отсутствует заголовок)]` | `NO_AUTH_403` | 🐞 покрыт как известный баг |
| REQ-SEC-02 | Невалидный токен — 401. | `test_api_security.py::test_api_security_auth_tokens` — `[invalid-401-Невалидный токен (Мусорная строка)]`; `[wrong_scheme-401-Неверная схема (Basic вместо Bearer)]` | — | ✅ покрыт |
| REQ-SEC-03 | Текст ошибки не раскрывает детали реализации. | `test_api_security.py::test_api_security_invalid_token_error_text` | `JWT_DETAILS_IN_ERROR` | 🐞 покрыт как известный баг |
| REQ-SEC-04 | Неподдерживаемый `Content-Type` — 415, а не ошибка сервера. | `test_api_security.py::test_api_security_unsupported_media_type` | `WRONG_CONTENT_TYPE_500` | 🐞 покрыт как известный баг |
| REQ-SEC-05 | Неизвестный путь — 404; неподдерживаемый метод — 405. | `test_api_security.py::test_api_security_method_not_allowed` | `UNKNOWN_ROUTE_403` | 🐞 покрыт как известный баг |
| REQ-SEC-06 | Выход из системы делает токен недействительным. | `test_playwright_session.py::test_pw_token_rejected_after_logout` | `LOGOUT_TOKEN_STILL_VALID` | 🐞 покрыт как известный баг |
| REQ-SEC-07 | Размер принимаемых и отдаваемых данных ограничен. | — | — | ⚪ исключение: вредит общему бэкенду |

### 2.1 Регистрация (UI-REG)

| ID | Формулировка | Тесты | Реестр | Статус |
|---|---|---|---|---|
| REQ-UI-REG-01 | Поля проверяются до отправки: Name, Last name, Email (формат), Password (не короче 6, буква и цифра), согласие с условиями. | `test_registration.py::test_registration_negative_fields`<br>`test_registration.py::test_registration_without_check_box` | — | ✅ покрыт |
| REQ-UI-REG-02 | После успешной регистрации — окно «Registered» / «You are logged in success»; пользователь залогинен. | `test_registration.py::test_registration_success` | — | ✅ покрыт |
| REQ-UI-REG-03 | При ответе 400 окно «Registration failed» показывает текст ошибки сервера. | `test_registration.py::test_registration_existing_user`<br>`test_registration.py::test_registration_password_rejected_by_api` | `PASSWORD_RULES_MISMATCH` | 🐞 покрыт как известный баг |
| REQ-UI-REG-04 | Гость видит в навигации ссылку «Sign up»; она ведёт на форму регистрации `/register`. | `test_registration.py::test_navigation_to_registration` | — | ✅ покрыт |

### 2.2 Вход (UI-LOGIN)

| ID | Формулировка | Тесты | Реестр | Статус |
|---|---|---|---|---|
| REQ-UI-LOGIN-01 | Email обязателен и проверяется по формату, пароль обязателен; перед отправкой email приводится к нижнему регистру. | `test_login.py::test_login_negative_frontend`<br>`test_playwright_login.py::test_pw_login_negative`<br>`test_playwright_login.py::test_pw_login_sends_email_lowercase` | — | ✅ покрыт |
| REQ-UI-LOGIN-02 | После входа — окно «You are logged in success», в навигации «Log out». | `test_login.py::test_login_success`<br>`test_playwright_login.py::test_pw_login_success` | — | ✅ покрыт |
| REQ-UI-LOGIN-03 | При 401 — окно «Login failed» с текстом «Login or Password incorrect»; при любой другой ошибке — «Login failed. Try again». | `test_login.py::test_login_negative_backend`<br>`test_playwright_login.py::test_pw_login_other_error_text` | `LOGIN_ERROR_TEXT_HARDCODED` | 🐞 покрыт как известный баг |

### 2.3 Добавление машины (UI-CAR)

| ID | Формулировка | Тесты | Реестр | Статус |
|---|---|---|---|---|
| REQ-UI-CAR-01 | Поля, отмеченные `*`, проверяются до отправки: City, Make, Model, Year, Fuel, Seats (≥ 1), Car class, Car registration number, Price (≥ 1). | `test_car_form_validation.py::test_car_form_required_field`<br>`test_car_form_validation.py::test_car_form_city_required` | `CAR_FORM_CITY_NOT_VALIDATED` | 🐞 покрыт как известный баг |
| REQ-UI-CAR-02 | Успешная отправка — «Car submitted successfully» и очистка формы; ошибка — «Failed to submit car». | `test_add_car.py::test_add_car_success`<br>`test_add_car.py::test_add_car_duplicate`<br>`test_playwright_add_car.py::test_real_add_car_success`<br>`test_playwright_add_car.py::test_pw_add_car_duplicate`<br>`test_playwright_car_form.py::test_pw_car_form_success_text` | `CAR_SUCCESS_TEXT_NOT_SHOWN` | 🐞 покрыт как известный баг |
| REQ-UI-CAR-03 | Значение Fuel уходит в API строчными: `petrol`, `diesel`, `hybrid`, `electric`. | `test_playwright_car_form.py::test_pw_car_form_sends_fuel_lowercase` | — | ✅ покрыт |
| REQ-UI-CAR-04 | Фото — ссылкой или файлом; файл отправляется в поле `image` как data URL (base64). | `test_playwright_car_form.py::test_pw_car_form_sends_photo_file_as_data_url`<br>`test_playwright_car_form.py::test_pw_car_form_sends_photo_link` | — | ✅ покрыт |
| REQ-UI-CAR-05 | При ответе 401 на отправку формы машины UI не показывает пользователю текст ошибки из ответа сервера. | `test_playwright_backend_faults.py::test_pw_car_form_401_hides_server_message` | — | ✅ покрыт |

### 2.4 Поиск (UI-SEARCH)

| ID | Формулировка | Тесты | Реестр | Статус |
|---|---|---|---|---|
| REQ-UI-SEARCH-01 | «Yalla!» доступна, только когда заполнены город и обе даты. | `test_search.py::test_search_form_dynamic`<br>`test_search.py::test_search_empty_city_validation` | — | ✅ покрыт |
| REQ-UI-SEARCH-02 | В календаре недоступны дни раньше сегодняшнего и позже «сегодня + 365 дней». | `test_calendar.py::test_calendar_past_navigation_blocked`<br>`test_calendar.py::test_calendar_far_future_blocked` | — | ✅ покрыт |
| REQ-UI-SEARCH-03 | Подсказка города показывает до 8 вариантов из списка фронтенда; город можно ввести вручную. | `test_search.py::test_search_city_suggestions`<br>`test_search.py::test_search_city_typed_manually` | — | ✅ покрыт |
| REQ-UI-SEARCH-04 | Пагинация выдачи — на стороне клиента: `page` и `size` в URL, 10, 20 или 50 карточек на странице. | `test_search.py::test_search_client_pagination` | — | ✅ покрыт |
| REQ-UI-SEARCH-05 | Цена на карточке показывается с одним знаком после запятой. | `test_playwright_mocking.py::test_mock_search_results`<br>`test_search.py::test_search_form_dynamic` | — | ✅ покрыт |
| REQ-UI-SEARCH-06 | Поле дат только для чтения: даты выбираются в календаре, который открывается кликом по полю и закрывается кликом вне календаря. | `test_calendar.py::test_calendar_ui_and_close`<br>`test_search.py::test_search_dates_readonly_protection` | — | ✅ покрыт |
| REQ-UI-SEARCH-07 | Календарь поиска показывает стандартный интерфейс react-date-range: месяцы листаются кнопками со стрелками в пределах `minDate`…`maxDate` (REQ-UI-SEARCH-02), сегодняшний день отмечен (класс `rdrDayToday`). | `test_calendar.py::test_calendar_ui_and_close`<br>`test_calendar.py::test_calendar_month_navigation` | — | ✅ покрыт |

### 2.5 Страница машины (UI-CARPAGE)

| ID | Формулировка | Тесты | Реестр | Статус |
|---|---|---|---|---|
| REQ-UI-CARPAGE-01 | Клик по карточке открывает `/cars/{serial}` с данными машины. | `test_playwright_car_page.py::test_pw_car_card_opens_car_page` | `CAR_PAGE_NOT_LOADED` | 🐞 покрыт как известный баг |
| REQ-UI-CARPAGE-02 | «Rent now!!»: гость попадает на вход с возвратом на страницу машины; залогиненный видит сообщение «Бронирование пока не реализовано в API». | — | — | ⚪ исключение: функциональность недостижима |

### 2.6 Сессия (UI-SESSION)

| ID | Формулировка | Тесты | Реестр | Статус |
|---|---|---|---|---|
| REQ-UI-SESSION-01 | При ответе 401 фронт удаляет `token` и запоминает `postLoginRedirect`. | `test_playwright_backend_faults.py::test_pw_401_on_screen_clears_token`<br>`test_playwright_session.py::test_pw_401_clears_token_and_remembers_redirect` | — | ✅ покрыт |
| REQ-UI-SESSION-02 | «Log out» удаляет токен и переводит на `/search`. | `test_playwright_session.py::test_pw_logout_clears_token_and_opens_search` | — | ✅ покрыт |
| REQ-UI-SESSION-03 | Неудачная попытка входа или регистрации — ответ ошибки или обрыв соединения — не создаёт сессию: в localStorage нет `token`, в навигации нет «Log out». | `test_playwright_backend_faults.py::test_pw_rejected_login_creates_no_session`<br>`test_playwright_backend_faults.py::test_pw_failed_login_creates_no_session`<br>`test_playwright_backend_faults.py::test_pw_failed_registration_creates_no_session` | — | ✅ покрыт |

### 3. Расхождения источников (DISC)

| ID | Формулировка | Тесты | Реестр | Статус |
|---|---|---|---|---|
| DISC-01 | Правила пароля: фронтенд — не короче 6, буква и цифра; Swagger и API — не короче 8, заглавная, строчная, цифра, спецсимвол обязателен; текст ошибки API — спецсимвол «можно» (Can contain). | `test_registration.py::test_registration_password_rejected_by_api` | `PASSWORD_RULES_MISMATCH` | 🐞 покрыт как известный баг |
| DISC-02 | Города: во фронтенде 54, в API 37, общих 22. | `test_dictionaries.py::test_frontend_backend_cities_mapping` | `CITIES_MISMATCH` | 🐞 покрыт как известный баг |
| DISC-03 | Регистр email внутри API: регистрация приводит email к нижнему регистру (повтор с другим регистром — «User already exists»), вход — нет (email с заглавными — 401). | `test_api_auth.py::test_api_login_email_case` | `LOGIN_EMAIL_CASE_SENSITIVE` | 🐞 покрыт как известный баг |
| DISC-04 | Поля формы машины Gear, WD, Doors (и `features` в состоянии формы) отсутствуют в `CarDto`; фронт их собирает и не отправляет. | `test_playwright_car_form.py::test_pw_car_form_sends_gear_wd_doors` | `CAR_FORM_FIELDS_NOT_SENT` | 🐞 покрыт как известный баг |
| DISC-05 | Фронт обращается к эндпоинтам, которых нет ни в Swagger, ни на бэкенде: `GET /v1/cars/{id}`, `GET` и `PUT /v1/user/profile`. | `test_playwright_car_page.py::test_pw_car_page_request_is_documented`<br>`test_playwright_car_page.py::test_pw_profile_page_request_is_documented`<br>`test_playwright_car_page.py::test_pw_profile_save_request_is_documented` | `FRONTEND_CALLS_UNDOCUMENTED_ENDPOINTS` | 🐞 покрыт как известный баг |
| DISC-06 | Бронирование: Swagger описывает эндпоинт, фронт считает его не реализованным («Бронирование пока не реализовано в API»), API отвечает успехом, ничего не сохраняя. | — | — | ⚪ исключение: функциональность недостижима |
| DISC-07 | Границы полей машины: фронт требует Seats ≥ 1 и Price ≥ 1; в Swagger ограничений нет; API принимает 0 и отрицательные значения. | `test_api_car.py::test_api_rejects_car_values_forbidden_by_form`<br>`test_car_form_validation.py::test_car_form_value_below_one` | `CAR_LIMITS_MISMATCH` | 🐞 покрыт как известный баг |
| DISC-08 | Пагинация: фронт передаёт `page` и `size` в поиск; в Swagger параметров нет; API их игнорирует. | `test_api_search.py::test_api_search_page_size` | `SEARCH_PAGINATION_IGNORED` | 🐞 покрыт как известный баг |
| DISC-09 | Страница машины читает поля, которых нет в `CarDto`: `make`, `car_class`, `image_url`, `imageUrl`, `price_per_day`, `engine`, `gear`, `wheels_drive`, `fuel_consumption`, `doors`, `address`, `distance_included`, `description`. | — | — | ⚪ исключение: заблокировано другим дефектом (DISC-05) |

### 4. Наблюдения (OBS)

| ID | Формулировка | Тесты | Реестр | Статус |
|---|---|---|---|---|
| OBS-01 | Поиск чувствителен к регистру города: `tel aviv` — 0 машин. | `test_playwright_search.py::test_pw_search_city_case_insensitive` | `SEARCH_CITY_CASE_SENSITIVE` | 👁 покрыт как наблюдение |
| OBS-02 | Поиск и бронирование принимают прошедшие даты и конец раньше начала. | `test_api_dates.py::test_api_meaningless_dates_rejected` | `INVALID_DATES_ACCEPTED` | 👁 покрыт как наблюдение |
| OBS-03 | API принимает бессмысленные значения машины: `seats` 0, цена 0 и −5, `year` «abc» и «2999», `fuel` «banana». | `test_api_mutations.py::test_api_car_mutations` — `[lambda_mutation-400-Отрицательная цена-False]` | `NONSENSE_CAR_VALUES` | 👁 покрыт как наблюдение |
| OBS-04 | Пустой результат поиска ничем не обозначен: нет сообщения «ничего не найдено». | `test_playwright_search.py::test_pw_empty_search_announced` | `SEARCH_OUTCOME_NOT_SHOWN` | 👁 покрыт как наблюдение |
| OBS-05 | После 401 нет перехода на страницу входа; «Log out» остаётся в навигации, хотя токен удалён. | `test_playwright_backend_faults.py::test_pw_search_401_hides_logout`<br>`test_playwright_session.py::test_pw_401_redirects_to_login`<br>`test_playwright_session.py::test_pw_401_hides_logout` | `STALE_SESSION_UI_AFTER_401` | 👁 покрыт как наблюдение |
| OBS-06 | Форма добавления машины открывается гостю; отправка заканчивается «Failed to submit car». | `test_playwright_ui_observations.py::test_pw_guest_redirected_from_car_form` | `GUEST_OPENS_CAR_FORM` | 👁 покрыт как наблюдение |
| OBS-07 | «Failed to submit car» не объясняет причину: город не поддерживается, пустой город, нет авторизации — текст один. | `test_playwright_ui_observations.py::test_pw_car_submit_error_names_cause` | `CAR_SUBMIT_ERROR_WITHOUT_CAUSE` | 👁 покрыт как наблюдение |
| OBS-08 | Цена на экране округляется: 1234.56 показывается как «1234.6». | `test_playwright_search.py::test_pw_card_price_matches_saved` | `CARD_PRICE_ROUNDED` | 👁 покрыт как наблюдение |
| OBS-09 | После регистрации URL остаётся `/register`. | `test_playwright_ui_observations.py::test_pw_registration_leaves_register_url` | `REGISTER_URL_UNCHANGED` | 👁 покрыт как наблюдение |
| OBS-10 | Кнопка «предыдущий месяц» в календаре доступна, но ничего не делает. | `test_calendar.py::test_calendar_prev_month_disabled_in_current_month` | `PREV_MONTH_BUTTON_ENABLED` | 👁 покрыт как наблюдение |
| OBS-11 | Интерфейс на английском, но страницы машины и профиля показывают русские тексты: «Не удалось загрузить машину», «Загрузка...», «Мой профиль». | `test_playwright_ui_observations.py::test_pw_page_texts_in_english` | `RUSSIAN_TEXTS_IN_ENGLISH_UI` | 👁 покрыт как наблюдение |

## Реестр исключений покрытия

Реестр — `data/coverage_exceptions.py`. Исключения: теста не будет, пока не изменится приложение.
Запланированные: запись убирает тот PR, который добавляет тест. Частично покрытые: тест есть,
в таблице — что из пункта он не проверяет; запись убирает тот PR, который доберёт остальное.

### Исключения

| ID | Категория | Причина |
|---|---|---|
| REQ-SEARCH-03 | заблокировано другим дефектом: REQ-BOOK-01 | Бронирование не сохраняется, bookedPeriods пуст у всех машин системы (Q-API-12): занятую машину для проверки поиска создать нечем |
| REQ-SEC-07 | вредит общему бэкенду | Проверка ограничения размера — это загрузка больших данных на общий бэкенд и выкачивание выдачи крупного города (Tel Aviv — около 18 МБ). Факт зафиксирован исследованием: Q-UI-06, Q-API-02 |
| REQ-UI-CARPAGE-02 | функциональность недостижима | Кнопка «Rent now!!» находится на странице машины, а страница не открывается: «Не удалось загрузить машину» (REQ-UI-CARPAGE-01, Q-UI-02) |
| DISC-06 | функциональность недостижима | Сторона фронтенда — сообщение «Бронирование пока не реализовано в API» — на странице машины, которая не открывается (REQ-UI-CARPAGE-01). Сторону API проверяют REQ-BOOK-01 и REQ-BOOK-02 |
| DISC-09 | заблокировано другим дефектом: DISC-05 | Поля, которые читает страница машины, видны только в ответе GET /v1/cars/{id}, а у этого эндпоинта нет контракта (DISC-05): на бэкенде он отвечает 403, в браузере обрывается (Q-UI-01, Q-UI-19). Подменять ответ несуществующего эндпоинта не будем — его тело пришлось бы выдумать. Согласовано с пользователем |

### Запланировано: PR 6.2 (API)

| ID | Что проверит тест |
|---|---|

### Запланировано: PR 6.3a (UI: перехват запросов и сессия)

| ID | Что проверит тест |
|---|---|

### Запланировано: PR 6.3b (UI: остальное и наблюдения)

| ID | Что проверит тест |
|---|---|

### Покрыто частично

| ID | Что не покрыто | PR |
|---|---|---|
