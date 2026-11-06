# Samhus engineering log

## 2026-11-04 — bootstrap milestone (0.0.1)

- Initialized the repository with README, rules and architecture notes.
- Added Python standard-library lexer, parser, evaluator and CLI.
- Added basic expressions, variables, if/else and text output.
- Added 23 regression tests and a GitHub Actions job on Python 3.11 / 3.13.

## 2026-11-04 — language prototype increment (0.0.2)

- Added multiple named functions, calls, parameters, return expressions,
  recursion, forward references and local function scoping.
- Added while loops, a runtime execution-step budget and call-depth checks.
- Preserved the legacy parse(source) entrypoint; added parse_program(source).
- Added 24 new tests for function semantics, recursion, scopes, malformed
  code and bounded execution.
- GitHub Actions completed successfully: **47 tests on Python 3.11 and 3.13**.
- Follow-up: CLI flag for bounded steps, documentation and an additional
  runnable functions example were added in the subsequent documentation commit.

Neither the syntax nor the .sahu suffix is an approved long-term standard.


## 2026-11-06 — developer foundation, prototype 0.0.3

- Added optional Int, String, Bool, Unit and Any annotations
  on function parameters, return signatures and local declarations.
- Added opt-in static type checker for scopes, arity, operators,
  assignments and return paths, with dynamic Any fallback.
- Added runtime type enforcement for explicit annotated values.
- Added typecheck, run --typecheck, ast, and fmt CLI commands.
- Added JSON AST inspection and deterministic AST source formatting.
- Added protection against fmt --write destroying source comments.
- Added typed examples, extensive regression tests and GitHub CI smoke checks.
- The initial 121-test version passed on Python 3.11 and 3.13.
- The documentation and decision log still identify unresolved decisions.

This is not a production compiler, finalized semantics or security sandbox.


## 2026-11-06 — compiler and multi-platform foundations, prototype 0.0.4

- Implemented independent in-memory stack-bytecode compiler and VM.
- Added explicit control flow for if/else, while, recursion and short-circuit
  boolean logic, with source-positioned diagnostics and typed guards.
- Added control-flow verification of reachable instructions, jump targets,
  stack consistency and lexical scopes.
- Added differential tests including 600 deterministic generated programs;
  regression suite expanded to 177 unittest methods.
- Integrated VM selection and disassembly in CLI; kept tree interpreter
  as default for compatibility.
- Added local editable CLI packaging, 3 OS x 2 Python cross-platform CI
  matrix and a lightweight two-backend benchmark harness.
- Initial packaging CI uncovered a build dependency problem on clean runners;
  switched to standard isolated build and reran the complete matrix.
- Latest six CI jobs (Ubuntu, macOS, Windows; Python 3.11 and 3.13):
  all completed successfully at this milestone.
- No native backend, portable artifact format or C++/Python language parity
  has been claimed.


## 2026-11-06 — combined systems reliability + AI productivity direction

- Recorded the owner's explicit objective to seek both C++-class practical
  systems capability/safety and Python-class AI productivity.
- Kept memory model, native backend, syntax and licensing undecided.
- Added experimental shared builtin signatures/runtime support for
  assert(Bool), len(String), str(Any) and json_valid(String).
- Added typecheck integration and differential tests for tree and VM,
  including deliberate failures and source error positions.
- Hardened json_valid to reject nonstandard NaN/Infinity JSON constants.
- Added PRODUCT_REQUIREMENTS and QUALITY_GATES with measurable evidence
  required for actual competitiveness; did not claim parity or 0.9.9.

## 2026-11-06 — experimental native C11 compiler (0.0.6)

- Added strict typed-subset source-to-C11 generator with source diagnostics.
- Introduced checked signed-64-bit arithmetic to prevent C signed overflow
  in supported numeric operations; explicitly documented the difference
  from the tree/VM arbitrary-precision integer semantics.
- Added emit-c and native CLI commands, with a user-installed C compiler.
- Generated executables run without Python. The compiler still uses Python.
- Added recursion, loops, Unicode, function call evaluation order, overflow
  and 100 deterministic arithmetic conformance examples.
- Added native smoke in cross-platform CI and documented exclusions.
- C11 is experimental, not a final compiler/ABI decision.


## 2026-11-06 — immutable List foundation (0.0.7)

- Added List literal and indexing AST, nested List[T] type spelling.
- Added immutability via host tuple values and runtime typed element checks.
- Added BUILD_LIST/INDEX bytecode and verifier state accounting.
- Added list length/append, safe index errors, Unicode string indexing.
- Added deep equality with strict Bool-vs-Int distinction.
- Added 54 new List tests and a 100-case generated indexing corpus.
- First test gate: 305/305 passed on 6 cross-platform CI jobs.
- Native C11 remains incompatible and rejects unsupported List.
