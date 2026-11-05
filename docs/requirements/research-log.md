# Лог исследования фактического поведения IlCarro

Здесь записаны **факты**: что отправили и что получили. Оценок нет: они делаются позже, по источникам
более высокого уровня (см. `README.md` в этой папке). Приложение внешнее и общее, поэтому данные
других пользователей (число машин в городах) могут меняться.

- Дата прогонов: 2026-11-05.
- API: https://ilcarro-backend.herokuapp.com, UI: https://icarro-v1.netlify.app.
- Скрипты: `research/explore_api.py` (функции `q_api_NN_*`), `research/explore_ui.py` (функции `q_ui_NN_*`),
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
- Ответ поиска по Tel Aviv весит около 18 МБ (2770 машин), поэтому в UI-скрипте для проб используется город с малым числом машин.

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
- Замечание исследователя: пока поиск игнорирует даты (Q-API-02), связь «бронирование ↔ поиск» на этих данных не проверяется:
  присутствие машины в выдаче на забронированные даты не отличает забронированные даты от свободных.

## Q-API-02 Поиск и даты

**Как проверяли:** `q_api_02_search_and_dates`. `POST /v1/cars/search`, город Tel Aviv, с созданной тестовой машиной.

- Будущие даты, прошедшие даты, конец раньше начала, даты не переданы, даты `null`: во всех пяти случаях HTTP 200, 2770 машин,
  тестовая машина в ответе.
- Регистр города: `Tel Aviv` → 2770 машин; `tel aviv` → 0; `TEL AVIV` → 0 (HTTP 200).
- Абсолютное число машин в Tel Aviv меняется со временем: в моих прогонах получалось 2771 и 2770. Бэкенд общий, машины
  добавляют и удаляют другие пользователи, поэтому числа из этого лога нельзя считать константами.
- Query-параметры `page` и `size` (без параметров; `page=0&size=1`; `page=0&size=2`; `page=1&size=1`; `page=0&size=1000`):
  везде HTTP 200 и 2770 машин.

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

## Статистика создания и удаления данных

| Скрипт | Пользователей создано | Машин создано | Машин удалено |
|---|---|---|---|
| `explore_api.py` (1 прогон) | 14 | 13 | 13 |
| `explore_ui.py` (1 прогон) | 11 | 7 | 7 |

- Эти числа одинаковы в прогонах 1 и 2. После очистки у временных пользователей машин с префиксом `RS-`/`RU-` не осталось.
- Пользователей API удалять не умеет, они остаются в системе.
- Попытки создать машину гостем и с мусорным токеном (Q-UI-13, Q-API-09) завершились ответами 401/403, машины не создались.
