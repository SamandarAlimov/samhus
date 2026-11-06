# Samhus 0.0.9: finite Float and explicit Null (EXPERIMENTAL)

These are implemented prototype semantics in the Python-hosted tree
interpreter and bytecode VM, not founder-approved permanent language rules.

## Float

- Float is finite IEEE-754 binary64 using Python float as host.
- Literals include 1.25, 2e3, 1.5E-2; malformed exponents are rejected.
- Int + Float, Float - Int, multiplication and division return Float.
- Int / Int retains truncate-toward-zero behavior and unbounded Int.
- Numeric order comparisons accept mixed Int and Float; strict equality
  considers Int(1) different from Float(1.0).
- to_float(number) converts Int/Float to Float, rejecting huge Int values
  that cannot be represented as finite binary64.
- Float division by zero and nonfinite arithmetic results are errors.
- Float is approximate and unsuitable for exact money or accounting.
- This is NOT an optimized native or GPU Float implementation.

## Null versus Unit

- null has type Null and a distinct runtime identity from Unit/None.
- is_null(value) tests the exact Null value; it does not coerce Unit.
- Null is supported in typed List/Map, Any, function returns, JSON values.
- A proper Option/Result model is NOT implemented.
- json_encode(Unit) currently still produces JSON null for compatibility,
  but the preferred JSON null representation is explicit Null.

## JSON

- json_parse accepts finite fractional JSON numbers as Float.
- JSON null is now Null (previously Unit); this is a breaking prototype
  behavior change.
- json_encode emits finite Float and Null in nested Map/List structures.
- Nonstandard NaN, Infinity and overflowing exponents are rejected.
- json_valid validates syntax only: a syntactically valid 1e309 may still
  be rejected by json_parse for its nonfinite value.
- JSON resource limits from MAPS_JSON.md still apply.

## CLI sample

    python -m samhus typecheck examples/float_null.sahu
    python -m samhus run examples/float_null.sahu --backend tree --typecheck
    python -m samhus run examples/float_null.sahu --backend vm --typecheck
    python -m samhus ast examples/float_null.sahu

The native C11 backend still rejects Float and Null. It has NOT attained
full native Samhus semantics. No final memory, type or compiler model
decision was made.
