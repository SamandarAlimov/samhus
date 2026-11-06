# Conservative stack type-flow prototype — unreleased Samhus

This layer supplements the existing control-flow IR with a lightweight
forward data-flow analysis of expression stack values and local variable
types. It is NOT typed SSA, a sound whole-program type system, a new
native backend or a proof of memory safety.

## Example

    python -m samhus ir examples/control_flow_ir.sahu --types

The command first runs the opt-in source TypeChecker. If it accepts the
program, it builds verified CFG IR and propagates stack and local type
hints through the reachable instructions. At control-flow merges, if
a type is not the same along both paths, the hint widens to Any.

Type hints include Int, Bool, String, Float, Decimal, Null, Unit,
List[T], Map[String,T], Result[T], and Any. The analyzer handles scoped
variables, function parameters and signatures, return/branch instructions,
short-circuit operators, recursive calls and loops.

## Safety and correctness boundaries

- Type hints are metadata. They do NOT change runtime behavior.
- Unknown values use Any. The source checker is conservative but not sound,
  particularly at dynamic JSON/function call and Any boundaries.
- No independent inference of generic trait bounds or flow-based null
  narrowing is currently implemented.
- Analyzer must converge to a fixed point; malformed CFG states raise
  BytecodeValidationError. The existing IR verifier still checks stack
  height and scope nesting separately.
- Code is first generated as stack bytecode, not source-typed SSA.
- The C11 native backend still consumes AST and has incomplete Samhus
  semantics; typed IR does NOT feed the native compiler yet.
- There is no stable IR serialization, ABI, memory model or portable
  artifact. Running arbitrary untrusted source is NOT safe.

## Verification

    python -m unittest discover -s tests -v
    python -m samhus ir examples/control_flow_ir.sahu --types
    python -m samhus ir examples/modules/main.sahu --types
    python -m samhus run examples/control_flow_ir.sahu --backend ir --typecheck

Future work: a typed, effect-aware IR with explicit values, phi/merge
semantics, sound typed subset and independently validated native backend.

The repository remains unreleased (0.0.0.dev0); no official 0.0.1.
