# Samhus String ownership on CFG edges — research-only

This experimental overlay is **read-only**. Its edges and cleanup
obligations are **not executable retain/drop instructions**, an approved
memory model, an owned/borrowed calling convention, or a security proof.
Samhus remains unreleased at `0.0.0.dev0`; `.sahu` is provisional.

## What the analysis records

`samhus/ownership_edge_ir.py` consumes validated Value IR,
scoped String lifetime information and local String SSA store versions
(with independent CFG dominance checks). It derives:

- `FORWARD_STRING_LOCAL`: the same lexical String store is live across
  a CFG edge with unchanged version.
- `PHI_EDGE_OWNER_OBLIGATION`: one predecessor edge forwards its
  own SSA store into the destination PHI (including while backedges).
  PHI is a value join, not a guaranteed ownership transfer.
- `REPLACE_OWNER_OBLIGATION`: old and new local String store versions
  for a mutable assignment. A real runtime would need retain-before-drop
  when values alias, but that is NOT performed.
- `SCOPE_EXIT_RELEASE_OBLIGATION`: candidate cleanup of a local String
  when control leaves its lexical scope normally.
- `RETURN_RELEASE_OBLIGATION`: candidate cleanup of active local
  Strings on explicit or implicit returns. Returned stack aliases must
  be preserved before any future release.
- `UNMODELED_EXCEPTION_CLEANUP`: operations that may fail while
  String locals are live, without a modeled exception/unwind CFG.
  The report does NOT track every live expression temporary.

These obligations identify *where further engineering is required*,
not where it is safe to insert a free or decrement.

## Inspect

    python -m samhus ir examples/native_value_ir_concat.sahu --edge-owners
    python -m samhus ir examples/native_value_ir_concat.sahu --edge-owners --optimize
    python -m unittest discover -s tests -v

`--edge-owners` is mutually exclusive with `--types`, `--values`,
`--ownership` and `--local-ssa`. Reports are re-derived from verified
Value IR to detect tampering; neither this nor CFG dominance checking
establishes heap-owner semantics or guarantees safe cleanup.

The separate [stack temporary report](TEMPORARY_LIFETIMES.md) now
identifies candidate nested-expression stack unwind gaps and lexical
uses. It does not reconcile those with actual heap ownership.

## Outstanding proof obligations

1. Establish precise heap-owner identity and temporary stack lifetime.
2. Define borrowed/owned parameter, result and FFI contracts.
3. Model exceptional/control transfer and cleanup ordering.
4. Prove PHI edge moves, scope exit, and self-assignment retain/drop
   rules preserve aliases without double-free or use-after-free.
5. Test sanitizers and stress random CFG programs; review concurrency.
6. Obtain an explicit owner decision on any permanent memory model.

The independent C11 refcount runtime remains **unconnected** to the
Samhus source compiler; the current native Value IR backend still uses
its bounded process-lifetime String arena.
