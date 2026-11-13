# Лог исследования фактического поведения IlCarro

Здесь записаны **факты**: что отправили и что получили. Оценок нет: они делаются позже, по источникам
более высокого уровня (см. `README.md` в этой папке). Приложение внешнее и общее, поэтому данные
других пользователей (число машин в городах) могут меняться.

- Дата прогонов: 2026-11-05.
- API: https://ilcarro-backend.herokuapp.com, UI: https://icarro-v1.netlify.app.
- Скрипты: `research/explore_api.py` (функции `q_api_NN_*`), `research/explore_ui.py` (функции `q_ui_NN_*`),
  `research/explore_ui_interception.py` (Q-UI-15 … Q-UI-19, с перехватом запросов), `research/explore_ui_rest.py`
  (Q-UI-20 … Q-UI-26, шаг 6.3b), `research/explore_ui_faults.py` (Q-UI-27 … Q-UI-37, шаг 7a, сбои бэкенда),
  общие функции — `research/common.py`. Описание запуска — `research/README.md`.
- Каждый скрипт запущен дважды (`--run 1`, `--run 2`). Скриншоты лежат в `research/evidence/` (в git не хранятся,
  создаются скриптом; имена указаны в вопросах).
- Только временные пользователи `probe_<uuid>@example.com`, созданные через API (или через форму регистрации UI в Q-UI-07…09).
  Токены заменены на `<hidden>`. Метки `<userN>`, `<carN>` — временные пользователи и машины.
- Формат дат в API: `YYYY-MM-DD`. «Сегодня» на момент прогона: 2026-11-05.

## Различия между прогонами

- Итоговые логи двух прогонов `explore_api.py` совпадают построчно, кроме времени прогона. То же верно для `explore_ui.py`.
- В более раннем варианте тех же скриптов (до исправления маскирования серийных номеров, логи заменены повторным
  запуском) число машин в Tel Aviv в двух прогонах API было разным: 2771 и 2770. Причина не установлена. В это время
  параллельно выполнялись пробные запуски, которые создавали и удаляли машины в Tel Aviv.
- Повторный запуск после правки маскирования (прогоны 14:34–14:40): итоговые логи прогонов 1 и 2 снова совпадают построчно, кроме времени. От предыдущих прогонов отличается одна строка: в ответе регистрации с пустым телом (Q-API-07) ключи объекта `message` пришли в другом порядке (раньше `lastName, firstName, password, username`, теперь `firstName, lastName, password, username`). Набор ключей и тексты те же.
- Число машин в Tel Aviv в этих прогонах: 2770 (и в прогоне 1, и в прогоне 2).
- Прогоны после добавления Q-API-12 (2026-11-05, 15:59 и 16:03): итоговые логи снова совпадают построчно, кроме времени и порядка ключей `message` в ответе регистрации с пустым телом (Q-API-07), как и раньше.
- Ответ поиска по Tel Aviv весит около 18 МБ (подробности — Q-API-02), поэтому в UI-скрипте для проб используется город с малым числом машин.

## Q-API-01 Бронирование

**Как проверяли:** `explore_api.py`, `q_api_01_booking_state`. Владелец создал машину в Tel Aviv, другой пользователь бронировал.
После каждой попытки смотрели `bookedPeriods` машины через `GET /v1/cars/my` владельца и искали машину поиском на те же даты.

| Попытка | Ответ | bookedPeriods после |
|---|---|---|
| 1. Другой пользователь, 2026-12-05..2026-12-09 | HTTP 200, `{"message":"Car booked successfully! We will contact you soon"}` | `[]` |
| 2. Пересекающиеся даты 2026-12-07..2026-12-12 | HTTP 200, то же сообщение | `[]` |
| 3. Прошедшие даты 2026-10-26..2026-10-31 | HTTP 200, то же сообщение | `[]` |
| 4. Конец раньше начала 2026-12-25..2026-12-20 | HTTP 200, то же сообщение | `[]` |
| 5. Несуществующая машина `RS-NOSUCHCAR` | HTTP 200, то же сообщение | `[]` |
| 6. Владелец бронирует свою машину | HTTP 200, то же сообщение | `[]` |
| 7. Без токена | HTTP 403, тело пустое, `Content-Type` отсутствует | `[]` |

- До бронирования `bookedPeriods` = `[]`. После всех попыток `bookedPeriods` у машины = `[]`.
- Во всех случаях поиск Tel Aviv на те же даты возвращает машину в выдаче (в том числе на даты, на которые бронирование принято).
- Пока бронирование не сохраняется (bookedPeriods после всех попыток = []) и ни у одной машины в системе bookedPeriods не заполнен (Q-API-12), связь „бронирование ↔ поиск" на этих данных не проверяется.

## Q-API-02 Поиск и даты

**Как проверяли:** `q_api_02_search_and_dates`. `POST /v1/cars/search`, город Tel Aviv, с созданной тестовой машиной.

- Будущие даты, прошедшие даты, конец раньше начала, даты не переданы, даты `null`: во всех пяти случаях HTTP 200, 2770 машин,
  тестовая машина в ответе.
- Регистр города: `Tel Aviv` → 2770 машин; `tel aviv` → 0; `TEL AVIV` → 0 (HTTP 200).
- Абсолютное число машин в Tel Aviv меняется со временем: в моих прогонах получалось 2771 и 2770. Бэкенд общий, машины
  добавляют и удаляют другие пользователи, поэтому числа из этого лога нельзя считать константами.
- Query-параметры `page` и `size` (без параметров; `page=0&size=1`; `page=0&size=2`; `page=1&size=1`; `page=0&size=1000`):
  везде HTTP 200 и 2770 машин.
- Все запросы поиска в `explore_api.py` (Q-API-01…04, Q-API-12) выполнялись без токена: функция `search` вызывается без параметра `token`,
  а прямой вызов с `null`-датами не задаёт заголовок `Authorization`. Поиск возвращал HTTP 200 (в Q-API-02 — для всех описанных случаев).
- Размер ответа поиска по Tel Aviv: около 18 МБ. Разовое измерение вне скрипта (2026-11-05, `requests`, тело `{"city":"Tel Aviv"}`):
  HTTP 200, 18 173 017 байт, 2768 машин в ответе. В скрипт размер не записывается.

## Q-API-03 Города

**Как проверяли:** `q_api_03_cities`. `GET /v1/cars/cities` против `UI_CITIES` из `data/data_generator.py`.

- В API 37 городов, во фронтенде (`UI_CITIES`) 54.
- Пересечение (22): Ashdod, Ashkelon, Bat Yam, Bnei Brak, Dimona, Eilat, Givatayim, Hadera, Haifa, Herzliya, Holon, Jerusalem,
  Kfar Saba, Nazareth, Netanya, Petah Tikva, Ramat Gan, Rehovot, Rishon LeZion, Sderot, Tel Aviv, Tiberias.
- Только в API (15): Beer Sheva, Hod HaSharon, Modiin, Qiryat Ata, Qiryat Bialik, Qiryat Gat, Qiryat Malakhi, Qiryat Motzkin,
  Qiryat Ono, Qiryat Shemona, Qiryat Tivon, Qiryat Yam, Qiryat Ye'arim, Qiryat Yovel, Raanana.
- Только во фронтенде (32): Acre, Afula, Arad, Beersheba, Beit Shemesh, Carmiel, Kiryat Ata, Kiryat Bialik, Kiryat Gat,
  Kiryat Motzkin, Kiryat Ono, Kiryat Shmona, Kiryat Yam, Lod, Ma'alot-Tarshiha, Migdal HaEmek, Modi'in-Maccabim-Re'ut, Nahariya,
  Nes Ziona, Ofakim, Or Yehuda, Ra'anana, Ramla, Rosh HaAyin, Safed, Sakhnin, Tamra, Tayibe, Tira, Umm al-Fahm, Yavne, Yeruham.
- Машина в городе `Acre` (только фронтенд): HTTP 400, `{"timestamp":…,"status":400,"error":"Bad Request","message":"City Acre is not supported","path":"/v1/cars"}`.
  В `/v1/cars/my` машины нет, `Acre` в `/v1/cars/cities` не появился, поиск по `Acre` её не находит.
- Машина в городе `Beer Sheva` (только API): HTTP 200. В `/v1/cars/my`: `city="Beer Sheva"`, `lat=31.252`, `lng=34.7916`.
  Поиск по `Beer Sheva` её находит, город есть в `/v1/cars/cities`.

