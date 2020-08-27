import json
from typing import Any


def update_not_none(params: dict, changes: dict) -> None:
    for k, v in changes.items():
        if v is not None:
            params[k] = v


def read_json_prefix(string: str) -> Any:
    try:
        return json.loads(string)
    except json.JSONDecodeError as e:
        return json.loads(string[:e.pos])
