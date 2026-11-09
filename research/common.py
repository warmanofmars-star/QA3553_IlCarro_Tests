"""
Общие функции для скриптов исследования (explore_api.py, explore_ui.py).

Здесь нет ни оценок, ни проверок: модуль только отправляет запросы и записывает, что получил.
Токены маскируются, email временных пользователей и серийные номера машин заменяются
на стабильные метки (<user1>, <car1>), чтобы логи двух прогонов можно было сравнить через diff.
"""
import ast
import contextlib
import json
import os
import re
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

API_BASE_URL = os.getenv("API_BASE_URL", "https://ilcarro-backend.herokuapp.com")
UI_BASE_URL = os.getenv("UI_BASE_URL", "https://icarro-v1.netlify.app")

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = Path(__file__).resolve().parent / "evidence"
TIMEOUT = 60
BODY_LIMIT = 400

# Пароль, подходящий под шаблон из Swagger. В логи не попадает.
VALID_PASSWORD = "Probe#2026ab"

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]*")
_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:?\d{2}|Z)?")


def load_ui_cities() -> list:
    """Берёт UI_CITIES из data/data_generator.py без импорта модуля (он тянет окружение проекта)."""
    tree = ast.parse((ROOT / "data" / "data_generator.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "UI_CITIES" for t in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError("UI_CITIES не найден в data/data_generator.py")


class Registry:
    """Реестр созданных данных: нужен для чистки, статистики и стабильных меток в логах."""

    def __init__(self):
        self.users = {}  # email -> метка
        self.cars = {}  # serial -> метка
        self.tokens = {}  # email -> токен (никогда не печатается)
        self.car_owner_token = {}  # serial -> токен создателя (для удаления в finally)
        self.cars_created = 0
        self.cars_deleted = 0
        self.users_created = 0
        self.extra_masks = {}

    def label_user(self, email: str) -> str:
        if email not in self.users:
            self.users[email] = f"<user{len(self.users) + 1}>"
        return self.users[email]

    def label_car(self, serial: str) -> str:
        if serial not in self.cars:
            self.cars[serial] = f"<car{len(self.cars) + 1}>"
        return self.cars[serial]


REG = Registry()


def mask(text) -> str:
    """Скрывает токены, метки пользователей/машин, таймстемпы; режет длинные строки."""
    s = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
    s = _JWT_RE.sub("<hidden>", s)
    for token in list(REG.tokens.values()):
        if token:
            s = s.replace(token, "<hidden>")
    for email, label in REG.users.items():
        s = s.replace(email, label)
        s = s.replace(email.lower(), label + "(lower)")
    for serial, label in REG.cars.items():
        s = s.replace(serial, label)
    s = _TS_RE.sub("<ts>", s)
    for src, dst in REG.extra_masks.items():
        s = s.replace(src, dst)
    return s


def short(text, limit: int = BODY_LIMIT) -> str:
    s = mask(text)
    return s if len(s) <= limit else s[:limit] + f"...(+{len(s) - limit} симв.)"


class FactLog:
    """Пишет факты в stdout и в файл research/evidence/<name>.log."""

    def __init__(self, name: str):
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        self.path = EVIDENCE_DIR / f"{name}.log"
        self.path.write_text("", encoding="utf-8")

    def line(self, text: str = ""):
        text = mask(text)  # последняя страховка: токены, email и серийные номера не попадают в лог
        try:
            print(text, flush=True)
        except UnicodeEncodeError:
            print(text.encode("ascii", "replace").decode(), flush=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(text + "\n")

    def header(self, qid: str, title: str):
        self.line("")
        self.line(f"## {qid} {title}")

    def fact(self, text: str):
        self.line(f"- {text}")


def run_name(script: str) -> str:
    """Имя лога: explore_api_run1 — номер прогона берётся из аргумента --run N."""
    run = "1"
    if "--run" in sys.argv:
        run = sys.argv[sys.argv.index("--run") + 1]
    return f"{script}_run{run}"


# ---------------------------------------------------------------- даты

def d(offset_days: int) -> str:
    return (date.today() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- HTTP

def describe(resp) -> str:
    ctype = resp.headers.get("Content-Type", "-")
    return f"HTTP {resp.status_code}; Content-Type={ctype.split(';')[0]}; тело={short(resp.text)}"


def call(method, path, token=None, scheme="Bearer", **kwargs):
    """Один HTTP-запрос. Токен подставляется в Authorization, в логи не попадает."""
    headers = dict(kwargs.pop("headers", {}) or {})
    if token:
        headers["Authorization"] = f"{scheme} {token}"
    return requests.request(method, f"{API_BASE_URL}{path}", headers=headers, timeout=TIMEOUT, **kwargs)


def body_json(resp):
    try:
        return resp.json()
    except ValueError:
        return None


def message_type(resp) -> str:
    """Тип поля message в теле ответа: строка или объект."""
    data = body_json(resp)
    if not isinstance(data, dict):
        return "тело не JSON-объект"
    if "message" not in data:
        return "поля message нет"
    return f"message — {type(data['message']).__name__}"


# ---------------------------------------------------------------- данные

def new_email(prefix: str = "probe") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}@example.com"


def new_serial(tag: str = "RS") -> str:
    return f"{tag}-{uuid.uuid4().hex[:10].upper()}"


def register_user(email=None, password=VALID_PASSWORD, track=True):
    """Регистрирует временного пользователя через API. Возвращает (email, password, token, response)."""
    email = email or new_email()
    REG.label_user(email)
    resp = call("POST", "/v1/user/registration/usernamepassword",
                json={"firstName": "Probe", "lastName": "User", "username": email, "password": password})
    token = None
    if resp.status_code == 200:
        token = (body_json(resp) or {}).get("accessToken")
        if track:
            REG.users_created += 1
        REG.tokens[email] = token
    return email, password, token, resp


def car_payload(base_city: str, serial: str = None, **overrides) -> dict:
    serial = serial or new_serial()
    REG.label_car(serial)
    payload = {
        "serialNumber": serial, "manufacture": "ProbeMake", "model": "ProbeModel", "year": "2020",
        "fuel": "Petrol", "seats": 4, "carClass": "Economy", "pricePerDay": 100.0,
        "about": "research probe", "city": base_city,
    }
    payload.update(overrides)
    for key in [k for k, v in payload.items() if v is _MISSING]:
        del payload[key]
    return payload


_MISSING = object()
MISSING = _MISSING


def create_car(token: str, payload: dict):
    """POST /v1/cars. Если машина создана (200), она попадает в реестр для удаления в finally."""
    REG.label_car(payload.get("serialNumber", ""))
    resp = call("POST", "/v1/cars", token=token, json=payload)
    if resp.status_code == 200:
        REG.cars_created += 1
        REG.car_owner_token[payload["serialNumber"]] = token
    return resp


def my_cars(token: str) -> list:
    resp = call("GET", "/v1/cars/my", token=token)
    data = body_json(resp)
    return (data or {}).get("cars", []) if isinstance(data, dict) else []


def find_my_car(token: str, serial: str):
    for car in my_cars(token):
        if car.get("serialNumber") == serial:
            return car
    return None


def cleanup_cars(log: FactLog):
    """Удаляет все созданные машины их владельцами; машины, созданные «не тем» токеном, пробует и общим перебором."""
    tokens = list({t for t in REG.car_owner_token.values() if t})
    for serial, token in list(REG.car_owner_token.items()):
        try:
            resp = call("DELETE", f"/v1/cars/{serial}", token=token)
            if resp.status_code == 200:
                REG.cars_deleted += 1
            else:
                # Запасная попытка: другими токенами из реестра (владелец мог отличаться от создателя)
                for other in tokens:
                    if other == token:
                        continue
                    resp2 = call("DELETE", f"/v1/cars/{serial}", token=other)
                    if resp2.status_code == 200:
                        REG.cars_deleted += 1
                        break
        except Exception as exc:  # чистка не должна прерывать остальную чистку
            log.fact(f"чистка: не удалось удалить {REG.cars.get(serial, serial)}: {type(exc).__name__}")
    remaining = 0
    for token in tokens:
        # Подсчёт остатка — только отчёт: сбой одного запроса не должен обрывать итог
        with contextlib.suppress(Exception):
            remaining += sum(1 for c in my_cars(token) if c.get("serialNumber", "").startswith(("RS-", "RU-")))
    log.fact(f"после чистки у временных пользователей осталось машин с префиксом RS-/RU-: {remaining}")


def print_stats(log: FactLog):
    log.header("ИТОГ", "Статистика созданных и удалённых данных")
    log.fact(f"создано пользователей: {REG.users_created}")
    log.fact(f"создано машин: {REG.cars_created}")
    log.fact(f"удалено машин: {REG.cars_deleted}")
    log.fact(f"дата и время прогона: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
