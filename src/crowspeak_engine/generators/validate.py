"""Validate a generator's JSON reply against its schema.

Covers the JSON-schema subset the engine's schemas use (`type`, `enum`, `properties`,
`required`, `additionalProperties: false`, `items`), so the base install needs no extra
dependency. Unknown keywords are ignored.
"""

from __future__ import annotations

import json
from typing import Any

from .base import GenerationError

_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "boolean": (bool,),
    "integer": (int,),
    "number": (int, float),
    "null": (type(None),),
}


def _is_type(value: Any, name: str) -> bool:
    if isinstance(value, bool) and name in ("integer", "number"):
        return False  # bool is an int subclass, but not a JSON number
    return isinstance(value, _TYPES[name])


def _check(value: Any, schema: dict, path: str) -> None:
    expected = schema.get("type")
    if expected is not None:
        names = [expected] if isinstance(expected, str) else expected
        if not any(_is_type(value, n) for n in names):
            raise GenerationError(f"{path}: expected {' or '.join(names)}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise GenerationError(f"{path}: {value!r} is not one of {schema['enum']}")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", ()):
            if key not in value:
                raise GenerationError(f"{path}: missing required field {key!r}")
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise GenerationError(f"{path}: unexpected field {extra[0]!r}")
        for key, sub in properties.items():
            if key in value:
                _check(value[key], sub, f"{path}.{key}")
    elif isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            _check(item, schema["items"], f"{path}[{i}]")


def validate(raw: str, schema: dict) -> Any:
    """Decode `raw` and check it against `schema`; raises GenerationError if unusable."""
    try:
        data = json.loads(raw)
    except ValueError as e:
        raise GenerationError(f"reply is not valid JSON: {e}") from e
    _check(data, schema, "$")
    return data
