# Samhus 0.0.4 — stack-bytecode architecture

**Experimental implementation document, not a final ABI or compiler spec.**

## Pipeline

~~~text
Source (.sahu provisional)
  -> lexer -> recursive-descent parser -> Program AST
                  |                  |
                  |          opt-in type checker
                  v
          bytecode compiler
                  |
      internal control-flow verifier
                  |
          VM executes bytecode
~~~

The old tree-walking interpreter remains available as an independent
reference implementation. It is used to verify behavior against the VM.

## Internal opcode families

| Family | Instructions |
| --- | --- |
| Constants and variables | PUSH, LOAD, ASSERT_FRESH, DECLARE, ASSERT_MUTABLE, ASSIGN |
| Stack and calls | POP, CALL, RETURN, RETURN_VOID |
| Computation | UNARY, BINARY |
| Lexical scope | SCOPE_IN, SCOPE_OUT |
| Control flow | JUMP, BRANCH_FALSE, KEEP_FALSE, KEEP_TRUE, EXPECT_BOOL |
| Resource accounting | TICK |

Each instruction stores a source token with line and column information
for error diagnostics. Function bytecode is represented as immutable
dataclass values in memory; this is **not a portable bytecode file format**.

### Example CLI

~~~bash
python -m samhus disasm examples/bytecode.sahu
python -m samhus run examples/bytecode.sahu --backend tree
python -m samhus run examples/bytecode.sahu --backend vm
~~~

### Verification

The verifier examines reachable control-flow paths and rejects:
- Unknown internal opcodes.
- Stack underflow, incompatible stack heights at merge points.
- Invalid jump destinations.
- Unbalanced scope nesting and malformed calls.
- Stack leftovers on function return.

It does **not** validate hostile serialized code, prove type safety,
check resource exhaustion, or establish that language semantics are correct.

### Execution behavior

- Each called function has its own call frame and local scopes.
- Calls can be recursive and respect a depth limit.
- Short-circuit boolean expressions compile to conditional jumps.
- If and while control flow compile into explicit branch targets.
- Explicit type annotations are enforced on variables, parameters
  and results at runtime.
- The interpreter and VM share the current parser and selected value
  representations; their execution loops and binary operations are separate.

### Differential testing

The regression suite compares tree and VM output and user-visible error
messages on successful and failing programs, including recursion, nested
scopes, typed declarations, short-circuit logic, control flow and budgets.
A deterministic generated corpus tests 600 additional program instances.

This catches a range of compiler discrepancies but does **not** prove that
either engine is completely correct or memory-safe.

## Limitations

- Python-hosted, not native/LLVM/Wasm.
- Bytecode has no stable serialization or compatibility version.
- No optimizer (constant folding, SSA, inlining, escape analysis, etc.).
- No user-defined types, modules, package system, general I/O or async.
- VM performance is not representative of a future native compiler.
- Neither execution path is a sandbox for untrusted source code.

## Next architecture decisions requiring owner approval

Choose the production language's semantics, type and memory model, and
target platforms based on measured requirements. Bytecode prototype choices
are not permanent commitments.