## Q-API-04 Лишние поля при создании машины

**Как проверяли:** `q_api_04_extra_fields`. В теле создания: `owner` = email второго пользователя и
`bookedPeriods` = `[{email: spoof@example.com, startDate, endDate}]`.

- HTTP 200, `{"message":"Car added successfully"}`.
- В `/v1/cars/my` создателя: машина найдена; `owner` = email создателя (не второго пользователя); `bookedPeriods` = `[]`.
- В `/v1/cars/my` второго пользователя (тот, кого указали в `owner`): машины нет.
- Поиск Tel Aviv на даты «подложного» периода и на свободные даты находит машину в обоих случаях.

## Q-API-05 Границы полей машины

**Как проверяли:** `q_api_05_field_bounds`. Для каждого случая — создание, затем чтение через `/v1/cars/my`.

| Случай | Ответ | Что сохранено |
|---|---|---|
| `seats` = 0 | HTTP 200 | `seats=0` |
| `pricePerDay` = 0 | HTTP 200 | `0.0` |
| `pricePerDay` = -5 | HTTP 200 | `-5.0` |
| `year` = "abc" | HTTP 200 | `'abc'` |
| `year` = "2999" | HTTP 200 | `'2999'` |
| `fuel` = "banana" | HTTP 200 | `'banana'` |
| `about` длиной 600 символов | HTTP 200 | длина 600 |
| `model` = "" | HTTP 400, `message`: `{"model":"must not be blank"}` | машины нет |
| `city` = "" | HTTP 400, `message`: `{"city":"must not be blank"}` | машины нет |
| `city` отсутствует | HTTP 400, `message`: `{"city":"must not be blank"}` | машины нет |

## Q-API-06 Регистр email

**Как проверяли:** `q_api_06_email_case`.

- Регистрация `Probe_…@Example.COM` (заглавные буквы): HTTP 200, `accessToken`.
- Вход тем же email (с заглавными): HTTP 401, `message`: `"Login or Password incorrect"`.
- Вход email в нижнем регистре: HTTP 200, `accessToken`.
- Повторная регистрация того же email в нижнем регистре: HTTP 400, `message`: `"User already exists"`.

## Q-API-07 Ошибки входа и регистрации

**Как проверяли:** `q_api_07_auth_errors`. Формат тела ошибки: `timestamp`, `status`, `error`, `message`, `path`.

| Запрос | Статус | `message` |
|---|---|---|
| Вход: неверный пароль (по шаблону) | 401 | строка `"Login or Password incorrect"` |
| Вход: несуществующий пользователь | 401 | строка, то же |
| Вход: `{}` | 401 | строка, то же |
| Вход: пароль `abc123` | 401 | строка, то же |
| Вход: 0 байт при `Content-Type: application/json` | 400 | строка `"Wrong format Credential Object"` |
| Регистрация: `{}` | 400 | **объект**: `lastName`, `firstName`, `password`, `username` → `"must not be blank"` |
| Регистрация: повтор того же email | 400 | строка `"User already exists"` |
| Регистрация: пароль `abc123` | 400 | **объект**: `{"password":" At least 8 characters; Must contain at least 1 uppercase letter, 1 lowercase letter, and 1 number; Can contain special characters [@$#^&*!]"}` |
| Регистрация: пароль `Abcdefg1` | 400 | объект, тот же текст про пароль |

## Q-API-08 Маршруты фронтенда, которых нет в Swagger

**Как проверяли:** `q_api_08_routes_not_in_swagger`; каждый маршрут — с токеном и без.

- `GET /v1/cars/{serial}` (существующая машина), `GET /v1/user/profile`, `PUT /v1/cars`, `GET /v1/nonexistent`:
  во всех восьми комбинациях HTTP 403, тело пустое, заголовка `Content-Type` нет.

## Q-API-09 Авторизация

**Как проверяли:** `q_api_09_auth_schemes`. Запросы: `GET /v1/cars/my`, `POST /v1/cars`, `POST /v1/cars/RS-NOSUCHCAR/booking`,
`DELETE /v1/cars/RS-NOSUCHCAR`.

- Без токена: везде HTTP 403, тело пустое, `Content-Type` нет. `POST /v1/cars` без токена машину не создал.
- Мусорный токен (`Bearer garbage.token.value`): везде HTTP 401, JSON; `message` = `"Malformed JWT JSON: …"` (за текстом следуют нечитаемые символы).
- Схема `Basic` вместо `Bearer`: везде HTTP 401, JSON; `message` = `"JWT strings must contain exactly 2 period characters. Found: 0"`.
- `POST /v1/cars` с мусорным токеном и со схемой `Basic` машину не создал.

## Q-API-10 Удаление

**Как проверяли:** `q_api_10_delete`.

- Удаление чужой машины другим пользователем: HTTP 400, `message`: `"Car with serial number <serial> not found"`. Машина осталась у владельца.
- Удаление несуществующей машины: HTTP 400, то же сообщение с серийным номером.
- Удаление своей машины: HTTP 200, `{"message":"Car deleted successfully"}`.
- Повторное удаление своей машины: HTTP 400, `"Car with serial number <serial> not found"`. В `/v1/cars/my` машины нет.

## Q-API-11 Content-Type text/plain

**Как проверяли:** `q_api_11_text_plain`. `POST /v1/cars` с телом-JSON-текстом и `Content-Type: text/plain`.

- HTTP 500, `{"status":500,"error":"Internal Server Error","message":"Content type 'text/plain;charset=UTF-8' not supported","path":"/v1/cars"}`.
- Машины у владельца нет.

## Q-API-12 Машины с непустым bookedPeriods

**Как проверяли:** `q_api_12_booked_periods_scan`. Для каждого города из `GET /v1/cars/cities` — `POST /v1/cars/search` без токена
(даты 2026-11-15..2026-11-19; в Q-API-02 при любых датах число машин в ответе одно и то же); в ответе считали машины с непустым `bookedPeriods`.

- Городов в `/v1/cars/cities`: 37. Поиск во всех 37 вернул HTTP 200.
- Машин в ответах всего: 13305; с непустым `bookedPeriods`: 0. Ни в одном городе таких машин нет.
- Число машин в системе меняется со временем (бэкенд общий), поэтому 13305 — значение на момент прогона.

## Пробы шага 6.2 (Q-API-13 … Q-API-17)

Добавлены 2026-11-11 для пунктов, по которым факта в логе не было. Запуск один:
`python research/explore_api.py --run 62 --only Q-API-13,Q-API-14,Q-API-15,Q-API-16,Q-API-17`
(лог — `research/evidence/explore_api_run62.log`). Город для машин — Tel Aviv (первый общий город
фронтенда и API), для поиска — Sderot. Создано: пользователей 3, машин 1, удалено 1.

## Q-API-13 Повтор serialNumber

**Как проверяли:** `q_api_13_duplicate_serial`. Владелец создал машину, затем `POST /v1/cars` с тем же `serialNumber`
(другая `model`) отправили тот же владелец и другой пользователь.

- Создание владельцем: HTTP 200, `{"message":"Car added successfully"}`.
- Повтор тем же владельцем: HTTP 400, `message`: `"Car with serial number <car1> already exists"`.
- Повтор другим пользователем: HTTP 400, то же сообщение.
- После обоих повторов: машина в `/v1/cars/my` владельца, `model='ProbeModel'` (исходная); у другого пользователя машины нет.

## Q-API-14 Поиск по городу с малым числом машин

**Как проверяли:** `q_api_14_search_small_city`. `POST /v1/cars/search` без токена, город Sderot, будущие даты.

- Без query-параметров: HTTP 200, 14 машин; значения `city` в выдаче — только `Sderot`.
- `page=0&size=1`: HTTP 200, 14 машин. `page=1&size=1`: HTTP 200, 14 машин.

## Q-API-15 Список городов

**Как проверяли:** `q_api_15_cities_shape`. `GET /v1/cars/cities` без токена.

- HTTP 200, `Content-Type: application/json`; ключ верхнего уровня — только `cities`.
- Элементов 37; у всех ровно ключи `city`, `lat`, `lng`; типы: `city` — строка, `lat` и `lng` — числа с дробной частью.
- Первый элемент: `{"city": "Beer Sheva", "lat": 31.252, "lng": 34.7916}`.

