# Samhus ownership obligations IR — read-only experiment

Status: **research-only analysis** at unreleased `0.0.0.dev0`.
This is NOT a verified borrow checker, final memory model, SSA, escape
analysis, reference-counting codegen, ABI contract or compiler sandbox.

The experimental `samhus/ownership_ir.py` reads verified stack Value IR
and reports candidate lifetime operations for static UTF-8 String values:

- `BORROW_STATIC_LITERAL` — no dynamic allocation for a literal.
- `ALLOCATE_CONCAT_RESULT` — concatenation would create a new owner.
- `RETAIN_PARENT_FOR_SLICE` — indexed views must keep backing storage live.
- `RETAIN_LOCAL_ON_LOAD` — local reads need retain/borrow rules.
- `TRANSFER_OR_RETAIN_FOR_LOCAL` — variable initialization or replacement.
- `TRANSFER_RETURN_TO_CALLER` — returns require a verified ownership move.
- `BORROW_CALL_ARGUMENT` — calls need an explicit parameter lifetime contract.
- `DROP_UNUSED_TEMP` — evaluation-stack results discarded by POP.
- `PHI_EDGE_OWNER` — future String joins need correctly staged edge transfers.

### Scoped local lifetime facts (new research layer)

`samhus/local_lifetime_ir.py` resolves lexical String bindings into
stable `local:<DECLARE offset>` slots, including nested shadowing and
function parameters. It adds the following candidate obligations:

- `BIND_STRING_LOCAL`: a String value is stored in a new lexical binding.
- `READ_STRING_LOCAL_STORE`: a local String read and the known may-reaching
  declaration/assignment versions.
- `REPLACE_STRING_LOCAL_OWNER`: a mutable String local is overwritten.
  A future runtime must retain the incoming alias *before* dropping an old
  owner, if aliases overlap.
- `RELEASE_STRING_AT_SCOPE_EXIT`: scope exit encounters a live String local.
- `RELEASE_STRING_AT_RETURN`: return bypasses ordinary scope-exit markers,
  so surviving String locals need explicit cleanup after protecting any
  returned aliases.
- `JOIN_STRING_REACHING_STORES`: branch/loop flow joins different reaching
  String stores to the same lexical binding.

The data-flow computes **may-reaching store sets**, not local-variable SSA
value identities or precise refcounts. Each loop is iterated to a finite
fixed point. These events describe possible cleanup locations, **not safe
drop instructions**: exceptional paths, escaped aliases, parameter ownership,
temporaries and call ABI remain unproven.

Every operation is a **requirement marker, not an executable instruction**.
`safe_to_lower` is always false, even for trivial programs, because
current Value IR does not model exceptional cleanup, local-variable SSA,
accurate temporary lifetimes, aliasing or scope-exit releases.

Usage (the `.sahu` extension remains provisional):

    python -m samhus ir examples/native_value_ir_concat.sahu --ownership
    python -m samhus ir examples/native_value_ir_concat.sahu --ownership --optimize
    python -m unittest discover -s tests -v

The report is re-derived from verified Value IR in `verify_ownership_ir`
to reject tampered event inventories. This is integrity checking, **not**
an independently proven semantic verifier.

The separate `runtime/owned_string.{h,c}` has a manually managed 1 MiB
live-byte budget and real last-owner reclamation, but is **not invoked**
by Samhus source compilation. The current native Value IR backend still
uses its 8 MiB process-lifetime arena.

## Blockers before executable ownership lowering

1. Introduce mutable local SSA or a precise local-lifetime data-flow model.
2. Specify move/retain/drop semantics at all branches, loop backedges and
   PHI edge merges, including repeated aliases.
3. Prove temporary and local cleanup on early returns and exceptional exits.
4. Define borrow/owned calling convention and foreign-function boundaries.
5. Exercise runtime safety with sanitizer-supported native C builds plus
   randomized, Unicode and recursion differential tests.
6. Obtain explicit owner approval before standardizing memory/ABI semantics.

No existing Samhus language program or native executable behavior changes
in this milestone.
