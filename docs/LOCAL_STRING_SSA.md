# Local String store SSA-like IR (research-only)

Samhus remains unreleased at `0.0.0.dev0`; the source extension
`.sahu` is provisional. This pass is **not full SSA**, a memory
ownership model, a verified dominance graph, or production compiler code.

The `samhus/local_ssa_ir.py` analyzer uses verified stack Value IR
plus the established lexical String lifetime facts to assign each local
String parameter/declaration/assignment a deterministic, distinct
store version. It resolves each `LOAD` to the version available along
that CFG path, and records explicit per-predecessor PHI sources where
different versions meet at a branch/loop header.

For a program like:

    fn main()->Unit {
        var s:String="initial"
        if true {s="left"} else {s="right"}
        println(s)
    }

the report identifies distinct stores for `initial`, `left`,
and `right`, plus a PHI for the load following the join.

## Try it

    python -m samhus ir examples/native_value_ir_concat.sahu --local-ssa
    python -m samhus ir examples/native_value_ir_concat.sahu --local-ssa --optimize
    python -m unittest discover -s tests -v

Tests cover branch merges, nested shadowing, loop backedges, recursive
function signatures, early returns, stable determinism and tampered
report rejection.

## Safety and scope

- This is a **read-only store data-flow graph**, not native instructions.
- SSA IDs represent **lexical local storage versions**, not distinct
  heap allocations or proof that all references to an object are gone.
- PHI is a data-flow merge marker; its operands do **not** indicate
  retain/drop operations or guarantee source lifetime.
- A fixed-point computes loop reaching versions from verified CFG edges.
  The verifier re-derives this graph; no independent dominance proof.
- Retain/drop placement, exception cleanup, function ABI, concurrency
  and FFI remain unspecified. The separately tested C11 refcounted
  String runtime remains **unconnected** to this IR.
- `safe_to_lower` is **always false**; production correctness or safety
  is not established by having a named store/PHI graph.

Next steps: independent dominance checks, explicit edge-specific lifetime
effects and a reviewed ownership-aware calling convention before considering
lowering to the standalone experimental C11 owned String library.
