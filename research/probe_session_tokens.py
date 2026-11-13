"""
Пробы перед решением о постоянной учётке (шаг 6.4a): Q-API-19 … Q-API-21.

Q-API-19 — два входа одним пользователем: действуют ли оба токена и не отзывает ли второй вход первый.
Q-API-20 — срок жизни токена: claims из payload JWT (без проверки подписи) и exp − iat.
Q-API-21 — по Swagger, без запросов: все операции API (метод, путь, защита, summary).

Скрипт фиксирует факты, оценок в нём нет. Регистрирует ровно одного пользователя — через
IlCarroAPI.register, который сам пишет его в журнал пользователей (logs/registered_users_main.jsonl).
Сами токены никуда не печатаются: в лог идут только claims, статусы и вычисленный срок
(FactLog дополнительно маскирует всё, что похоже на JWT).

Запуск: python research/probe_session_tokens.py --run 1
Лог: research/evidence/probe_session_tokens_run1.log
"""

import base64
import json
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

# Скрипт запускается как файл: research/ (common) и корень проекта (api) надо добавить в путь до импорта,
# поэтому импорты ниже стоят после кода — E402 подавлен намеренно
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.car_api import IlCarroAPI  # noqa: E402
from common import REG, ROOT, VALID_PASSWORD, FactLog, body_json, call, new_email, print_stats, run_name  # noqa: E402

LOG = FactLog(run_name("probe_session_tokens"))
SWAGGER = ROOT / "docs" / "requirements" / "api-docs.json"
# GET, который требует токен (Swagger: security «Bearer Authentication») и ничего не меняет
AUTH_GET = "/v1/cars/my"


def jwt_claims(token: str) -> dict:
    """Payload JWT без проверки подписи: нужен только срок, подпись проверяет сервер."""
    payload = token.split(".")[1]
    padded = payload + "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def login(email: str):
    resp = call("POST", "/v1/user/login/usernamepassword", json={"username": email, "password": VALID_PASSWORD})
    token = (body_json(resp) or {}).get("accessToken") if resp.status_code == 200 else None
    if token:
        REG.tokens[f"{email}#{len(REG.tokens)}"] = token  # чтобы mask() скрыл и этот токен
    return resp, token


def auth_get(title: str, token: str | None):
    resp = call("GET", AUTH_GET, token=token)
    LOG.fact(f"`GET {AUTH_GET}` {title}: HTTP {resp.status_code}; тело={(resp.text or '')[:80]!r}")
    return resp


def q_api_19_two_logins(email: str, reg_token: str) -> dict[str, str]:
    LOG.header("Q-API-19", "Два входа одним пользователем")
    auth_get("с токеном регистрации, до входов", reg_token)
    resp1, token1 = login(email)
    LOG.fact(f"вход 1: HTTP {resp1.status_code}, accessToken {'есть' if token1 else 'нет'}")
    auth_get("с токеном входа 1, до входа 2", token1)
    resp2, token2 = login(email)
    LOG.fact(f"вход 2: HTTP {resp2.status_code}, accessToken {'есть' if token2 else 'нет'}")
    LOG.fact(f"токен входа 2 совпадает с токеном входа 1: {'да' if token1 == token2 else 'нет'}")
    auth_get("с токеном входа 1, после входа 2", token1)
    auth_get("с токеном входа 2", token2)
    auth_get("с токеном регистрации, после двух входов", reg_token)
    return {"регистрация": reg_token, "вход 1": token1, "вход 2": token2}


def q_api_20_token_lifetime(tokens: dict[str, str]) -> None:
    LOG.header("Q-API-20", "Срок жизни токена (claims payload JWT, подпись не проверялась)")
    for title, token in tokens.items():
        if not token:
            LOG.fact(f"{title}: токена нет")
            continue
        claims = jwt_claims(token)
        LOG.fact(f"{title}: claims {json.dumps(claims, ensure_ascii=False, sort_keys=True)}")
        iat, exp = claims.get("iat"), claims.get("exp")
        if isinstance(iat, int) and isinstance(exp, int):
            utc = {name: datetime.fromtimestamp(value, UTC).isoformat() for name, value in (("iat", iat), ("exp", exp))}
            LOG.fact(
                f"{title}: iat {utc['iat']}, exp {utc['exp']}, exp − iat = {exp - iat} с ({(exp - iat) / 3600:g} ч)"
            )
        else:
            LOG.fact(f"{title}: iat или exp нет (или не целые)")


def q_api_21_swagger_operations() -> None:
    LOG.header("Q-API-21", "Операции API по Swagger (без запросов)")
    spec = json.loads(SWAGGER.read_text(encoding="utf-8"))
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            secured = "Bearer" if operation.get("security") else "без защиты"
            LOG.fact(f"`{method.upper()} {path}` — {secured}; summary: {operation.get('summary', '')!r}")


def main() -> None:
    LOG.line(f"# probe_session_tokens, {datetime.now().isoformat(timespec='seconds')}")
    try:
        q_api_21_swagger_operations()
        email = new_email()
        REG.label_user(email)
        api = IlCarroAPI()
        resp = api.register(email, VALID_PASSWORD)
        if resp.status_code != 200 or not api.token:
            LOG.fact(f"регистрация не удалась: HTTP {resp.status_code}; дальнейшие пробы не выполнялись")
            return
        REG.users_created += 1
        REG.tokens[email] = api.token
        tokens = q_api_19_two_logins(email, api.token)
        q_api_20_token_lifetime(tokens)
    except Exception:
        LOG.line(traceback.format_exc())
        raise
    finally:
        print_stats(LOG)


if __name__ == "__main__":
    main()
