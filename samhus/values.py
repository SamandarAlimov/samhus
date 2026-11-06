"""Experimental immutable-list value semantics, shared across execution paths.

Lists are represented as Python tuples only INSIDE the research runtimes.
The type notation and representation have not been approved as permanent.
"""
import json
from typing import Any

from .errors import SamhusError
from .lexer import Token


MAX_LIST_ITEMS = 100_000


def type_name(value: Any) -> str:
    if type(value) is bool:
        return "Bool"
    if type(value) is int:
        return "Int"
    if type(value) is str:
        return "String"
    if value is None:
        return "Unit"
    if type(value) is tuple:
        if not value:
            return "List[Any]"
        first = type_name(value[0])
        return "List[" + (first if all(type_name(item) == first for item in value) else "Any") + "]"
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
    return type_name(value) == expected


def structural_equal(left: Any, right: Any) -> bool:
    """Avoid Python's surprising True == 1 inside nested list values."""
    if type(left) is not type(right):
        return False
    if type(left) is tuple:
        return len(left) == len(right) and all(
            structural_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def show(value: Any) -> str:
    if type(value) is bool:
        return "true" if value else "false"
    if value is None:
        return "unit"
    if type(value) is tuple:
        return "[" + ", ".join(json.dumps(x, ensure_ascii=False) if type(x) is str else show(x) for x in value) + "]"
    return str(value)


def index_of(sequence: Any, index: Any, token: Token) -> Any:
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
