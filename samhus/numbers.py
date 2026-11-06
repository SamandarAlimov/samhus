"""Experimental finite Float and mixed-number semantics for Samhus.

Int/Int division retains the legacy truncate-toward-zero behavior. Any
operation involving Float returns a finite binary64 Float; conversion of a
very large Int or nonfinite results fails with SamhusError instead of leaking
host exceptions. This is NOT a financial decimal arithmetic implementation.
"""
import math
from decimal import Decimal
from .decimal_core import operation as decimal_operation, decimal_negate

from .errors import SamhusError
from .lexer import Token


def numeric(value: object) -> bool:
    return type(value) in (int, float)


def finite(value: float, token: Token) -> float:
    if not math.isfinite(value):
        raise SamhusError("Non-finite Float result", token.line, token.column)
    return value


def as_float(value: int | float, token: Token) -> float:
    if type(value) is float:
        return finite(value, token)
    try:
        result = float(value)
    except OverflowError:
        raise SamhusError("Int too large to convert to Float", token.line, token.column) from None
    return finite(result, token)


def arithmetic(op: str, left: object, right: object, token: Token):
    if op in {"==", "!="}:
        raise AssertionError("Equality is handled by structural equality")
    if op == "+" and type(left) is str and type(right) is str:
        return left + right
    if type(left) is Decimal or type(right) is Decimal:
        return decimal_operation(op, left, right, token)
    if not (numeric(left) and numeric(right)):
        raise SamhusError(
            f"'{op}' requires integers or floats (or two strings for '+')",
            token.line, token.column,
        )
    if type(left) is int and type(right) is int:
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            if right == 0:
                raise SamhusError("Division by zero", token.line, token.column)
            quotient = abs(left) // abs(right)
            return -quotient if (left < 0) != (right < 0) else quotient
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
    a, b = as_float(left, token), as_float(right, token)
    if op == "/":
        if b == 0.0:
            raise SamhusError("Division by zero", token.line, token.column)
        return finite(a / b, token)
    if op == "+":
        return finite(a + b, token)
    if op == "-":
        return finite(a - b, token)
    if op == "*":
        return finite(a * b, token)
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    if op == ">":
        return a > b
    if op == ">=":
        return a >= b
    raise AssertionError(f"Unexpected numeric operator {op!r}")


def negate(value: object, token: Token):
    if type(value) is Decimal:
        return decimal_negate(value, token)
    if not numeric(value):
        raise SamhusError("Unary '-' requires an integer or float", token.line, token.column)
    if type(value) is float:
        return finite(-value, token)
    return -value
