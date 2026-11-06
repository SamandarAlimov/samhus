# Samhus 0.0.10 — Decimal and Result research

**Status: experimental.** Works in the Python-hosted tree interpreter and bytecode VM.
No stable semantics, native backend support, audited security or accounting certification.

## Decimal: bounded exact base-10 arithmetic

    fn main() -> Unit {
        println(decimal("0.10") + decimal("0.20"))
        println(decimal_round(decimal("1.245"), 2, "half_up"))
        println(decimal_div(decimal("1"), decimal("3"), 2, "half_up"))
    }

Expected output: 0.30, 1.25, 0.33 on separate lines.

Construction uses decimal(String) or decimal(Int). Float input is rejected
to avoid silently importing binary rounding. Accepted Decimal inputs have
at most 256 digits and absolute exponent up to 128; intermediate result
digits and exponents are bounded. Internal arithmetic uses a 4096-digit
working context and fails rather than silently rounding. Exact division
such as 1 / 4 succeeds; 1 / 3 fails unless decimal_div is explicitly used.

Rounding modes: half_even (ties to even), half_up (ties away from zero),
down (toward zero). Scale: Int between 0 and 18 inclusive. Operators +, -,
*, /, ordering and unary negation are implemented. Do not mix Decimal
and Float. This is not a substitute for a reviewed accounting ledger.

Decimal cannot be encoded as a JSON number in this prototype: use an
explicit string representation for suitable external API contracts.

## Result[T]: typed successes and controlled errors

    fn main() -> Unit {
        let good: Result[Int] = result_ok(42)
        let bad: Result[Int] = result_err("missing record")
        println(result_is_ok(good))
        println(result_or(bad, 0))
        println(result_value(good))
        println(result_error(bad))
    }

Helpers: result_ok, result_err, result_is_ok, result_value, result_error,
result_or. The fallback argument to result_or is eagerly evaluated like
other Samhus call arguments. result_value(Err) or result_error(Ok) raises
a diagnosed Samhus error, rather than silently returning the wrong type.

try_json_parse(String) returns Result[Any]. A malformed JSON string becomes
Err(message), not an immediate uncaught JSON parse error. This does NOT
catch arbitrary runtime exceptions or provide full try/catch semantics.
At a statically known typed boundary Result[T] checks successful values.
Any may still defer errors to runtime and the type checker is not sound.

## Native compatibility

Float, Decimal, Result, Map and List are NOT supported in the experimental
C11 native backend. Only the separately documented restricted native
subset produces a Python-free executable; no full-language parity yet.

## Verification

    python -m unittest discover -s tests -v
    python -m samhus typecheck examples/decimal_result.sahu
    python -m samhus run examples/decimal_result.sahu --backend tree --typecheck
    python -m samhus run examples/decimal_result.sahu --backend vm --typecheck

The suffix .sahu and the type/runtime implementation decisions are provisional.
