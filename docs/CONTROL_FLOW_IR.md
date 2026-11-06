# Experimental Samhus CFG intermediate representation

This is a research compiler middle-end, NOT typed SSA, a final native
compiler, production optimization framework or stable binary IR.

## Compiler pipeline

Source -> Parser AST -> Stack bytecode -> Verified control-flow IR
-> IR verification -> compacted stack bytecode -> Python-hosted VM.

The C11 native backend still uses the AST. It does not consume CFG IR.
The IR execution option uses the existing VM: not a third independent runtime.

## Structure

- BasicBlock stores a label, original offset, ordered instructions,
  successor labels, verified entry stack depth and lexical scope depth.
- FunctionIR stores function name, parameter types, return annotation
  and ordered basic blocks. This is function-level type metadata only;
  individual intermediate values do NOT have assigned static types.
- ProgramIR groups functions and provides a human-readable dump.

Basic blocks split at jump targets and immediately after terminators.
Short-circuit &&/|| branches retain lazy evaluation. Loops and
if/else become explicit control-flow edges.

## Verification

- Bytecode verifier computes stack/scope states on reachable code.
- IR verifier rejects incorrect successor labels, duplicate blocks,
  misplaced terminators, incorrect entry states or invalid signatures.
- Unreachable blocks are omitted by the CFG constructor; this can
  remove dead code after unconditional return/jump.
- Lowered bytecode is independently re-verified before VM execution.
- This transformation is not constant folding, SSA, inlining,
  register allocation or dead-store elimination.

## Try

    python -m samhus ir examples/control_flow_ir.sahu
    python -m samhus run examples/control_flow_ir.sahu --backend tree --typecheck
    python -m samhus run examples/control_flow_ir.sahu --backend vm --typecheck
    python -m samhus run examples/control_flow_ir.sahu --backend ir --typecheck

The sample prints 55 on each route. VM and IR use the same final runtime.

## Missing before a serious native compiler

- Typed, effect-aware, independent language IR.
- Production optimizer and full-semantic native code generation.
- Memory model, FFI, ABI and sound type system.
- Independent fuzzing and benchmark evidence.

All syntax, ABI and source extension choices remain provisional.
Unreleased package version remains 0.0.0.dev0; no official 0.0.1.
