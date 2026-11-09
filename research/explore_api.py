"""
Исследование фактического поведения API IlCarro (вопросы Q-API-01 … Q-API-12).

Скрипт фиксирует факты: что отправили и что получили. Оценок в нём нет.
Запуск: python research/explore_api.py --run 1
Лог: research/evidence/explore_api_run1.log
"""

import base64
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    MISSING,
    REG,
    FactLog,
    body_json,
    call,
    car_payload,
    cleanup_cars,
    create_car,
    d,
    describe,
    find_my_car,
    load_ui_cities,
    message_type,
    new_email,
    new_serial,
    print_stats,
    register_user,
    run_name,
    short,
)

LOG = FactLog(run_name("explore_api"))
UI_CITIES = load_ui_cities()


# ---------------------------------------------------------------- вспомогательное


def api_cities() -> list:
    data = body_json(call("GET", "/v1/cars/cities")) or {}
    return [c.get("city") for c in data.get("cities", [])]


def pick_shared_city() -> str:
    """Город, который есть и в API, и во фронтенде: берём первый по списку фронтенда."""
    in_api = set(api_cities())
    for city in UI_CITIES:
        if city in in_api:
            return city
    return "Tel Aviv"


def search(city, start, end, params=None, token=None):
    body = {"city": city}
    if start is not None:
        body["startDate"] = start
    if end is not None:
        body["endDate"] = end
    return call("POST", "/v1/cars/search", token=token, json=body, params=params)


def search_serials(city, start, end, params=None) -> list:
    resp = search(city, start, end, params)
    data = body_json(resp)
    return [c.get("serialNumber") for c in (data or {}).get("cars", [])] if isinstance(data, dict) else []


def booked(token, serial):
    car = find_my_car(token, serial)
    return None if car is None else car.get("bookedPeriods")


# ---------------------------------------------------------------- вопросы


def q_api_01_booking_state(city):
    LOG.header("Q-API-01", "Бронирование: ответ, bookedPeriods, поиск на забронированные даты")
    owner, _, tok_owner, _ = register_user()
    booker, _, tok_booker, _ = register_user()
    serial = new_serial()
    resp = create_car(tok_owner, car_payload(city, serial))
    LOG.fact(f"создание машины владельцем (город {city}): {describe(resp)}")
    s, e = d(30), d(34)
    LOG.fact(f"bookedPeriods до бронирования (через /v1/cars/my владельца): {short(booked(tok_owner, serial))}")
    LOG.fact(f"в поиске {city} {s}..{e} до бронирования машина есть: {serial in search_serials(city, s, e)}")

    cases = [
        ("1. другой пользователь, даты " + f"{s}..{e}", tok_booker, serial, s, e),
        ("2. пересекающиеся даты " + f"{d(32)}..{d(37)} (другой пользователь)", tok_booker, serial, d(32), d(37)),
        ("3. прошедшие даты " + f"{d(-10)}..{d(-5)}", tok_booker, serial, d(-10), d(-5)),
        ("4. конец раньше начала " + f"{d(50)}..{d(45)}", tok_booker, serial, d(50), d(45)),
        ("5. несуществующая машина", tok_booker, "RS-NOSUCHCAR", d(60), d(62)),
        ("6. своя машина (владелец) " + f"{d(70)}..{d(72)}", tok_owner, serial, d(70), d(72)),
        ("7. без токена " + f"{d(80)}..{d(82)}", None, serial, d(80), d(82)),
    ]
    for title, token, car_serial, start, end in cases:
        resp = call("POST", f"/v1/cars/{car_serial}/booking", token=token, json={"startDate": start, "endDate": end})
        LOG.fact(f"бронирование, {title}: {describe(resp)}")
        LOG.fact(f"  bookedPeriods после (через /v1/cars/my владельца): {short(booked(tok_owner, serial))}")
        LOG.fact(
            f"  поиск {city} на эти даты {start}..{end}: машина в выдаче = {serial in search_serials(city, start, end)}"
        )
    LOG.fact(f"поиск на даты {s}..{e} после всех попыток: машина в выдаче = {serial in search_serials(city, s, e)}")


