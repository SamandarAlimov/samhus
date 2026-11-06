# Samhus Value IR — experimental stack-value SSA-like analysis

Status: research-only, still `0.0.0.dev0`; NOT released as 0.0.1.
No memory-model, runtime, native backend or language syntax decision is final.

## Motivation

The CFG and typed IR layers previously tracked instruction order, stack
height, and conservative type *hints*. Value IR makes each stack-result
definition and its uses explicit, with stable identifiers per instruction.

## Architecture

Source -> AST -> verified stack bytecode -> CFG IR -> conservative type
flow -> Value IR with def/use relationships and stack PHI nodes.

Value IR is an analysis overlay. It is not currently used by VM or C11
native code generation. Running the sample still uses the existing VM.

## Commands

    python -m samhus ir examples/short_circuit_values.sahu --values
    python -m samhus ir examples/short_circuit_values.sahu --values --optimize
    python -m samhus run examples/short_circuit_values.sahu --backend ir --typecheck

The `--values` and `--types` viewers are alternatives; `--values` may be
combined with the existing opt-in `--optimize` CFG pass.

## Representation

`ValueOp` describes an existing bytecode instruction, its ordered input
value IDs, optional output ID, output type hint, token and bytecode offset.
`ValuePhi` records one named stack-slot result and a (predecessor, value)
pair for each incoming CFG edge. A phi can appear at short-circuit
`&&`/`||` merges, including inside loops.

`ValueBlock` describes entry/exit symbolic stack IDs, predecessors,
successors, phis and operations. `ValueFunction` and `ValueProgram`
preserve the original CFG and function boundaries.

Example of the intended meaning (IDs vary by source layout):

    %b0002.phi0: Bool = phi(b0001:%b0001.v3, b0004:%b0004.v2)

Only *evaluation-stack* values use SSA-like IDs. Locals and function
parameters still use opaque LOAD/DECLARE/ASSIGN operations and are not
converted into SSA values. No full phi elimination, dominance analysis,
alias tracking, ownership analysis or typed SSA code generation exists.

## Verification

1. Verify the original CFG's jump, stack-height and scope invariants.
2. Construct stable IDs for instruction-produced stack values.
3. At blocks with multiple predecessors, reserve a PHI for every
   incoming stack slot, including backedges in loops.
4. Ensure all incoming references correspond to the predecessor's
   symbolic outgoing stack. Re-derive the graph and reject tampering.
5. Use the conservative typed IR pass for output type hints; Any means
   analysis cannot demonstrate a precise type.

These steps do not prove arbitrary host bytecode is safe and do not
establish a sound static type system. A full value IR verifier still
requires independent SSA dominance and effect-aware semantics.

## Safety boundaries and next steps

- No changes to runtime output or error order in this pass.
- No native binary is generated from Value IR.
- Current optimizer still operates on CFG stack bytecode, not Value IR.
- Phi nodes are descriptive and are not lowered to native registers yet.
- Next: separate typed operations with explicit effects; define dominance
  rules, SSA for mutable locals, and independently tested value lowering.
- Benchmark a standalone IR-native subset before making performance claims.

Validation: `python -m unittest discover -s tests -v` and
`tests/test_value_ir.py`; see GitHub Actions for six-OS/Python jobs.