## Q-API-16 Регистрация: поля по одному и правила пароля

**Как проверяли:** `q_api_16_registration_fields`. Каждый запрос — с новым email; остальные поля корректные.

| Случай | Статус | `message` |
|---|---|---|
| `username` отсутствует / `""` | 400 | объект `{"username":"must not be blank"}` |
| `password` отсутствует | 400 | объект `{"password":"must not be blank"}` |
| `password` = `""` | 400 | поля `message` в теле нет |
| `firstName` отсутствует / `""` | 400 | объект `{"firstName":"must not be blank"}` |
| `lastName` отсутствует / `""` | 400 | объект `{"lastName":"must not be blank"}` |
| пароль 7 символов `Ab1@xyz` | 400 | объект, текст про пароль, как в Q-API-07 |
| без цифры `Abcdefg@` | 400 | то же |
| без заглавной `abcdef1@` | 400 | то же |
| без строчной `ABCDEF1@` | 400 | то же |
| без спецсимвола `Abcdefg1` | 400 | то же |

- Ни один запрос не создал пользователя (ответов 200 нет).

## Q-API-17 Обязательные поля CarDto по одному

**Как проверяли:** `q_api_17_car_required_fields`. Для каждого из девяти полей `CarDto.required` — два запроса:
поле отсутствует; поле пустое (`""` для строк, `null` для `seats` и `pricePerDay`). После каждого — чтение `/v1/cars/my`.

- Все 18 запросов: HTTP 400, `message` — объект с именем поля: `"must not be blank"` для строковых полей
  (`serialNumber`, `manufacture`, `model`, `year`, `fuel`, `carClass`, `city`), `"must not be null"` для `seats` и `pricePerDay`.
- Ни одна машина не сохранилась: машин у пользователя до проб 0, после — 0.

## Q-UI-01 Страница машины

**Как проверяли:** `explore_ui.py`, `q_ui_01_car_page`. Машина создана через API в городе Sderot (в выдаче 13 машин). Поиск в UI: город из списка, даты в календаре.

- На первой странице выдачи (`size=10` в URL) 10 карточек, нашей среди них нет. При том же URL с `size=500` карточек 13, наша есть.
- Клик по карточке: URL `/cars/<serial>`. На экране: «Не удалось загрузить машину». Запрос `GET /v1/cars/<serial>` оборван браузером (`net::ERR_FAILED`), ответа со статусом нет.
- Прямой URL `/cars/<serial>`: тот же текст «Не удалось загрузить машину»; запрос `GET /v1/cars/<serial>` оборван (`net::ERR_FAILED`).
- Для сравнения: тот же запрос через `requests` возвращает HTTP 403 с пустым телом (Q-API-08).
- Скриншоты: `q_ui_01_card_click.png`, `q_ui_01_direct_url.png`.

## Q-UI-02 «Rent now!!»

**Как проверяли:** `q_ui_02_rent_now`. Гость и залогиненный пользователь открывают страницу машины.

- Вопрос закрыт: кнопка недостижима, потому что страница машины не открывается (Q-UI-01). В обоих случаях (гость, залогиненный)
  на экране «Не удалось загрузить машину», элементов с текстом «Rent now» на странице нет (0). Клик по кнопке выполнить нельзя,
  поэтому диалогов, URL после клика и `postLoginRedirect` для этой кнопки нет.
- Залогиненный: в навигации есть «Log out».
- Попутно: ключ `postLoginRedirect` наблюдался в Q-UI-13 (значение `/let-car-work`).
- Скриншоты: `q_ui_02_guest_no_button.png`, `q_ui_02_logged_no_button.png`.

## Q-UI-03 Добавление машины в городе, которого нет в API

**Как проверяли:** `q_ui_03_ui_only_city`; город Beersheba, залогиненный временный пользователь.

- Город выбирается из списка. После «Submit»: блок `div.error[role=alert]` с текстом «Failed to submit car».
- Запрос: `POST /v1/cars`, `city="Beersheba"`; ответ HTTP 400, `message`: `"City Beersheba is not supported"`. Машины у владельца нет.
- Скриншот: `q_ui_03_ui_only_city.png`.

## Q-UI-04 Форма без города

**Как проверяли:** `q_ui_04_no_city`.

- Кнопка Submit доступна (`enabled=True`, атрибута `disabled` нет).
- После клика: запрос `POST /v1/cars` с `"city": ""`; ответ HTTP 400, `message`: `{"city":"must not be blank"}`. На экране текст «Failed to submit car». Машины нет.
- Скриншот: `q_ui_04_no_city.png`.

## Q-UI-05 Поля gear, wheelsDrive, doors; значение fuel

**Как проверяли:** `q_ui_05_extra_fields`. В форме выбраны gear = «Automatic», wheelsDrive = «AWD», doors = 4, fuel = «Petrol».

- Значения в форме: `fuel='petrol'`, `gear='auto'`, `wheelsDrive='AWD'`, `doors='4'`.
- Ключи тела запроса: `about, carClass, city, fuel, image, manufacture, model, pricePerDay, seats, serialNumber, year`.
  Полей `gear`, `wheelsDrive`, `doors` в теле нет.
- `fuel` в запросе: `"petrol"` (строчными буквами). В `/v1/cars/my`: `fuel='petrol'`.
- Ответ HTTP 200, `Car added successfully`.

## Q-UI-06 Фото

**Как проверяли:** `q_ui_06_photo`. Загрузка через `#photo-file`: PNG 1×1 (69 байт) и PNG 600×600 из случайных пикселей (1 080 748 байт).

| Файл | Значение поля `image` в запросе | Ответ | `image` в `/v1/cars/my` |
|---|---|---|---|
| 1×1 | начало `data:image/png;base64,iVBORw0KGgoAAAANSU…`, длина 114 | HTTP 200 | длина 114 |
| ~1 МБ | то же начало, длина 1 441 022 | HTTP 200 | длина 1 441 022 |

- Для сравнения: без фото в запросе `"image": ""`; в `/v1/cars/my` длина 82 (Q-UI-05).

## Q-UI-07 Регистрация с паролем `abc123`, 5 раз

**Как проверяли:** `q_ui_07_weak_password`, каждый раз новый email.

- Во всех пяти попытках кнопка Submit доступна; запрос `POST /v1/user/registration/usernamepassword` → HTTP 400, `message` — объект
  `{"password":" At least 8 characters; Must contain at least 1 uppercase letter, …"}`.
- Текст окна во всех пяти попытках одинаковый: заголовок «Registration failed», текст `"[object Object]"`, кнопка «OK».
- Инлайн-ошибок (`.error`) под полями нет.
- Скриншот: `q_ui_07_attempt1.png`.

## Q-UI-08 Повторная регистрация через UI

**Как проверяли:** `q_ui_08_duplicate`.

- Запрос → HTTP 400, `message`: `"User already exists"`. Окно: «Registration failed», `"User already exists"`, «OK».
- Скриншот: `q_ui_08_duplicate.png`.

## Q-UI-09 Заглавные буквы в email: регистрация, выход, вход

**Как проверяли:** `q_ui_09_uppercase_email`; email `Probe_…@Example.COM`.

- Регистрация: запрос с `username`, как введён (с заглавными); HTTP 200. Окно: «Registered», «You are logged in success», «OK».
  В localStorage: `token`, `tokenType=Bearer`. После закрытия окна URL `/register`, в навигации «Log out».
- После «Log out»: кнопки нет, в localStorage остался `tokenType=Bearer` (ключа `token` нет).
- Вход тем же email, введённым с заглавными: в запросе `username` **в нижнем регистре**; HTTP 200. Окно «You are logged in success», появилась кнопка «Log out».
- Скриншот: `q_ui_09_login_after_upper.png`.

## Q-UI-10 Окно ошибки логина при подменённых ответах

**Как проверяли:** `q_ui_10_login_failures`, `page.route` на `POST /v1/user/login/usernamepassword`. Тела подмены написаны скриптом и не принадлежат приложению.

| Подмена | Окно на экране |
|---|---|
| 500, JSON `{"status":500,"error":"Internal Server Error","message":"mocked server error"}` | «Login failed» / `"Login or Password incorrect"` / «OK» |
| 400, JSON, `message` — строка `"mocked bad request"` | то же |
| 400, JSON, `message` — объект `{"password":"mocked field error"}` (дополнительный случай) | то же |
| Запрос оборван (`route.abort`, `net::ERR_FAILED`) | то же |

