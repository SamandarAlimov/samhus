"""Experimental exact finite decimal arithmetic with explicit resource limits.

Unlike binary64 Float, Decimal arithmetic must never silently round.
Operations exceeding limits or requiring rounding raise a Samhus error.
Only Decimal/Decimal and Decimal/Int combinations are supported.
"""
from decimal import (
    Decimal, DecimalException, DivisionByZero, Inexact, InvalidOperation,
    ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext,
)
import re

from .errors import SamhusError
from .lexer import Token

MAX_INPUT_DIGITS = 256
MAX_ABS_EXPONENT = 128
WORK_PRECISION = 4096


def _error(token: Token, message: str):
    raise SamhusError(message, token.line, token.column)


def bounded(value: Decimal, token: Token) -> Decimal:
    if not value.is_finite():
        _error(token, "Decimal must be finite")
    if len(value.as_tuple().digits) > MAX_INPUT_DIGITS * 4:
        _error(token, "Decimal digit budget exceeded")
    if abs(value.as_tuple().exponent) > MAX_ABS_EXPONENT * 4:
        _error(token, "Decimal exponent budget exceeded")
    return value


def make_decimal(value: object, token: Token) -> Decimal:
    if type(value) is Decimal:
        return bounded(value, token)
    if type(value) is int:
        if len(str(abs(value))) > MAX_INPUT_DIGITS:
            _error(token, "Decimal input digit budget exceeded")
        return Decimal(value)
    if type(value) is not str:
        _error(token, "decimal expects String, Int or Decimal (Float conversion is forbidden)")
    if not value or len(value) > MAX_INPUT_DIGITS + 16:
        _error(token, "Invalid Decimal input or length")
    if re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value) is None:
        _error(token, "Invalid Decimal literal")
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        _error(token, "Invalid Decimal literal")
    if not parsed.is_finite():
        _error(token, "Decimal must be finite")
    if len(parsed.as_tuple().digits) > MAX_INPUT_DIGITS:
        _error(token, "Decimal input digit budget exceeded")
    if abs(parsed.as_tuple().exponent) > MAX_ABS_EXPONENT:
        _error(token, "Decimal exponent budget exceeded")
    return parsed


def operation(op: str, left: object, right: object, token: Token):
    if type(left) not in (Decimal, int) or type(right) not in (Decimal, int):
        _error(token, "Decimal cannot mix with Float, Bool or non-numeric values")
    a = make_decimal(left, token)
    b = make_decimal(right, token)
    try:
        with localcontext() as ctx:
            ctx.prec = WORK_PRECISION
            ctx.Emax = 999999
            ctx.Emin = -999999
            ctx.traps[Inexact] = True
            if op == "+":
                value = a + b
            elif op == "-":
                value = a - b
            elif op == "*":
                value = a * b
            elif op == "/":
                if b.is_zero():
                    _error(token, "Division by zero")
                value = a / b
            elif op in ("<", "<=", ">", ">="):
                return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
            else:
                raise AssertionError(f"Unhandled Decimal operator {op!r}")
    except Inexact:
        _error(token, "Decimal division requires rounding; use an explicit future rounding API")
    except (InvalidOperation, DecimalException, OverflowError):
        _error(token, "Decimal arithmetic failed or exceeded limits")
    return bounded(value, token)


ROUNDING_MODES = {
    "half_even": ROUND_HALF_EVEN,
    "half_up": ROUND_HALF_UP,
    "down": ROUND_DOWN,
}


def _rounding_args(scale: object, mode: object, token: Token):
    if type(scale) is not int or not 0 <= scale <= 18:
        _error(token, "Decimal scale must be Int between 0 and 18")
    if type(mode) is not str or mode not in ROUNDING_MODES:
        _error(token, "Decimal rounding mode must be half_even, half_up or down")
    return Decimal(1).scaleb(-scale), ROUNDING_MODES[mode]


def decimal_round(value: object, scale: object, mode: object, token: Token) -> Decimal:
    if type(value) is not Decimal:
        _error(token, "decimal_round expects Decimal")
    quantizer, rounding = _rounding_args(scale, mode, token)
    try:
        with localcontext() as ctx:
            ctx.prec = WORK_PRECISION
            ctx.rounding = rounding
            return bounded(bounded(value, token).quantize(quantizer), token)
    except DecimalException:
        _error(token, "Decimal rounding failed")


def decimal_div(left: object, right: object, scale: object, mode: object, token: Token) -> Decimal:
    if type(left) is not Decimal or type(right) is not Decimal:
        _error(token, "decimal_div expects Decimal operands")
    quantizer, rounding = _rounding_args(scale, mode, token)
    a, b = bounded(left, token), bounded(right, token)
    if b.is_zero():
        _error(token, "Division by zero")
    try:
        with localcontext() as ctx:
            ctx.prec = WORK_PRECISION
            ctx.rounding = rounding
            result = a / b
            return bounded(result.quantize(quantizer), token)
    except DecimalException:
        _error(token, "Decimal division or rounding failed")


def decimal_negate(value: Decimal, token: Token):
    return bounded(bounded(value, token).copy_negate(), token)
