"""
Операции API, описанные в Swagger (docs/requirements/api-docs.json).

Нужны проверкам «фронт обращается только к тому, что есть в контракте» (DISC-05): запрос, пойманный
в браузере, сверяется со списком операций. Параметр пути ({serialNumber}) совпадает с любым одним
сегментом.
"""

import json
import re
from functools import cache

from config import PROJECT_ROOT

SWAGGER_FILE = PROJECT_ROOT / "docs" / "requirements" / "api-docs.json"
_HTTP_METHODS = frozenset({"get", "put", "post", "delete", "patch", "head", "options"})
_PATH_PARAMETER = re.compile(r"(\{[^}]*\})")


@cache
def documented_operations() -> tuple[tuple[str, str], ...]:
    """Пары (МЕТОД, шаблон пути) из Swagger, например ("DELETE", "/v1/cars/{serialNumber}")."""
    paths = json.loads(SWAGGER_FILE.read_text(encoding="utf-8"))["paths"]
    return tuple(
        (method.upper(), template)
        for template, operations in paths.items()
        for method in operations
        if method in _HTTP_METHODS
    )


def is_documented(method: str, path: str) -> bool:
    """Есть ли в Swagger операция с таким методом и путём."""
    for known_method, template in documented_operations():
        pattern = "".join(
            "[^/]+" if part.startswith("{") else re.escape(part) for part in _PATH_PARAMETER.split(template)
        )
        if known_method == method.upper() and re.fullmatch(pattern, path):
            return True
    return False
