"""Experimental safe-core builtins shared by the two Samhus runtimes.

Builtins here are intentionally small and deterministic. These Python-hosted
implementations are NOT part of a finalized Samhus standard library or ABI.
Neither execution engine is a sandbox for untrusted programs.
"""
import json
from typing import Any, Callable, TextIO

from .errors import SamhusError
from .lexer import Token

# One primitive signature per function. Keep signatures and execution in sync.
BUILTIN_SIGNATURES: dict[str, tuple[tuple[str, ...], str]] = {
    "println": (("Any",), "Unit"),
    "assert": (("Bool",), "Unit"),
    "len": (("String",), "Int"),
    "str": (("Any",), "String"),
    "json_valid": (("String",), "Bool"),
}


def type_name(value: Any) -> str:
    if type(value) is bool:
        return "Bool"
    if type(value) is int:
        return "Int"
    if type(value) is str:
        return "String"
    if value is None:
        return "Unit"
    raise TypeError("Unsupported Samhus runtime type")


def display(value: Any) -> str:
    if type(value) is bool:
        return "true" if value else "false"
    if value is None:
        return "unit"
    return str(value)


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"Non-JSON numeric constant {value!r}")


def call_builtin(name: str, args: tuple[Any, ...], token: Token, output: TextIO) -> Any:
    """Execute a declared builtin or fail with a source-positioned diagnostic."""
    signature = BUILTIN_SIGNATURES.get(name)
    if signature is None:
        raise KeyError(name)
    expected_types, _return_type = signature
    if len(args) != len(expected_types):
        raise SamhusError(
            f"{name} expects {len(expected_types)} argument, got {len(args)}",
            token.line, token.column,
        )
    for value, required in zip(args, expected_types):
        if required != "Any" and type_name(value) != required:
            raise SamhusError(
                f"Type mismatch: expected {required}, got {type_name(value)}",
                token.line, token.column,
            )

    value = args[0]
    if name == "println":
        print(display(value) if value is not None else "None", file=output)
        return None
    if name == "assert":
        if not value:
            raise SamhusError("Assertion failed", token.line, token.column)
        return None
    if name == "len":
        return len(value)
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