- Во всех четырёх случаях «Log out» не появился, в localStorage только `tokenType=Bearer`.
- Скриншоты: `q_ui_10_case1.png` … `q_ui_10_case4.png`.

## Q-UI-11 Календарь поиска

**Как проверяли:** `q_ui_11_calendar`, страница `/search`, поле «Dates».

- При открытии: «November 2026». Ячеек дня 35; с классом `rdrDayDisabled` — 4 (дни 1, 2, 3, 4); с `rdrDayPassive` — 5.
- Кнопка «предыдущий месяц» есть, атрибута `disabled` нет. После клика месяц остаётся «November 2026»; недоступных дней по-прежнему 4.
- Клик по 1-му числу текущего месяца (раньше сегодняшнего 5-го): значение поля дат остаётся пустым.
- Листание вперёд 13 раз кнопкой «следующий месяц»: на +11 мес. — «October 2027», доступно 31 день, недоступных нет;
  на +12 и +13 мес. подпись остаётся «November 2027», доступных дней 5, недоступных 25.
  Сегодня + 365 дней = 2027-11-05.
- Ячейка 15 ноября 2027 имеет класс `rdrDay rdrDayDisabled`; клики по 15-му и 17-му числам: значение поля дат пустое.
- Скриншоты: `q_ui_11_after_prev.png`, `q_ui_11_far_future.png`.

## Q-UI-12 Поиск

**Как проверяли:** `q_ui_12_search`.

- Город только из фронтенда (Beersheba), выбран из списка: `POST /v1/cars/search` с `city="Beersheba"` → HTTP 200, 0 машин.
  URL: `/search?city=Beersheba&from=2026-12-03&to=2026-12-06&page=0&size=10`. Карточек 0; отдельного сообщения «ничего не найдено» на экране нет (виден текст главной страницы).
- Город введён вручную без выбора из списка («Sderot»): значение поля = `Sderot`, кнопка «Yalla!» доступна. Запрос ушёл с `city="Sderot"`; HTTP 200, 16 машин; карточек на экране 10.
- Цены для первых трёх карточек Sderot: на экране 887.0 / 567.0 / 820.0; `pricePerDay` в ответе search — 887.0 / 567.0 / 820.0 (совпадают).
- Цены машин, созданных скриптом: отправлено 99.5 → на карточке «99.5», в ответе 99.5; отправлено 250 → «250.0», в ответе 250.0;
  отправлено 1234.56 → на карточке «1234.6», в ответе 1234.56.
- Параметр `size` в URL влияет на число карточек: при `size=10` — 10 карточек, при `size=500` — все.
- Скриншоты: `q_ui_12_ui_only_city.png`, `q_ui_12_manual_city.png`, `q_ui_12_prices.png`.

## Q-UI-13 Сессия

**Как проверяли:** `q_ui_13_session`.

- Мусорный `token` в localStorage (длина 19), перезагрузка, форма машины: страница `/let-car-work` открывается, кнопка «Log out» есть.
  После отправки: `POST /v1/cars` → HTTP 401, `message`: `"JWT strings must contain exactly 2 period characters. Found: 0"`;
  на экране блок с текстом «Failed to submit car»; URL остался `/let-car-work`; «Log out» на месте;
  localStorage после отправки: `postLoginRedirect=/let-car-work`, `tokenType=Bearer` (ключа `token` нет).
- Гость: страница `/let-car-work` открывается, форма на месте, «Log out» нет. После отправки: `POST /v1/cars` → HTTP 403 (пустое тело);
  на экране «Failed to submit car»; URL остался; localStorage: `tokenType=Bearer`.
- Скриншоты: `q_ui_13_garbage_token.png`, `q_ui_13_guest.png`.

## Q-UI-14 Выход

**Как проверяли:** `q_ui_14_logout`.

- После входа в localStorage `token` (длина 216) и `tokenType=Bearer`.
- После «Log out»: URL `/search?page=0&size=10`, кнопки «Log out» нет, в localStorage `tokenType=Bearer` (токена нет).
- `GET /v1/cars/my` с токеном, сохранённым до выхода: HTTP 200, `{"cars":[]}`.

## Пробы шага 6.3a (Q-UI-15 … Q-UI-19)

Добавлены 2026-11-12 для пунктов, по которым факта в логе не было. Запуск один:
`python research/explore_ui_interception.py --run 63` (лог — `research/evidence/explore_ui_interception_run63.log`).
Запросы, которые меняют данные (`POST /v1/cars`, `PUT /v1/user/profile`), перехвачены через `page.route` и до бэкенда
не дошли. Тела подменённых ответов написаны скриптом; для `POST /v1/cars` взят формат настоящего ответа
(`200 {"message":"Car added successfully"}`, Q-UI-05). Город — Sderot. Создано: пользователей 1, машин 0.

## Q-UI-15 Значение fuel для каждого варианта списка

**Как проверяли:** `q_ui_15_fuel_values`. Залогиненный пользователь, форма машины; в списке Fuel по очереди выбраны
Petrol, Diesel, Hybrid, Electric; gear = «Automatic», wheelsDrive = «AWD», doors = 4. `POST /v1/cars` перехвачен, ответ подменён на 200.

| Выбрано в списке | Значение в форме | `fuel` в запросе |
|---|---|---|
| Petrol | `petrol` | `"petrol"` |
| Diesel | `diesel` | `"diesel"` |
| Hybrid | `hybrid` | `"hybrid"` |
| Electric | `electric` | `"electric"` |

- В каждом из четырёх случаев перехвачен ровно один запрос. Ключи тела:
  `about, carClass, city, fuel, image, manufacture, model, pricePerDay, seats, serialNumber, year`.
  Полей `gear`, `wheelsDrive`, `doors`, `features` в теле нет (в форме: `gear='auto'`, `wheelsDrive='AWD'`, `doors='4'`).
- После ответа 200 поле Make пустое, URL остаётся `/let-car-work`; блоков `role=status` и `role=alert` на странице нет —
  текста «Car submitted successfully» на экране нет.

## Q-UI-16 Фото ссылкой и файлом JPEG

**Как проверяли:** `q_ui_16_photo`. `POST /v1/cars` перехвачен, ответ подменён на 200.

- Ссылка: в поле `image` (placeholder `https://...`) введено `https://example.com/probe-car.jpg`; в запросе
  `image` = `"https://example.com/probe-car.jpg"` (как введено).
- Файл: `assets/car.jpg` (174 268 байт) через `#photo-file`; в запросе `image` начинается с
  `data:image/jpeg;base64,/9j/4AAQSkZJRgABA…`, длина 232 383; часть после запятой декодируется из base64 в байты файла.

## Q-UI-17 Подменённый ответ 401 при настоящей сессии

**Как проверяли:** `q_ui_17_substituted_401`. Вход через форму (в localStorage `token` длиной 216), форма машины,
`POST /v1/cars` перехвачен, ответ подменён на 401 (JSON с `message` = `"mocked unauthorized"`).

- Перехвачен один запрос. После ответа: URL остался `/let-car-work`; на экране «Failed to submit car»; «Log out» на месте;
  localStorage: `postLoginRedirect=/let-car-work`, `tokenType=Bearer` (ключа `token` нет).
- После перезагрузки страницы: URL `/let-car-work`, кнопки «Log out» нет, localStorage тот же.

## Q-UI-18 Страница профиля

**Как проверяли:** `q_ui_18_profile`.

- Залогиненный, `/profile`: фронт отправляет `GET /v1/user/profile` с заголовком `Authorization`; запрос оборван браузером
  (`net::ERR_FAILED`), ответа со статусом нет. На экране: «Не удалось загрузить профиль»; URL `/profile`; «Log out» на месте.
  Для сравнения: тот же запрос через `requests` возвращает HTTP 403 с пустым телом (Q-API-08).
- Подменённый `GET /v1/user/profile` → 200 с телом, придуманным скриптом
  (`{"firstName":"Probe","lastName":"User","username":"probe@example.com"}`; настоящего ответа у приложения нет):
  на экране «Мой профиль», поля `firstName`, `lastName`, `username`, кнопка «Сохранить». Клик «Сохранить»: фронт отправляет
  `PUT /v1/user/profile` с тем же телом (перехвачен, до бэкенда не дошёл; ответ подменён на 200); диалог браузера `alert`: «Профиль обновлён».