def q_api_02_search_and_dates(city):
    LOG.header("Q-API-02", "Поиск и даты, регистр города, параметры page и size")
    owner, _, tok, _ = register_user()
    serial = new_serial()
    LOG.fact(f"создание тестовой машины в {city}: {describe(create_car(tok, car_payload(city, serial)))}")
    scenarios = [
        ("будущие даты", d(10), d(14)),
        ("прошедшие даты", d(-20), d(-15)),
        ("конец раньше начала", d(14), d(10)),
        ("без дат (поля отсутствуют)", None, None),
        ("даты null", "NULL", "NULL"),
    ]
    for title, s, e in scenarios:
        if s == "NULL":
            resp = call("POST", "/v1/cars/search", json={"city": city, "startDate": None, "endDate": None})
        else:
            resp = search(city, s, e)
        data = body_json(resp)
        count = len(data.get("cars", [])) if isinstance(data, dict) and "cars" in data else "-"
        mine = (
            serial in [c.get("serialNumber") for c in data.get("cars", [])]
            if isinstance(data, dict) and "cars" in data
            else "-"
        )
        LOG.fact(
            f"поиск {city}, {title}: HTTP {resp.status_code}; машин в ответе={count}; тестовая машина в ответе={mine}"
        )
    for variant in ("Tel Aviv", "tel aviv", "TEL AVIV"):
        resp = search(variant, d(10), d(14))
        data = body_json(resp) or {}
        LOG.fact(
            f"поиск города '{variant}', будущие даты: HTTP {resp.status_code}; "
            f"машин={len(data.get('cars', [])) if isinstance(data, dict) else '-'}"
        )
    for params in (
        None,
        {"page": 0, "size": 1},
        {"page": 0, "size": 2},
        {"page": 1, "size": 1},
        {"page": 0, "size": 1000},
    ):
        resp = search(city, d(10), d(14), params=params)
        data = body_json(resp) or {}
        LOG.fact(
            f"поиск {city} с query {params}: HTTP {resp.status_code}; "
            f"машин={len(data.get('cars', [])) if isinstance(data, dict) else '-'}"
        )


def q_api_03_cities():
    LOG.header("Q-API-03", "Города API и города фронтенда (UI_CITIES)")
    in_api = api_cities()
    api_set, ui_set = set(in_api), set(UI_CITIES)
    both = sorted(api_set & ui_set)
    only_api = sorted(api_set - ui_set)
    only_ui = sorted(ui_set - api_set)
    LOG.fact(f"городов в API: {len(api_set)}; городов во фронтенде (UI_CITIES): {len(ui_set)}")
    LOG.fact(f"пересечение ({len(both)}): {both}")
    LOG.fact(f"только в API ({len(only_api)}): {only_api}")
    LOG.fact(f"только во фронтенде ({len(only_ui)}): {only_ui}")
    owner, _, tok, _ = register_user()
    for label, pool in (("только во фронтенде", only_ui), ("только в API", only_api)):
        if not pool:
            LOG.fact(f"город '{label}': в списке нет ни одного города")
            continue
        city = pool[0]
        serial = new_serial()
        resp = create_car(tok, car_payload(city, serial))
        LOG.fact(f"создание машины в городе '{city}' ({label}): {describe(resp)}")
        car = find_my_car(tok, serial)
        LOG.fact(
            f"  в /v1/cars/my: city={car.get('city') if car else None}; lat={car.get('lat') if car else None}; "
            f"lng={car.get('lng') if car else None}"
        )
        LOG.fact(f"  поиск по '{city}' на будущие даты находит машину: {serial in search_serials(city, d(10), d(14))}")
        LOG.fact(f"  '{city}' есть в /v1/cars/cities после создания: {city in api_cities()}")


