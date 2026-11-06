"""Experimental immutable-list value semantics, shared across execution paths.

Lists are represented as Python tuples only INSIDE the research runtimes.
The type notation and representation have not been approved as permanent.
"""
import json
from dataclasses import dataclass
from typing import Any

from .errors import SamhusError
from .lexer import Token


MAX_LIST_ITEMS = 100_000
MAX_MAP_ITEMS = 100_000


@dataclass(frozen=True)
class NullValue:
    """Explicit null, distinct from Unit/None. Temporary prototype semantics."""


NULL = NullValue()


@dataclass(frozen=True)
class MapValue:
    """Internal immutable string-key map, insertion order preserved."""
    entries: tuple[tuple[str, Any], ...]

    def get(self, key: str, token: Token) -> Any:
        for stored_key, value in self.entries:
            if stored_key == key:
                return value
        raise SamhusError(f"Missing map key: {key!r}", token.line, token.column)


def map_value(pairs: tuple[tuple[Any, Any], ...], token: Token) -> MapValue:
    if len(pairs) > MAX_MAP_ITEMS:
        raise SamhusError(f"Map size limit exceeded ({MAX_MAP_ITEMS})", token.line, token.column)
    seen = set()
    for key, _ in pairs:
        if type(key) is not str:
            raise SamhusError(f"Map key must be String, got {type_name(key)}", token.line, token.column)
        if key in seen:
            raise SamhusError(f"Duplicate map key: {key!r}", token.line, token.column)
        seen.add(key)
    return MapValue(pairs)


def map_value_type(annotation: str) -> str | None:
    """Return value type from parser-normalized Map[String,T]."""
    if annotation.startswith("Map[String,") and annotation.endswith("]"):
        return annotation[len("Map[String,"):-1]
    return None



def type_name(value: Any) -> str:
    if type(value) is bool:
        return "Bool"
    if type(value) is int:
        return "Int"
    if type(value) is float:
        return "Float"
    if type(value) is NullValue:
        return "Null"
    if type(value) is str:
        return "String"
    if value is None:
        return "Unit"
    if type(value) is tuple:
        if not value:
            return "List[Any]"
        first = type_name(value[0])
        return "List[" + (first if all(type_name(item) == first for item in value) else "Any") + "]"
    if type(value) is MapValue:
        if not value.entries:
            return "Map[String,Any]"
        first = type_name(value.entries[0][1])
        return "Map[String," + (first if all(type_name(item) == first for _, item in value.entries) else "Any") + "]"
    raise TypeError(f"Unknown Samhus value type {type(value).__name__}")


def element_type(declared: str) -> str | None:
    """Extract the element of a parser-validated List[T] annotation."""
    if declared.startswith("List[") and declared.endswith("]"):
        return declared[5:-1]
    return None


def accepts(expected: str | None, value: Any) -> bool:
    if expected in (None, "Any"):
        return True
    inner = element_type(expected)
    if inner is not None:
        return type(value) is tuple and all(accepts(inner, item) for item in value)
    value_type = map_value_type(expected)
    if value_type is not None:
        return type(value) is MapValue and all(accepts(value_type, v) for _, v in value.entries)
    return type_name(value) == expected


def structural_equal(left: Any, right: Any) -> bool:
    """Avoid Python's surprising True == 1 inside nested list values."""
    if type(left) is not type(right):
        return False
    if type(left) is tuple:
        return len(left) == len(right) and all(
            structural_equal(a, b) for a, b in zip(left, right)
        )
    if type(left) is MapValue:
        if len(left.entries) != len(right.entries):
            return False
        right_items = dict(right.entries)
        return all(key in right_items and structural_equal(value, right_items[key])
                   for key, value in left.entries)
    return left == right


def show(value: Any) -> str:
    if type(value) is bool:
        return "true" if value else "false"
    if value is None:
        return "unit"
    if type(value) is NullValue:
        return "null"
    if type(value) is tuple:
        return "[" + ", ".join(json.dumps(x, ensure_ascii=False) if type(x) is str else show(x) for x in value) + "]"
    if type(value) is MapValue:
        return "{" + ", ".join(json.dumps(k, ensure_ascii=False) + ": "
                             + (json.dumps(v, ensure_ascii=False) if type(v) is str else show(v))
                             for k, v in value.entries) + "}"
    return str(value)


def index_of(sequence: Any, index: Any, token: Token) -> Any:
    if type(sequence) is MapValue:
        if type(index) is not str:
            raise SamhusError(f"Map index must be String, got {type_name(index)}", token.line, token.column)
        return sequence.get(index, token)
    if type(sequence) not in (tuple, str):
        raise SamhusError(
            f"Indexing requires List or String, got {type_name(sequence)}",
            token.line, token.column,
        )
    if type(index) is not int:
        raise SamhusError(
            f"Index must be Int, got {type_name(index)}", token.line, token.column,
        )
    if index < 0 or index >= len(sequence):
        raise SamhusError(
            f"Index out of bounds: {index} for length {len(sequence)}",
            token.line, token.column,
        )
    return sequence[index]


def build_list(items: tuple[Any, ...], token: Token) -> tuple[Any, ...]:
    if len(items) > MAX_LIST_ITEMS:
        raise SamhusError(
            f"List size limit exceeded ({MAX_LIST_ITEMS})", token.line, token.column
        )
    return items