- Гость, `/profile`: URL становится `/login`; localStorage: `postLoginRedirect=/profile`, `tokenType=Bearer`; запросов к API нет.

## Q-UI-19 Страница чужой машины из выдачи

**Как проверяли:** `q_ui_19_listed_car`. Гость; поиск в UI по Sderot (даты — сегодняшний день), клик по первой карточке.
Машину скрипт не создаёт.

- Поиск: HTTP 200, 14 машин в ответе, 10 карточек на странице (`size=10` в URL).
- Первая карточка: `href="/cars/<serial>"`, машина с таким `serialNumber` есть в ответе поиска.
- После клика: URL `/cars/<serial>`; единственный запрос к API — `GET /v1/cars/<serial>`, оборван браузером (`net::ERR_FAILED`).
  На экране: «Не удалось загрузить машину»; `model` и `manufacture` машины на странице нет.

## Пробы шага 6.3b (Q-API-18, Q-UI-20 … Q-UI-26)

Добавлены 2026-11-12 для пунктов шага 6.3b, по которым факта в логе не было. Запуски:
`python research/explore_api.py --run 63b --only Q-API-18` и `python research/explore_ui_rest.py --run 63b`
(Q-UI-24 и Q-UI-26 повторены отдельно: `--run 63b2 --only Q-UI-24,Q-UI-26` — в первом запуске упал сам скрипт,
обработчик маршрута получал не те аргументы). Логи — `research/evidence/explore_api_run63b.log`,
`research/evidence/explore_ui_rest_run63b.log`, `research/evidence/explore_ui_rest_run63b2.log`.
В UI-пробах запросы, которые меняют данные (`POST /v1/cars`, `POST` регистрации), перехвачены через `page.route`
и до бэкенда не дошли; вход — токеном в localStorage, без запроса входа. Город — Sderot. «Сегодня» — 2026-11-12.

## Q-API-18 Даты поиска и бронирования: своя машина, малый город

**Как проверяли:** `explore_api.py`, `q_api_18_dates_own_car_small_city`. Владелец создал машину в Sderot и бронировал её сам;
поиск — без токена.

| Случай | Поиск Sderot | Бронирование владельцем | bookedPeriods после |
|---|---|---|---|
| Прошедшие даты 2026-11-02..2026-11-06 | HTTP 200, 15 машин, своя в выдаче | HTTP 200, `Car booked successfully! We will contact you soon` | `[]` |
| Конец раньше начала 2026-12-07..2026-12-02 | HTTP 200, 15 машин, своя в выдаче | HTTP 200, то же сообщение | `[]` |
| Будущие даты 2026-12-02..2026-12-07 (для сравнения) | HTTP 200, 15 машин, своя в выдаче | HTTP 200, то же сообщение | `[]` |

- Машина удалена в конце скрипта.

## Q-UI-20 Форма машины: проверка полей до отправки

**Как проверяли:** `explore_ui_rest.py`, `q_ui_20_car_form_validation`. Каждый раз форма заполнена целиком (город выбран
из подсказки), затем одно поле изменено и с него снят фокус.

| Поле и значение | Submit со всеми полями | Submit после изменения | Текст под полем |
|---|---|---|---|
| Make, Model, Year, Seats, Car class, Car registration number, Price — пусто (по одному) | доступна | недоступна | `Required` |
| Fuel — «Select fuel» (значение `""`) | доступна | недоступна | `Required` |
| Seats `0`, Seats `-1` | доступна | недоступна | `seats must be greater than or equal to 1` |
| Price `0`, Price `-5` | доступна | недоступна | `pricePerDay must be greater than or equal to 1` |
| City стёрт после выбора (значение поля `""`) | доступна | **доступна** | блока ошибки нет |

- Пишущих запросов не было (0 оборвано).

## Q-UI-21 Подсказка города на /search

**Как проверяли:** `q_ui_21_city_suggestions`.

| Введено | Вариантов | Варианты |
|---|---|---|
| фокус в пустом поле | 8 | Tel Aviv, Jerusalem, Haifa, Rishon LeZion, Petah Tikva, Ashdod, Netanya, Beersheba |
| `a` | 8 | Tel Aviv, Jerusalem, Haifa, Petah Tikva, Ashdod, Netanya, Beersheba, Bnei Brak |
| `Kiryat`, `kiryat` | 7 | Kiryat Ata, Kiryat Gat, Kiryat Yam, Kiryat Motzkin, Kiryat Bialik, Kiryat Ono, Kiryat Shmona |
| `sderot` | 1 | Sderot |
| `Zzz` | 0 | — |

- Порядок вариантов совпадает с порядком списка городов фронтенда (`UI_CITIES` в `data/data_generator.py`).

## Q-UI-22 Пагинация выдачи

**Как проверяли:** `q_ui_22_pagination`. Поиск Sderot в UI (город из подсказки, даты 2026-11-12 — 2026-11-13).

- Ответ поиска: HTTP 200, 14 машин. URL: `city=Sderot&from=2026-11-12&to=2026-11-13&page=0&size=10`; карточек 10.
- «Rows per page»: варианты `10`, `20`, `50`, выбрано `10`; подпись «1-10 of 14», «1/2».
- Next: `page=1`, `size=10`; карточек 4.
- Rows per page = 20: `page=0&size=20`, карточек 14; = 50: `page=0&size=50`, карточек 14; = 10: `page=0&size=10`, карточек 10.
- Новых запросов поиска при смене страницы и размера скрипт не ждал и не считал.

## Q-UI-23 Поиск городом в другом регистре

**Как проверяли:** `q_ui_23_city_case`. Город введён вручную (без выбора из подсказки), даты выбраны в календаре.

| Введено | `city` в запросе | Ответ | Карточек |
|---|---|---|---|
| `Sderot` (из подсказки) | `"Sderot"` | HTTP 200, 14 машин | 10 |
| `sderot` (вручную) | `"sderot"` | HTTP 200, 0 машин | 0 |
| `SDEROT` (вручную) | `"SDEROT"` | HTTP 200, 0 машин | 0 |

## Q-UI-24 Поиск: пустая выдача и сбой запроса

**Как проверяли:** `q_ui_24_search_failures`. Ответ `POST /v1/cars/search` в двух случаях подменён (500, JSON
`{"status":500,"message":"probe"}`) или оборван (`route.abort`).

| Случай | Карточек | Блоков `role=status` / `role=alert` | Блок результатов |
|---|---|---|---|
| Beersheba, настоящий ответ HTTP 200, 0 машин | 0 | нет | нет |
| Sderot, ответ подменён на 500 | 0 | нет | нет |
| Sderot, запрос оборван | 0 | нет | нет |

- После сбоя кнопка снова «Yalla!», URL с параметрами поиска (`page=0&size=10`).
- Строки со сбоем запроса (500 и обрыв) — точка старта исследования шага 7: с v6 `requirements.md` OBS-04 говорит
  только о пустой выдаче, поведение при сбое поиска ни одним пунктом пока не описано.

## Q-UI-25 URL после регистрации (ответ подменён)

**Как проверяли:** `q_ui_25_register_url`. `POST /v1/user/registration/usernamepassword` перехвачен, ответ подменён на 200
в формате настоящего (`{"accessToken": …}`, Q-API-06; значение токена придумано скриптом).

- Перехвачен один запрос. Окно: «Registered», «You are logged in success», «OK»; при открытом окне путь `/register`.
- После «OK»: путь `/register`; кнопка «Log out» есть; `token` в localStorage есть. То же, что при настоящей регистрации (Q-UI-09).

## Q-UI-26 Текст ошибки отправки машины (ответ подменён)

**Как проверяли:** `q_ui_26_submit_error_text`. Форма заполнена, `POST /v1/cars` перехвачен; тела ошибок 400 — в формате
настоящих ответов (Q-UI-03, Q-UI-04).

| Подменённый ответ | Блоки `role=status` / `role=alert` | Поле Make после ответа |
|---|---|---|
| 400, `message` `"City Beersheba is not supported"` | `Failed to submit car` | заполнено |
| 400, `message` `{"city":"must not be blank"}` | `Failed to submit car` | заполнено |
| 401, `message` `"probe unauthorized"` | `Failed to submit car` | заполнено |
| 200, `{"message":"Car added successfully"}` | нет | пустое |