def q_api_04_extra_fields(city):
    LOG.header("Q-API-04", "Лишние поля при создании машины: owner и bookedPeriods")
    creator, _, tok_creator, _ = register_user()
    other, _, tok_other, _ = register_user()
    serial = new_serial()
    payload = car_payload(
        city, serial, owner=other, bookedPeriods=[{"email": "spoof@example.com", "startDate": d(20), "endDate": d(22)}]
    )
    resp = create_car(tok_creator, payload)
    LOG.fact(f"создание с owner=<email второго пользователя> и подложными bookedPeriods: {describe(resp)}")
    car = find_my_car(tok_creator, serial)
    LOG.fact(
        f"в /v1/cars/my создателя: найдена={car is not None}; owner={short(car.get('owner')) if car else None}; "
        f"bookedPeriods={short(car.get('bookedPeriods')) if car else None}"
    )
    car2 = find_my_car(tok_other, serial)
    LOG.fact(f"в /v1/cars/my второго пользователя (указан как owner): найдена={car2 is not None}")
    LOG.fact(
        f"поиск {city} на {d(20)}..{d(22)} (подложный период) находит машину: "
        f"{serial in search_serials(city, d(20), d(22))}"
    )
    LOG.fact(
        f"поиск {city} на {d(40)}..{d(42)} (свободные даты) находит машину: "
        f"{serial in search_serials(city, d(40), d(42))}"
    )


def q_api_05_field_bounds(city):
    LOG.header("Q-API-05", "Границы полей машины")
    owner, _, tok, _ = register_user()
    cases = [
        ("seats=0", {"seats": 0}),
        ("pricePerDay=0", {"pricePerDay": 0}),
        ("pricePerDay=-5", {"pricePerDay": -5}),
        ("year='abc'", {"year": "abc"}),
        ("year='2999'", {"year": "2999"}),
        ("fuel='banana'", {"fuel": "banana"}),
        ("about длиной 600 символов", {"about": "a" * 600}),
        ("model пустой", {"model": ""}),
        ("city пустой", {"city": ""}),
        ("city отсутствует", {"city": MISSING}),
    ]
    for title, over in cases:
        serial = new_serial()
        resp = create_car(tok, car_payload(city, serial, **over))
        stored = find_my_car(tok, serial)
        extra = ""
        if stored:
            extra = (
                f"; сохранено: seats={stored.get('seats')}, pricePerDay={stored.get('pricePerDay')}, "
                f"year={stored.get('year')!r}, "
                f"fuel={stored.get('fuel')!r}, model={stored.get('model')!r}, city={stored.get('city')!r}, "
                f"about(длина)={len(stored.get('about') or '')}"
            )
        LOG.fact(f"{title}: {describe(resp)}; машина в /v1/cars/my={stored is not None}{extra}")


def q_api_06_email_case():
    LOG.header("Q-API-06", "Регистр email при регистрации и входе")
    upper = f"Probe_{new_email('Case')[5:]}".replace("@example.com", "@Example.COM")
    email, pwd, tok, resp = register_user(email=upper)
    LOG.fact(f"регистрация email с заглавными буквами ({email}): {describe(resp)}")
    resp = call("POST", "/v1/user/login/usernamepassword", json={"username": upper, "password": pwd})
    LOG.fact(f"вход тем же email (с заглавными): {describe(resp)}")
    resp = call("POST", "/v1/user/login/usernamepassword", json={"username": upper.lower(), "password": pwd})
    LOG.fact(f"вход email в нижнем регистре: {describe(resp)}")
    REG.label_user(upper.lower())
    resp = call(
        "POST",
        "/v1/user/registration/usernamepassword",
        json={"firstName": "Probe", "lastName": "User", "username": upper.lower(), "password": pwd},
    )
    LOG.fact(f"повторная регистрация того же email в нижнем регистре: {describe(resp)}")


