# Samhus native backend — experimental 0.0.6

This research backend translates a RESTRICTED, explicitly typed Samhus
subset into C11. A trusted local C compiler produces a machine-code
executable which runs WITHOUT a Python interpreter.

The Samhus compiler itself STILL RUNS ON PYTHON. This is not LLVM,
self-hosting, a stable ABI, or a full-language native compiler.

## Commands

~~~sh
python -m samhus emit-c examples/native.sahu > generated.c
python -m samhus native examples/native.sahu -o native-demo
./native-demo
~~~

On Windows choose an executable output name ending in .exe and launch
that output. Use --cc to select a C11 compiler (cc, gcc, clang); a
suitable compiler must be installed on the machine and in PATH.

## Supported subset

- Explicitly typed functions with returns Int, Bool, String, Unit.
- Explicitly typed parameters and declarations: Int, Bool, String.
- Zero-argument main with explicit Unit return type.
- Integers, booleans and UTF-8 string literals and bindings.
- If/else, while, function calls, recursion, local variable scopes.
- Numeric operations, comparisons, boolean short-circuiting, string equality.
- println(Int / Bool / String) and assert(Bool).
- Deterministic left-to-right argument and operand evaluation.

## Critical semantic difference: integer range

The tree and bytecode runtimes implement arbitrary-precision Samhus Int.
The native C backend has CHECKED SIGNED 64-BIT Int:
- minimum: -9223372036854775808
- maximum: 9223372036854775807
- multiplication, addition, subtraction, division and negation are checked.
- overflow exits the executable with error status 2; it does not wrap.

Full Samhus language equivalence is therefore NOT claimed. The native
backend rejects out-of-range literals and unsupported syntax instead
of silently producing incompatible behavior.

## Deliberately unsupported

Dynamic Any, untyped local declarations/function signatures, string
concatenation, Unit return expressions, len/str/json_valid, AI runtimes,
JSON objects, collection types, modules/imports, networking, async,
threading, GPU operations, filesystem, FFI, portable artifact format.

It is not a security sandbox or a production-grade compiler.
Generated code relies on the host C compiler and system C runtime.
Do not use this converter on untrusted source or with untrusted compilers.

## Verification

- Test compilation of standalone executables and their outputs.
- Arithmetic boundary cases, division-by-zero, overflow, Unicode, recursion.
- Deterministic in-range arithmetic corpus compared against tree interpreter.
- Cross-platform end-to-end smoke on CI with compatible C compilers.

## Future work

True typed IR; full-semantic native lowering; verified memory model;
fuzzing/sanitizers; external libraries; optimized native code; linking
and reproducible packaging; Python-independent compiler and self-hosting.

C as an implementation target is an EXPERIMENT, not a founder-approved
permanent language architecture.