## Пробы шага 6.4a (Q-API-19 … Q-API-21)

Добавлены 2026-11-13 перед решением о постоянной учётке. Запуск: `python research/probe_session_tokens.py --run 1`,
лог — `research/evidence/probe_session_tokens_run1.log`. Один временный пользователь, зарегистрирован через
`IlCarroAPI.register` (записан в журнал пользователей), машин не создавалось. Токены в лог не выводились: только
статусы ответов и claims.

## Q-API-19 Два входа одним пользователем

**Как проверяли:** проба, `q_api_19_two_logins`. Токен проверяли запросом `GET /v1/cars/my` — в Swagger он защищён
(`Bearer Authentication`) и ничего не меняет.

| Шаг | Результат |
|---|---|
| `GET /v1/cars/my` с токеном регистрации, до входов | HTTP 200, `{"cars":[]}` |
| Вход 1 | HTTP 200, `accessToken` есть |
| `GET /v1/cars/my` с токеном входа 1, до входа 2 | HTTP 200, `{"cars":[]}` |
| Вход 2 | HTTP 200, `accessToken` есть, не совпадает с токеном входа 1 |
| `GET /v1/cars/my` с токеном входа 1, после входа 2 | HTTP 200, `{"cars":[]}` |
| `GET /v1/cars/my` с токеном входа 2 | HTTP 200, `{"cars":[]}` |
| `GET /v1/cars/my` с токеном регистрации, после двух входов | HTTP 200, `{"cars":[]}` |

- Все три токена (регистрации, входа 1, входа 2) приняты одновременно; второй вход первый токен не отозвал.
- Связанный факт: после «Log out» в UI токен, сохранённый до выхода, тоже принимается (Q-UI-14).

## Q-API-20 Срок жизни токена

**Как проверяли:** проба, `q_api_20_token_lifetime`. Payload JWT декодирован без проверки подписи.

| Токен | Claims (кроме времени) | iat (UTC) | exp (UTC) | exp − iat |
|---|---|---|---|---|
| регистрации | `iss` `"Regulait"`, `roles` `["ROLE_USER"]`, `sub` — email пользователя | 2026-11-13 08:17:15 | 2026-11-20 06:57:15 | 600000 с |
| входа 1 | те же | 2026-11-13 08:17:17 | 2026-11-20 06:57:17 | 600000 с |
| входа 2 | те же | 2026-11-13 08:17:18 | 2026-11-20 06:57:18 | 600000 с |

- 600000 с = 6 сут 22 ч 40 мин (≈166,7 ч). Срок одинаков у токена регистрации и токенов входа.
- Принимает ли сервер токен после `exp`, проба не проверяла (ждать 7 суток).

## Q-API-21 Операции, которые меняют состояние пользователя или его данных

**Как проверяли:** по Swagger (`docs/requirements/api-docs.json`), без запросов; список операций печатает
`q_api_21_swagger_operations`.

| Операция | Защита | summary в Swagger | Меняет состояние |
|---|---|---|---|
| `POST /v1/user/registration/usernamepassword` | нет | Registration users by username and password | да: создаёт пользователя |
| `POST /v1/user/login/usernamepassword` | нет | Login users by username and password | выдаёт новый токен; прежние остаются в силе (Q-API-19) |
| `POST /v1/cars` | Bearer | Add new Car | да: машина пользователя |
| `POST /v1/cars/{serialNumber}/booking` | Bearer | Booking car | да: бронь машины |
| `DELETE /v1/cars/{serialNumber}` | Bearer | Delete car by id | да: машина пользователя |
| `POST /v1/cars/search` | нет | Search Car by city and period | нет: поиск, метод POST |
| `GET /v1/cars/my` | Bearer | Get User cars | нет |
| `GET /v1/cars/cities` | нет | Get All Cities | нет |

- Операций профиля, смены пароля и выхода (отзыва токена) в Swagger нет.
- Для учётки «только вход и чтение» допустимы `POST /v1/user/login/usernamepassword`, `GET /v1/cars/my`,
  `GET /v1/cars/cities` и `POST /v1/cars/search`; запрещены `POST /v1/cars`, `POST /v1/cars/{serialNumber}/booking`,
  `DELETE /v1/cars/{serialNumber}` и регистрация.

## Пробы шага 7a (Q-UI-27 … Q-UI-37): сбои бэкенда в UI

Добавлены 2026-11-13. Скрипт — `research/explore_ui_faults.py`, основной запуск `--run 7a`, лог —
`research/evidence/explore_ui_faults_run7a.log` (32 ячейки «экран × сбой», ни одна проба не упала). Код фронта —
бандл `index-CIwwRVbQ.js` и чанки `cars`, `Search`, `Login`, `Register`, `LetCarWork`, `Profile` с
icarro-v1.netlify.app (скачаны 2026-11-13). Браузер — Chromium (Playwright), headless.

- Сбои внедрялись только в запросы, которые экран действительно отправляет: подменённый статус с **пустым телом**,
  обрыв (`route.abort`), задержка 5 и 35 с с последующей отправкой настоящего запроса, на поиске — страница nginx
  «502 Bad Gateway» (`text/html`). Регистрация и `POST /v1/cars` до сервера не доходили (кроме Q-UI-34).
- В каждой ячейке записаны: число срабатываний маршрута сбоя (0 — проба падает), база без сбоя, новый видимый
  текст, кнопка/индикатор и URL, есть ли `token` в localStorage, сохранились ли данные формы, консоль, повтор без
  сбоя, пишущие запросы мимо подмен. У регистрации и формы машины база — форма перед отправкой: успешный ответ на
  запись не подменяется, а настоящая запись не допускается бюджетом следа.
- Поиск и регистрация — гостем; форма машины и профиль — исследовательский пользователь, вход токеном
  в localStorage; вход — через форму этим же пользователем. Город поиска — Sderot, даты — сегодня и завтра.
- Пользователь один (`fault_<uuid>@example.com`), зарегистрирован через `IlCarroAPI.register` в отладочном запуске
  (записан в журнал пользователей); основной запуск входил им через API. Машин скрипт не создавал.

## Q-UI-27 Какие запросы к бэкенду отправляют экраны

**Как проверяли:** по коду (чанки фронта) и сетевому логу базовых ячеек `*.base`. Запросы к бэкенду идут через один
экземпляр axios (`Y.create({baseURL})`); перехватчик ответов при статусе 401 удаляет `token` и записывает
`postLoginRedirect` — это общая ветка для всех экранов.

| Экран | Запрос | В Swagger | Отдельные ветки по статусу в коде | Что делает код | База (сетевой лог) |
|---|---|---|---|---|---|
| Поиск `/search` | `POST /v1/cars/search` (при отправке; при загрузке — если в URL есть город и обе даты) | да | нет; 401 — общий перехватчик | любая ошибка: `console.error(e)`, выдача не меняется, кнопка снова «Yalla!» | HTTP 200, 1,5 с от клика до спокойного экрана |
| Вход `/login` | `POST /v1/user/login/usernamepassword` | да | 401 / всё остальное; 401 — ещё и перехватчик | `authError` = «Login or Password incorrect» или «Login failed. Try again», но окно показывает зашитый текст `"Login or Password incorrect"` в обоих случаях; в консоль не пишет | HTTP 200, 0,6 с |
| Регистрация `/register` | `POST /v1/user/registration/usernamepassword` | да | 400 с непустым `message` / 409 / всё остальное; 401 — перехватчик | 400: окно «Registration failed» с `response.data.message`, а если его нет — с `error.message` axios; 409: `role=alert` «User with that email already exists»; иначе `role=alert` «Registration failed. Try again»; в консоль не пишет | не отправлялся (запись) |
| Форма машины `/let-car-work` | `POST /v1/cars` | да | нет; 401 — перехватчик | любая ошибка: `console.error(e)`, `role=alert` «Failed to submit car» | не отправлялся (запись) |
| Профиль `/profile` (защищённый маршрут) | `GET /v1/user/profile`; `PUT` — только после загрузки профиля | нет (DISC-05) | нет; 401 — перехватчик | любая ошибка: текст «Не удалось загрузить профиль» | сбой `net::ERR_FAILED`: ответ без `Access-Control-Allow-Origin`, браузер блокирует его по CORS (текст в консоли) |
| Навигация, «Log out», `/terms-of-use` | нет | — | — | выход только клиентский (Q-UI-14) | запросов нет |
| Страница машины `/cars/:id` | `GET /v1/cars/{id}` | нет (DISC-05) | — | в шаге 7a не исследовалась | — |

