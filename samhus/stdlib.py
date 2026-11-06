"""Experimental safe-core builtins shared by the two Samhus runtimes.

Builtins here are intentionally small and deterministic. These Python-hosted
implementations are NOT part of a finalized Samhus standard library or ABI.
Neither execution engine is a sandbox for untrusted programs.
"""
import json
from typing import Any, Callable, TextIO

from .errors import SamhusError
from .lexer import Token
from .values import MAX_LIST_ITEMS, MAX_MAP_ITEMS, MapValue, NullValue, map_value, show, type_name as value_type_name
from .numbers import as_float, numeric
from .json_bridge import decode_json, encode_json

# One primitive signature per function. Keep signatures and execution in sync.
BUILTIN_SIGNATURES: dict[str, tuple[tuple[str, ...], str]] = {
    "println": (("Any",), "Unit"),
    "assert": (("Bool",), "Unit"),
    "len": (("Any",), "Int"),
    "append": (("Any", "Any"), "Any"),
    "str": (("Any",), "String"),
    "json_valid": (("String",), "Bool"),
    "is_null": (("Any",), "Bool"),
    "to_float": (("Any",), "Float"),
    "json_parse": (("String",), "Any"),
    "json_encode": (("Any",), "String"),
    "map_set": (("Any", "String", "Any"), "Any"),
    "map_has": (("Any", "String"), "Bool"),
    "map_keys": (("Any",), "List[String]"),
}


def type_name(value: Any) -> str:
    return value_type_name(value)


def display(value: Any) -> str:
    return show(value)


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"Non-JSON numeric constant {value!r}")


def call_builtin(name: str, args: tuple[Any, ...], token: Token, output: TextIO) -> Any:
    """Execute a declared builtin or fail with a source-positioned diagnostic."""
    signature = BUILTIN_SIGNATURES.get(name)
    if signature is None:
        raise KeyError(name)
    expected_types, _return_type = signature
    if len(args) != len(expected_types):
        plural = "argument" if len(expected_types) == 1 else "arguments"
        raise SamhusError(
            f"{name} expects {len(expected_types)} {plural}, got {len(args)}",
            token.line, token.column,
        )
    for value, required in zip(args, expected_types):
        if required != "Any" and type_name(value) != required:
            raise SamhusError(
                f"Type mismatch: expected {required}, got {type_name(value)}",
                token.line, token.column,
            )

    value = args[0]
    if name == "is_null":
        return type(value) is NullValue
    if name == "to_float":
        if not numeric(value):
            raise SamhusError(f"to_float expects Int or Float, got {type_name(value)}", token.line, token.column)
        return as_float(value, token)
    if name in {"map_set", "map_has", "map_keys"}:
        if type(value) is not MapValue:
            raise SamhusError(f"{name} expects Map, got {type_name(value)}", token.line, token.column)
        if name == "map_has":
            return any(key == args[1] for key, _ in value.entries)
        if name == "map_keys":
            return tuple(key for key, _ in value.entries)
        key, item = args[1], args[2]
        if not any(k == key for k, _ in value.entries) and len(value.entries) >= MAX_MAP_ITEMS:
            raise SamhusError(f"Map size limit exceeded ({MAX_MAP_ITEMS})", token.line, token.column)
        if any(k == key for k, _ in value.entries):
            return MapValue(tuple((k, item if k == key else v) for k, v in value.entries))
        return MapValue(value.entries + ((key, item),))
    if name == "json_parse":
        return decode_json(value, token)
    if name == "json_encode":
        return encode_json(value, token)
    if name == "append":
        if type(value) is not tuple:
            raise SamhusError(
                f"append expects List, got {type_name(value)}", token.line, token.column,
            )
        if len(value) >= MAX_LIST_ITEMS:
            raise SamhusError(
                f"List size limit exceeded ({MAX_LIST_ITEMS})", token.line, token.column
            )
        return value + (args[1],)
    if name == "len":
        if type(value) not in (tuple, str, MapValue):
            raise SamhusError(
                f"Type mismatch: expected String, got {type_name(value)} (or List)",
                token.line, token.column,
            )
    if name == "println":
        print(display(value) if value is not None else "None", file=output)
        return None
    if name == "assert":
        if not value:
            raise SamhusError("Assertion failed", token.line, token.column)
        return None
    if name == "len":
        return len(value.entries) if type(value) is MapValue else len(value)
    if name == "str":
        return display(value)
    if name == "json_valid":
        # AI outputs often contain user-controlled JSON text. Validation must
        # report false rather than propagate JSONDecodeError into the host.
        try:
            # Reject Python json's non-standard NaN / Infinity extensions.
            json.loads(value, parse_constant=_reject_nonfinite)
            return True
        except (ValueError, RecursionError):
            return False
    raise AssertionError(f"Unhandled builtin {name!r}")
