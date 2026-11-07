# Samhus native Value IR: borrowed length-tracked UTF-8 String views

Research status: **unreleased `0.0.0.dev0`**, not an approved memory model,
ownership language feature, standard ABI, package format or native runtime.

## This milestone implements

- `String` literals mapped to immutable, static-lifetime UTF-8 bytes in C11.
- Native String is an internal struct of pointer plus exact byte length;
  indexing returns a bounded, non-owning view of one Unicode code point.
- `String[Int]` validates negative and overlong indices at runtime, without
  allocation or reading beyond the backing literal.
- Safe fixed-width octal escaping prevents C string escape injection.
- `let` and `var` String storage, assignments and lexical shadowing.
- Explicitly typed String function parameters and String return values.
- String `==`/`!=` compare byte lengths plus content via `memcmp`;
  neither pointer identity nor null-termination is used for equality.
- `println(String)` uses length-bounded `fwrite` plus a newline, never
  attacker-controlled printf formatting or null-termination assumptions.
- `len(String)` counts Unicode code points (matching Python-hosted runtime)
  by counting UTF-8 leading bytes; valid UTF-8 is guaranteed for literals.
- Static String values may pass through nested and recursive functions;
  no heap allocation or release is needed for these literal-backed values.

## Explicit limitations

- String + String is supported only using a fixed, bounded process-lifetime
  arena (8 MiB). No arbitrary substring slicing, mutation, interpolation,
  formatting, StringBuilder, file/network input, FFI, heap allocation,
  GC, refcounting, or borrow checker. Arena bytes are never reclaimed.
- Rebinding `var name: String` swaps static references; it does NOT mutate
  the original immutable literal bytes.
- `String` literal cannot contain NUL (current C11 null-terminated model);
  payload is limited to 65536 UTF-8 bytes per literal.
- Unpaired surrogate code points are rejected by the strict UTF-8 encoder.
- `len` counts code points, not grapheme clusters or rendered glyphs.
- Native String code-point indexing returns a view, not an owned copy.
- Native String + String makes an immutable copy in a checked 8 MiB
  process-lifetime arena; earlier views remain valid across calls and loops.
  Concatenation with an empty String avoids allocation; other concatenations
  consume their combined byte lengths until exit. Exhaustion exits with
  runtime code 2. Binaries without concat do not reserve the arena.
- All native strings ultimately come from known compiler-generated constants
  or checked copies in the arena.
  Never expose a pointer from unknown or untrusted C memory through this
  path without introducing lifetime/length validation and ownership rules.
- No guarantee of an independently compiled native Samhus toolchain.
- The interpreter's arbitrary-precision Int and native checked Int64
  still have different failure behavior on overflow.

## CLI

    python -m samhus typecheck examples/native_value_ir_strings.sahu
    python -m samhus native-ir examples/native_value_ir_slices.sahu -o native-slices
    python -m samhus emit-ir-c examples/native_value_ir_strings.sahu
    python -m samhus native-ir examples/native_value_ir_strings.sahu -o samhus-strings
    ./samhus-strings

The example prints:

    Assalomu alaykum, Samhus!
    Toshkent
    11
    true
    🌍🚀

Check tests/test_native_value_ir_strings.py for positive/negative and
Unicode content parity cases. The GitHub workflow verifies the native binary
on Windows, macOS and Linux under Python 3.11 and 3.13.

## Next necessary work

Implement an owned, **length-tracked** String representation with checked
allocation and cleanup, explicit FFI contracts and resource bounds.
The current bounded static arena supports String concat as a research bridge;
general dynamic ownership, arbitrary slicing and external UTF-8 strings
still require a reviewed architecture. This would require owner approval for the permanent
language-level memory model. The current static-lifetime representation
is an internal prototype choice, not a ratified Samhus rule.