def q_api_07_auth_errors():
    LOG.header("Q-API-07", "Ошибки входа и регистрации")
    email, pwd, _, _ = register_user()
    login = "/v1/user/login/usernamepassword"
    reg = "/v1/user/registration/usernamepassword"
    tests = [
        ("вход: неверный пароль (по шаблону)", "POST", login, {"username": email, "password": "Wrong#2026xx"}),
        ("вход: несуществующий пользователь", "POST", login, {"username": new_email("nouser"), "password": pwd}),
        ("вход: пустое тело {}", "POST", login, {}),
        ("вход: пароль не по шаблону Swagger ('abc123')", "POST", login, {"username": email, "password": "abc123"}),
        ("регистрация: пустое тело {}", "POST", reg, {}),
        (
            "регистрация: повторная с тем же email",
            "POST",
            reg,
            {"firstName": "Probe", "lastName": "User", "username": email, "password": pwd},
        ),
        (
            "регистрация: пароль 'abc123'",
            "POST",
            reg,
            {"firstName": "Probe", "lastName": "User", "username": new_email(), "password": "abc123"},
        ),
        (
            "регистрация: пароль 'Abcdefg1'",
            "POST",
            reg,
            {"firstName": "Probe", "lastName": "User", "username": new_email(), "password": "Abcdefg1"},
        ),
    ]
    for title, method, path, body in tests:
        if "username" in body:
            REG.label_user(body["username"])
        resp = call(method, path, json=body)
        if resp.status_code == 200 and path == reg and body.get("username") != email:
            REG.users_created += 1
        LOG.fact(f"{title}: {describe(resp)}; {message_type(resp)}")
    resp = call("POST", login, data="", headers={"Content-Type": "application/json"})
    LOG.fact(f"вход: совсем пустое тело (0 байт) с Content-Type JSON: {describe(resp)}; {message_type(resp)}")


def q_api_08_routes_not_in_swagger(city):
    LOG.header("Q-API-08", "Маршруты фронтенда, которых нет в Swagger")
    owner, _, tok, _ = register_user()
    serial = new_serial()
    create_car(tok, car_payload(city, serial))
    payload = car_payload(city, serial)
    routes = [
        ("GET", f"/v1/cars/{serial}", None),
        ("GET", "/v1/user/profile", None),
        ("PUT", "/v1/cars", payload),
        ("GET", "/v1/nonexistent", None),
    ]
    for method, path, body in routes:
        for with_token in (True, False):
            resp = call(method, path, token=tok if with_token else None, json=body)
            LOG.fact(f"{method} {path} {'с токеном' if with_token else 'без токена'}: {describe(resp)}")


def q_api_09_auth_schemes(city):
    LOG.header("Q-API-09", "Авторизация: нет токена, мусорный токен, схема Basic")
    owner, pwd, tok, _ = register_user()
    basic = base64.b64encode(f"{owner}:{pwd}".encode()).decode()
    variants = [
        ("без токена", None, "Bearer"),
        ("мусорный токен (Bearer)", "garbage.token.value", "Bearer"),
        ("схема Basic вместо Bearer", basic, "Basic"),
    ]
    REG.extra_masks[basic] = "<basic-credentials>"
    for title, token, scheme in variants:
        resp = call("GET", "/v1/cars/my", token=token, scheme=scheme)
        LOG.fact(f"GET /v1/cars/my, {title}: {describe(resp)}")
        serial = new_serial()
        REG.car_owner_token[serial] = tok  # на случай, если машина всё же создастся — удалим в finally
        resp = call("POST", "/v1/cars", token=token, scheme=scheme, json=car_payload(city, serial))
        created = find_my_car(tok, serial) is not None
        if created:
            REG.cars_created += 1
        LOG.fact(f"POST /v1/cars, {title}: {describe(resp)}; машина появилась у владельца={created}")
        if not created:
            REG.car_owner_token.pop(serial, None)
        resp = call(
            "POST",
            "/v1/cars/RS-NOSUCHCAR/booking",
            token=token,
            scheme=scheme,
            json={"startDate": d(90), "endDate": d(92)},
        )
        LOG.fact(f"POST /v1/cars/RS-NOSUCHCAR/booking, {title}: {describe(resp)}")
        resp = call("DELETE", "/v1/cars/RS-NOSUCHCAR", token=token, scheme=scheme)
        LOG.fact(f"DELETE /v1/cars/RS-NOSUCHCAR, {title}: {describe(resp)}")


