# String stack temporaries and aliases — read-only research

Status: **experimental** Samhus `0.0.0.dev0`, source extension
`.sahu` provisional, memory/ABI semantics undecided.

`samhus/temporary_lifetime_ir.py` walks verified **Value IR stack
value identifiers**. It records typed String origins:

- `STATIC_LITERAL`: compiler-created String literal, not a heap owner.
- `CONCAT_RESULT`: String addition (new result; exact owner undecided).
- `PARENT_DEPENDENT_VIEW`: Unicode code-point index with a String
  parent that must remain alive in a future owned storage design.
- `LOCAL_LOAD_ALIAS`: local String load tied to a particular
  local-store SSA version, not a newly owned allocation by itself.
- `CALL_RESULT_UNKNOWN_ABI`: a function's String result whose
  owned/borrowed contract is not yet specified.
- `STACK_PHI`: conditional stack result from multiple CFG edges.
  The incoming edge is not an unconditional move or drop.

All String operand uses are recorded, including expression consumption,
String local assignments, returns, calls, unused-call result POP, and
conditional PHI edge forwarding. A `last-operation-use` marker means
only the final **syntactic use in one basic block**: it does not imply
reference uniqueness, last execution, or permission to free memory.

## Incomplete exceptional cleanup

The analyzer replays the evaluation stack and records a
`UNMODELED_STACK_UNWIND` gap whenever a potentially failing operation
is reached with a **non-static String temporary still on the stack**.
This includes nested concatenations, indexed String views, String
function results and String local load aliases. The risk list is a
conservative experiment and not an exhaustive exception semantics
analysis. It does not account for all local-variable owners, callee
failure contracts or complete stack spills. These gaps are blockers,
not executable unwind handlers.

Run:

    python -m samhus ir examples/native_value_ir_concat.sahu --temp-owners
    python -m samhus ir examples/native_value_ir_concat.sahu --temp-owners --optimize
    python -m unittest discover -s tests -v

The report can be verified by deterministic reconstruction from
validated Value IR; this is an integrity check, **not an independent
heap lifetime proof**. The separately tested C11 owned String
runtime remains unconnected to source compilation.

**No automatic retain/drop/free**, no memory model approval, no final
SSA, no allocation reclamation. Every report returns
`safe_to_lower=false`.
