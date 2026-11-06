# Samhus experimental IR optimization — pure literal folding

Status: unreleased research prototype (0.0.0.dev0). This is NOT a
typed SSA optimizer, an LLVM backend, or proof of native speed.

## Pipeline

Source files -> AST -> stack bytecode -> verified CFG IR -> opt-in
local literal folding -> CFG verifier -> compact bytecode -> Python VM.

The native C11 backend still compiles AST directly and does not consume
this optimized intermediate representation.

## Commands

    python -m samhus ir examples/control_flow_ir.sahu --optimize
    python -m samhus run examples/control_flow_ir.sahu --backend ir --optimize --typecheck

IR `--types` and `--optimize` are intentionally separate research views.
Attempting `--optimize` with tree/VM backends fails with CLI diagnostics.

## Transformations

- PUSH constant + PUSH constant + pure BINARY becomes PUSH result.
- PUSH constant + pure UNARY becomes PUSH result.
- PUSH constant + POP can be removed when no observable effect occurs.
- Repeated local passes fold adjacent expressions within a CFG basic block.
- Numeric operations use the SAME shared runtime functions as the VM.
- Folded Ints are capped at 4096 result bits; folded strings at 4096 chars.
- User calls, branches, scopes, TICK, memory allocation, collections,
  uncertain values and externally visible operations are NOT evaluated.

## Semantic preservation constraints

Zero division, overflow, illegal numeric combinations and other errors
are deliberately not folded. They remain runtime errors with original
source diagnostics. All control-flow entry stacks and scope states are
re-verified after rewriting. Source TICK instructions remain unchanged;
the execution-step budget is not bypassed.

Optimization is opt-in and deterministic, and should remain idempotent.
No performance claim follows from fewer bytecode instructions alone.
VM execution speed and native performance still need measured benchmarks.

## Remaining gaps

- Typed SSA, phi nodes, alias/lifetime reasoning and full effect analysis.
- Inter-block constant propagation, escape analysis and register allocation.
- Independent native IR code generator and cross-target optimization.
- Fuzzing, formal validation, robust execution resource isolation.

See tests/test_optimizer.py for error preservation, randomized arithmetic
and branch differential comparisons among tree, VM and optimized IR.