def q_api_10_delete(city):
    LOG.header("Q-API-10", "Удаление: чужая, несуществующая, повторное")
    owner, _, tok_owner, _ = register_user()
    stranger, _, tok_stranger, _ = register_user()
    serial = new_serial()
    create_car(tok_owner, car_payload(city, serial))
    resp = call("DELETE", f"/v1/cars/{serial}", token=tok_stranger)
    LOG.fact(f"удаление чужой машины другим пользователем: {describe(resp)}")
    LOG.fact(f"машина осталась у владельца в /v1/cars/my: {find_my_car(tok_owner, serial) is not None}")
    resp = call("DELETE", "/v1/cars/RS-NOSUCHCAR", token=tok_owner)
    LOG.fact(f"удаление несуществующей машины: {describe(resp)}")
    resp = call("DELETE", f"/v1/cars/{serial}", token=tok_owner)
    LOG.fact(f"удаление своей машины (1-й раз): {describe(resp)}")
    if resp.status_code == 200:
        REG.cars_deleted += 1
        REG.car_owner_token.pop(serial, None)
    resp = call("DELETE", f"/v1/cars/{serial}", token=tok_owner)
    LOG.fact(f"повторное удаление своей машины (2-й раз): {describe(resp)}")
    LOG.fact(f"машина есть у владельца в /v1/cars/my после удаления: {find_my_car(tok_owner, serial) is not None}")


def q_api_11_text_plain(city):
    LOG.header("Q-API-11", "Content-Type text/plain при создании машины")
    import json as _json

    owner, _, tok, _ = register_user()
    serial = new_serial()
    payload = car_payload(city, serial)
    REG.car_owner_token[serial] = tok
    resp = call("POST", "/v1/cars", token=tok, data=_json.dumps(payload), headers={"Content-Type": "text/plain"})
    created = find_my_car(tok, serial) is not None
    LOG.fact(
        f"POST /v1/cars с Content-Type text/plain и JSON-текстом: {describe(resp)}; машина появилась у "
        f"владельца={created}"
    )
    if created:
        REG.cars_created += 1
    else:
        REG.car_owner_token.pop(serial, None)


def q_api_12_booked_periods_scan():
    LOG.header("Q-API-12", "Машины с непустым bookedPeriods по всем городам /v1/cars/cities")
    # Поиск не зависит от дат (Q-API-02), поэтому берём одни и те же будущие даты для всех городов.
    # Серийные номера в лог не пишем: чужие машины, к тому же маскирование их всё равно заменит.
    cities = api_cities()
    LOG.fact(f"городов в /v1/cars/cities: {len(cities)}")
    total_cars = total_booked = failed = 0
    for city in cities:
        resp = search(city, d(10), d(14))
        data = body_json(resp)
        if resp.status_code != 200 or not isinstance(data, dict):
            failed += 1
            LOG.fact(f"поиск {city}: HTTP {resp.status_code}; ответ не разобран")
            continue
        cars = data.get("cars", [])
        with_booked = [c for c in cars if c.get("bookedPeriods")]
        total_cars += len(cars)
        total_booked += len(with_booked)
        if with_booked:
            LOG.fact(f"поиск {city}: машин={len(cars)}; с непустым bookedPeriods={len(with_booked)}")
    LOG.fact(
        f"итого по {len(cities) - failed} городам: машин={total_cars}; с непустым "
        f"bookedPeriods={total_booked}; городов с ошибкой поиска={failed}"
    )


# ---------------------------------------------------------------- запуск


def main():
    LOG.line("# Факты: explore_api.py")
    LOG.line(f"API_BASE_URL: {__import__('common').API_BASE_URL}")
    city = None
    try:
        city = pick_shared_city()
        LOG.fact(f"город для проб (есть и в API, и в UI_CITIES): {city}")
        steps = [
            lambda: q_api_01_booking_state(city),
            lambda: q_api_02_search_and_dates(city),
            q_api_03_cities,
            lambda: q_api_04_extra_fields(city),
            lambda: q_api_05_field_bounds(city),
            q_api_06_email_case,
            q_api_07_auth_errors,
            lambda: q_api_08_routes_not_in_swagger(city),
            lambda: q_api_09_auth_schemes(city),
            lambda: q_api_10_delete(city),
            lambda: q_api_11_text_plain(city),
            q_api_12_booked_periods_scan,
        ]
        for step in steps:
            try:
                step()
            except Exception as exc:
                LOG.fact(f"вопрос не завершён: {type(exc).__name__}: {short(str(exc), 200)}")
                traceback.print_exc()
    finally:
        cleanup_cars(LOG)
        print_stats(LOG)


if __name__ == "__main__":
    main()
