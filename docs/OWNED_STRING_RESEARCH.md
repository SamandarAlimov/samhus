# Owned String C11 runtime — isolated research experiment

**Status:** independent proof of concept, **not integrated** with the Samhus
parser, Value IR-to-C compiler, CLI, language semantics or production runtime.
Samhus remains unreleased at `0.0.0.dev0`. No permanent memory model,
ABI, concurrency policy or FFI has been approved.

This experiment consists of `runtime/owned_string.h` and
`runtime/owned_string.c`.

## Demonstrated behavior

- Immutable UTF-8 values with reference-counted heap buffers.
- Every returned handle owns one strong reference. An explicit
  `sh_owned_retain` creates another reference; every owned handle must be
  paired with exactly one `sh_owned_drop`.
- `sh_owned_copy_assign(&destination, source)` retains the incoming
  reference **before** releasing the previous destination, including
  `sh_owned_copy_assign(&x, x)`; `sh_owned_move_assign(&destination,
  &source)` transfers an existing strong reference and clears source.
  `sh_owned_move_assign(&x, &x)` is a no-op. Both operations require
  valid initialized C handles and do **not** prevent unsafe shallow copies.
- Code-point slices and indexes increment the original buffer's reference
  count and remain readable after the parent handle is dropped.
- Concatenation creates a fresh owned result, except when an operand is
  empty, in which case the nonempty operand is retained.
- Dropping the **last reference** frees the backing allocation. A later
  allocation may consume its live-byte budget again. This is genuine
  reclamation within the independent C library, unlike the static arena.
- UTF-8 validation rejects malformed or truncated encodings, overlong
  encodings, surrogates, embedded NUL and code points outside Unicode.
- Checked **1 MiB concurrently live payload** budget, excluding headers,
  stack, library and allocator overhead. This is NOT a process memory cap.
- Single-threaded runtime; invalid input or exhaustion exits with code 2.

## Safety limitations

This API is **manual**. A caller can trigger undefined behavior by
shallow-copying a C handle struct without `sh_owned_retain`, dropping an
invalid handle, or retaining an already-freed handle. The library provides
no general memory safety for arbitrary C code and has not been independently
audited. Reference counts are non-atomic; cycles and concurrency are not
supported.

The current Samhus native Value IR compiler does not track ownership
transfers through temporary expressions, PHI nodes, assignments, function
arguments/returns and every early-exit path. Therefore this library is
**not linked into** the compiler, and the compiler continues to use the
separate static 8 MiB String arena. Unsound integration would risk
use-after-free.

## Reproducible test commands

    python -m unittest discover -s tests -p "test_owned_string_c.py" -v
    python -m unittest discover -s tests -v

Cross-platform GitHub Actions runs these compiled C11 scenarios on Ubuntu,
Windows and macOS for Python 3.11 and 3.13, including deterministic
50,000-operation randomized handle replacement/move/slice/concat stress.
An additional Ubuntu Clang build runs that stress fixture with
**AddressSanitizer + UndefinedBehaviorSanitizer**, including leak detection.
Sanitizer success is a narrower dynamic test, not a proof of memory safety
for arbitrary C clients, platforms or real compiler lowering.

## Next engineering gate

Implement ownership-aware typed/effect IR with explicit retain, move,
borrow and drop operations; verify all CFG joins and error/early-return
paths; then evaluate integration using sanitizers and differential tests.
The choice of a permanent ownership model and ABI requires owner approval.