- `GET /v1/cars/cities`, `GET /v1/cars/my`, бронирование и `DELETE` фронт не вызывает: список городов зашит
  в `CityAutocomplete` (54 города).
- Свой таймаут у HTTP-клиента не задан: экземпляр axios создан только с `baseURL`, значит действует умолчание
  axios `timeout: 0` (без ограничения). Отмены запросов (`AbortController`, `CancelToken`) в коде экранов нет.

## Q-UI-28 Поиск: статус ошибки, обрыв, страница посредника

**Как проверяли:** проба, ячейки `search.401`, `search.500`, `search.abort`, `search.proxy502` (гость, новая страница,
поиск формой). Продолжение Q-UI-24: там тело 500 было JSON, здесь пустое; добавлены 401 и 502 (HTML).

| Сбой | Карточек | Окна / `role=alert` / `role=status` | Новый видимый текст | Кнопка | Консоль |
|---|---|---|---|---|---|
| 401, тело пустое | 0 | нет | нет | «Yalla!», доступна | `Failed to load resource … 401`, `AxiosError: Request failed with status code 401` |
| 500, тело пустое | 0 | нет | нет | «Yalla!», доступна | `… 500`, `AxiosError: … status code 500` |
| обрыв | 0 | нет | нет | «Yalla!», доступна | `net::ERR_FAILED`, `AxiosError: Network Error` |
| 502, страница nginx (`text/html`) | 0 | нет | нет | «Yalla!», доступна | `… 502 (Bad Gateway)`, `AxiosError: … status code 502` |

- Во всех четырёх случаях: URL с параметрами поиска, город и даты в форме сохранились, повторный поиск без сбоя —
  HTTP 200, 10 карточек. Текст страницы nginx на экран не попал.
- 401 (гость, токена не было): в localStorage появился `postLoginRedirect` = текущий путь поиска с параметрами;
  перехода на вход нет.

## Q-UI-29 Поиск: сбой после успешного поиска

**Как проверяли:** проба, `search.stale500`. Настоящий поиск (HTTP 200, 10 карточек), затем тот же поиск ещё раз
с ответом 500 (тело пустое), затем повтор без сбоя.

- После ответа 500 на экране те же 10 карточек: видимый текст страницы не изменился ни в одной строке. Сообщений
  нет, кнопка «Yalla!» доступна; в консоли `AxiosError: Request failed with status code 500`.
- По коду (`Search`): при ошибке список машин не сбрасывается (`v(l)` вызывается только при успехе), поэтому
  на экране остаётся выдача прошлого успешного поиска. Поиск с другим городом после успешного проба не проверяла.

## Q-UI-30 Вход: статус ошибки и обрыв

**Как проверяли:** проба, `login.401`, `login.500`, `login.abort`; учётные данные исследовательского пользователя,
запрос подменён и до сервера не дошёл. Повтор Q-UI-10 с пустым телом и ответом 401.

- Во всех трёх случаях — окно «Login failed» / `"Login or Password incorrect"` / «OK». Пока окно открыто, кнопка
  «Y’alla!» недоступна. «Log out» нет, `token` нет, email и пароль в полях сохранились.
- 401: `postLoginRedirect` = `/login` (перехватчик). 500 и обрыв: `postLoginRedirect` нет.
- В консоли только сообщение браузера `Failed to load resource …`; сообщения от кода экрана нет.
- Повтор без сбоя после «OK»: HTTP 200, «Log out» есть, `token` есть.

## Q-UI-31 Регистрация: статусы ошибок и обрыв

**Как проверяли:** проба, `register.400`, `register.409`, `register.401`, `register.500`, `register.abort`; email
фальшивый (`fake_<uuid>@example.com`), запрос перехвачен.

| Подменённый ответ | Что на экране |
|---|---|
| 400, тело пустое | окно «Registration failed» / `"Request failed with status code 400"` / «OK» (текст ошибки axios) |
| 409, тело пустое | `role=alert` «User with that email already exists» |
| 401, тело пустое | `role=alert` «Registration failed. Try again»; `postLoginRedirect` = `/register` |
| 500, тело пустое | `role=alert` «Registration failed. Try again» |
| обрыв | `role=alert` «Registration failed. Try again» |

- Во всех случаях: URL `/register`, «Log out» нет, `token` нет, 4 поля заполнены, согласие отмечено, кнопка доступна.
  Повторная отправка возможна (после «OK» для 400) — второй запрос ушёл и тоже был перехвачен.
- В консоли — только `Failed to load resource …`.

## Q-UI-32 Форма машины: статус ошибки и обрыв

**Как проверяли:** проба, `car.401`, `car.500`, `car.abort`; вход токеном, форма заполнена (город Sderot),
`POST /v1/cars` перехвачен.

- Во всех трёх случаях — `role=alert` «Failed to submit car»; URL `/let-car-work`; 7 полей и город сохранились;
  кнопка «Submit» доступна, повторная отправка ушла (перехвачена). В консоли `AxiosError: Request failed with status
  code …` (`Network Error` при обрыве).
- 401: `token` удалён, `postLoginRedirect` = `/let-car-work`, «Log out» остаётся в навигации (как Q-UI-17).
  500 и обрыв: `token` на месте.

## Q-UI-33 Профиль: статус ошибки, обрыв, задержка

**Как проверяли:** проба, `profile.base`, `profile.401`, `profile.500`, `profile.abort`, `profile.delay5`,
`profile.delay35`; вход токеном. Настоящий запрос профиля всегда заканчивается сбоем (база, DISC-05).

- База, 500, обрыв: текст «Не удалось загрузить профиль», других сообщений нет, `token` на месте.
- 401: тот же текст; `token` удалён, `postLoginRedirect` = `/profile`; страница осталась на `/profile`. После
  перезагрузки — переход на `/login`, запрос профиля не отправлялся (за 30 с).
- Задержка: всё время ожидания на экране «Загрузка...»; после отправки настоящего запроса — «Не удалось загрузить
  профиль».

## Q-UI-34 Настоящий 401 на форме машины: показывает ли UI текст сервера

**Как проверяли:** проба без подмены, `car.real401`. В localStorage мусорный `token` (`probe-garbage-token`, без
точек), форма заполнена без города. `POST /v1/cars` пропущен к серверу только при этих двух условиях.

- Ответ сервера: HTTP 401, `message` = `"JWT strings must contain exactly 2 period characters. Found: 0"`.
- На экране — только «Failed to submit car»; текста сервера на странице нет. В консоли
  `AxiosError: Request failed with status code 401`.
- После ответа: `token` удалён, `postLoginRedirect` = `/let-car-work`, «Log out» в навигации есть, 7 полей сохранились.

## Q-UI-35 Задержка ответа: поиск и вход

**Как проверяли:** проба, `search.delay5`, `search.delay35`, `login.delay5`, `login.delay35`. Запрос удерживался
5 или 35 с, затем уходил на сервер.

| Ячейка | Во время задержки | Фронт прервал запрос сам | От клика до спокойного экрана | После ответа |
|---|---|---|---|---|
| поиск, 5 с | кнопка «Loading...», недоступна; 0 карточек; сообщений нет | нет | 6,6 с | HTTP 200, 10 карточек |
| поиск, 35 с | то же | нет | 36,6 с | HTTP 200, 10 карточек |
| вход, 5 с | кнопка «Loading...», недоступна; «Log out» нет; сообщений нет | нет | 5,8 с | HTTP 200, «You are logged in success», «Log out» есть |
| вход, 35 с | то же | нет | 35,7 с | то же |

- Видимый текст между началом и концом задержки не менялся. В консоли сообщений нет.

## Q-UI-36 Общий перехватчик 401 на всех экранах

**Как проверяли:** сводка проб Q-UI-28 … Q-UI-34 и код перехватчика (`index`).

- После ответа 401 на любом из пяти экранов `token` в localStorage отсутствует, а `postLoginRedirect` равен пути
  текущей страницы (поиск — с параметрами). Ни один экран, кроме самой страницы входа, сразу после 401 на вход
  не переходит.

## Q-UI-37 Тело ошибки: что читает код и что объявлено в Swagger

