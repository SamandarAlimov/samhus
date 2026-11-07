# Native String ownership: experimental design constraints

Status: **research**, not owner-approved semantics, not a selected ABI/runtime.

## What is safe today

The Value IR -> C11 backend represents String as immutable
`(const byte *, byte_length)` views. Compiler literals live for the process.
Concatenations are stored in a statically bounded **8 MiB** arena, so views
to them cannot dangle while the process is alive. An optional 4096-slot
content-reuse cache can return a previously allocated identical view.

- A cache entry may be replaced; the actual string bytes remain allocated.
- Cache candidates are checked by both a hash and full byte comparison.
- The arena has checked cumulative bounds. Novel results may exhaust it.
- Existing views do not reveal addresses or aliases to Samhus source code.
- This does **not** prevent DoS, cap process output, or make untrusted
  programs safe to execute.

## Why the arena cannot simply be reset on function or block exit

Values can be aliased to locals, passed to other functions and returned.
An indexed String points inside the original backing bytes. A function or
block can return a view into a String created earlier in the same scope.
Reusing those bytes without knowing **all surviving aliases** creates
use-after-free and content mutation bugs.

The cache introduced above is *deduplication*; it never frees memory.

## Separate C11 owned-handle proof of concept (not compiler-integrated)

The independent C11 runtime in `runtime/owned_string.{h,c}` explores
reference counts, UTF-8 views that retain their owner, last-reference
reclamation and a 1 MiB live-payload ceiling. C code must use explicit
retain/drop correctly. It is **not enabled in the Samhus compiler**.
See [isolated runtime research](OWNED_STRING_RESEARCH.md).

## Read-only Value IR ownership obligations (implemented; no codegen)

The `samhus/ownership_ir.py` overlay and `ir --ownership` CLI report
candidate lifetime events and unresolved local/call/edge questions.
These markers are *not safe executable releases*. See
[ownership IR research](OWNERSHIP_IR.md).

## Next compiler-integration architecture experiment (not yet implemented)

Implement a **separate** owned-handle prototype, with:

1. Backing allocations recording size, provenance and reference count.
2. Borrowed slices keeping the owner's lifetime, not only a raw pointer.
3. Explicit clone/retain/drop operations for assignments, call parameters,
   returns, local scope exits, PHI edges and expression temporaries.
4. Overflow-checked allocation and a strict live-byte budget; exhaustion
   must fail deterministically before allocation.
5. Audit of all exceptional and early-return edges for cleanup.
6. ASan/UBSan builds where supported, plus differential stress for
   nested/recursive calls, indexing, loops, aliasing and lifetime.
7. Independent review of concurrency, FFI, unsafe boundary and language
   ownership semantics **before** replacing the current compiler runtime.

Do not deploy a reclaiming allocator into the Samhus compiler simply by
freeing memory on rebind or block exit: the present IR does not encode
sufficient ownership and escape information to prove it safe.