**Как проверяли:** по коду (чанки фронта) и Swagger (`docs/requirements/api-docs.json`), без запросов.

- Код читает из тела ошибки только `response.data.message` — на экране регистрации при статусе 400. Остальные экраны
  смотрят только на `response.status` (вход — 401; регистрация — 400 и 409; перехватчик — 401) или не смотрят
  на ответ вовсе (поиск, форма машины, профиль).
- Swagger для всех восьми операций объявляет ответы 200, 400, 401 и 500. Схема 400 — `oneOf`:
  `ErrorMessageDtoMapStringString` (`message` — объект строк), `ErrorMessageDtoString` (`message` — строка)
  или произвольный объект; схема 401 и 500 — `ErrorMessageDtoString`. Поля обеих схем: `timestamp`, `status`,
  `error`, `message`, `path`.
- Ответов 409, 403 и 502 в Swagger нет. Код регистрации обрабатывает 409 отдельной веткой; настоящий повтор email
  отвечает 400 `"User already exists"` (Q-API-07); гостю `POST /v1/cars` отвечает 403 (Q-UI-13).

## Шаг 7a: кандидаты в требования

Предложения для решения, не решения. Источник — по иерархии `docs/requirements/README.md`.

| Кандидат | Вид | Предлагаемое основание | Факты |
|---|---|---|---|
| Сбой поиска (4xx/5xx, обрыв, страница посредника) не обозначен на экране: пустая выдача неотличима от «ничего не найдено» | OBS | RFC 9110 §15.6 (5xx — сервер ошибся или не может выполнить запрос); OWASP Error Handling (пользователь получает общее сообщение об ошибке) | Q-UI-24, Q-UI-28 |
| После неудачного повторного поиска на экране остаётся прошлая выдача без пометки | OBS | RFC 9110 §15.6; общие принципы UX (показанное не соответствует последнему запросу) | Q-UI-29; FE: `Search` |
| Регистрация: 409 → «User with that email already exists», 401 / 500 / обрыв → «Registration failed. Try again» | REQ | код фронта (FE: `Register`) | Q-UI-31 |
| Регистрация: 400 без `message` показывает внутренний текст axios «Request failed with status code 400» | OBS | OWASP Error Handling (технические детали не показываются пользователю); FE: `Register` | Q-UI-31 |
| Фронт обрабатывает 409 при регистрации, Swagger 409 не объявляет, сервер на повтор email отвечает 400 | DISC | SW; FE: `Register`; EXP | Q-UI-31, Q-UI-37, Q-API-07 |
| Форма машины при 500 и обрыве — «Failed to submit car», данные формы сохраняются | REQ (расширение REQ-UI-CAR-02 новыми случаями, без нового ID) | код фронта (FE: `LetCarWork`) | Q-UI-32 |
| Текст ошибки сервера (парсер JWT) при 401 не показывается в UI | REQ | OWASP Error Handling; FE: `LetCarWork` | Q-UI-34 |
| После 401 на любом экране токен удаляется (fail securely) | REQ (расширение REQ-UI-SESSION-01 на поиск, вход, регистрацию, профиль) | OWASP fail securely; FE: `index` | Q-UI-36 |
| У HTTP-клиента нет таймаута: при медленном бэкенде «Loading...» без ограничения и без сообщения | OBS | код фронта (axios без `timeout`); прямого пункта RFC/OWASP не нашлось — основание слабое | Q-UI-27, Q-UI-35 |
| Профиль: после 401 страница остаётся на `/profile` с «Не удалось загрузить профиль», на вход ведёт только перезагрузка | OBS (дополнение к OBS-05) | общие принципы UX | Q-UI-33 |
| Вход при 500 и обрыве показывает «Login or Password incorrect» | уже есть: REQ-UI-LOGIN-03 (нарушается) | — | Q-UI-30 подтверждает Q-UI-10 |

## Шаг 7a: что пробы задержки говорят о нестабильном тесте

Тест `test_playwright_session.py::test_pw_token_rejected_after_logout` однажды не дождался «Log out» за 30 с после
входа через форму. Факты проб:

- У фронта нет таймаута запроса (Q-UI-27): ответ входа, пришедший позже 30 с, UI ждёт без ограничения. При задержке
  35 с «Log out» появился через 35,7 с после клика; всё ожидание кнопка показывала «Loading...», других сообщений
  не было (Q-UI-35). Значит, ответ входа дольше 30 с даёт ровно такой симптом.
- Ошибка входа (500, обрыв) симптом даёт другой: через доли секунды окно «Login failed», кнопка «Y’alla!» (Q-UI-30).
- В этом прогоне настоящий вход занял 0,6 с от клика до спокойного экрана (одно измерение). Был ли бэкенд медленным
  в момент того падения, пробы не показывают; версия «медленный бэкенд» остаётся неподтверждённой.
- Различить версии при следующем падении можно по состоянию кнопки входа в момент таймаута: «Loading...» — ответа
  ещё нет; «Y’alla!» с окном «Login failed» — ответ-ошибка.

## Фреймворк: одновременная запись журналов прогона

Вопрос не о приложении, а о самом фреймворке: портятся ли журналы прогона, когда воркеры xdist пишут
в общий файл. Повод — локальный прогон `-n 2` на Windows, в котором итог упал с
`JSONDecodeError: Extra data` при разборе `logs/car_factory.jsonl`.

- Скрипт: `research/race_journal_append.py` (2026-11-12, Windows 11, Python 3.14). 4 процесса стартуют
  одновременно и пишут по 5000 записей в каждый журнал функциями проекта (`CarCleanup._write_journal`,
  `record_registration`) во временный каталог.
- Схема до починки — общий файл на все процессы (`car_factory.jsonl`, `registered_users.jsonl`), режим append:

| Запуск | Испорченных строк | Потеряно записей фабрики машин (из 20000) | Потеряно записей пользователей (из 20000) |
|---|---|---|---|
| 1 | 1 | 1243 | 1145 |
| 2 | 4 | 1471 | 1361 |
| 3 | 1 | 1377 | 1326 |

- Испорченные строки в этих запусках — пустые строки внутри файла. Склеенных записей (`Extra data`) в них
  не было; в прогоне тестов такая ошибка возникла один раз.
- Основная часть ущерба — потерянные записи: целые строки, затёртые записью соседнего процесса. Разбору
  они не мешают, но итог прогона занижают молча.
- Схема после починки — файл на процесс (`car_factory_gw0.jsonl` …, `registered_users_gw0.jsonl` …),
  запись через `utils/run_journal.py`; тот же скрипт, 4 процесса × 5000 записей, 8 файлов:

| Запуск | Испорченных строк | Потеряно записей фабрики машин (из 20000) | Потеряно записей пользователей (из 20000) |
|---|---|---|---|
| 1 | 0 | 0 | 0 |
| 2 | 0 | 0 | 0 |
| 3 | 0 | 0 | 0 |

## Статистика создания и удаления данных

| Скрипт | Пользователей создано | Машин создано | Машин удалено |
|---|---|---|---|
| `explore_api.py` (1 прогон) | 14 | 13 | 13 |
| `explore_api.py --only Q-API-13…17` (2026-11-11) | 3 | 1 | 1 |
| `explore_ui.py` (1 прогон) | 11 | 7 | 7 |
| `explore_ui_interception.py` (2026-11-12) | 1 | 0 | 0 |
| `explore_api.py --only Q-API-18` (2026-11-12) | 1 | 1 | 1 |
| `explore_ui_rest.py` (2026-11-12, два запуска) | 2 | 0 | 0 |
| `probe_session_tokens.py` (2026-11-13) | 1 | 0 | 0 |
| `explore_ui_faults.py` (2026-11-13, отладочные и основной запуски) | 1 | 0 | 0 |

- Числа первых двух скриптов одинаковы в прогонах 1 и 2. После очистки у временных пользователей машин с префиксом `RS-`/`RU-` не осталось.
- Пользователей API удалять не умеет, они остаются в системе.
- Попытки создать машину гостем и с мусорным токеном (Q-UI-13, Q-API-09) завершились ответами 401/403, машины не создались.
- `explore_ui_faults.py`: единственный пишущий запрос, дошедший до сервера, — `POST /v1/cars` с мусорным токеном и пустым
  городом (Q-UI-34), ответ 401. Остальные запросы к серверу — входы, поиск и `GET /v1/user/profile`.
