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

## 2026-11-06 — experimental Map and JSON (0.0.8)

- Added Map literals, checked key indexing and persistent map updates.
- Added BUILD_MAP bytecode with verifier stack accounting.
- Extended runtime, type checker and formatter to recursive Map/List values.
- Implemented strict size/depth-limited JSON conversion for AI data workflows.
- Added regression suite including 100 generated Map lookup scenarios.
- Experimental native C11 deliberately rejects Map and JSON APIs.
- No inference, schemas, Float or native Map support claimed.

## 2026-11-06: finite Float and explicit Null (0.0.9)

- Implemented Float lexer/parser/runtime/VM and static checking.
- Preserved Int/Int truncated division; mixed numeric arithmetic returns Float.
- Added to_float and is_null helpers with source-positioned errors.
- JSON now handles finite Float and maps null to distinct Null.
- AST exporter, formatter and a new 60-test differential suite were added.
- Added 200 generated numeric/JSON cases; initial CI 432/432 succeeded
  on 6 jobs across Windows, macOS and Linux on Python 3.11/3.13.
- Native C11 remains experimental and does not accept Float/Null.

## 2026-11-06 — Decimal and Result prototype (0.0.10)

- Added exact base-10 Decimal runtime, bounded inputs/results and no silent rounding.
- Added explicit decimal_round and decimal_div modes with validation.
- Added Result[T] Ok/Err runtime values and try_json_parse for safe JSON errors.
- Added 75 regression methods on Decimal/Result and generated scenarios;
  first full CI gate 507 tests after explicit numeric rounding changes.
- Native C11 remains incompatible; no complete memory-safety or financial audit.

## 2026-11-06 — engineering priority reset and input hardening

- Added input size, token count, number/string size and expression depth guards.
- Added adversarial regression cases (malformed random inputs and tree/VM parity).
- Established a staged plan emphasizing compiler correctness, safety, native
  independence, AI/data integration and developer ecosystem over version counts.
- No native parity, security audit or final architecture decision claimed.

## 2026-11-06 — version correction and multi-file build foundation

- Corrected package and CLI identifier to `0.0.0.dev0` (unreleased).
- Archived earlier research labels without claiming any official release.
- Created release requirements and a regression check for version identity.
- Added local module AST parsing and confined relative file loading.
- Integrated multi-file linking with checker, interpreter, VM, AST/disassembly
  and restricted native C compilation.
- Added import validation, symlink/path traversal defense, cycle detection,
  module and source budgets, and regression/CI examples.
- The system still has no package manager, namespace/visibility model,
  full native semantic parity or security certification.

## 2026-11-06 — CFG IR, no version bump

- Added IR with named basic blocks, explicit jump edges and entry states.
- Reused verifier control-flow analysis to check IR/bytecode consistency.
- Added unreachable block removal, IR-to-bytecode lowering and CLI display.
- IR backend uses existing VM, not independent native compilation.
- Added malformed IR and 300 deterministic differential workload cases.
- C11 native remains AST-based; typed SSA is NOT implemented.
- Kept unreleased 0.0.0.dev0 identifier, no 0.0.1 yet.

## 2026-11-06 — conservative CFG value type propagation

- Added `samhus/typed_ir.py` and optional `ir FILE --types` inspection.
- Source checker runs first; CFG stack/local hints propagate through
  loops, branches, calls, collections and numeric operations.
- Unknown or conflicting types widen conservatively to Any.
- 34 new unittest methods cover flow, CLI, errors and 150 generated cases.
- This is NOT SSA, sound type checking, compiler independence or native IR.
- Prototype remains 0.0.0.dev0; no official release or version bump.

## 2026-11-06 — opt-in IR constant folding (unreleased)

- Added `samhus/optimizer.py` with bounded pure binary/unary literal folds.
- Added verified IR `--optimize` inspection and VM execution option.
- Kept runtime diagnostics, function effects, short-circuit operations
  and statement step budgets unchanged.
- Added 39 test methods and 200 generated differential programs.
- Native backend remains AST-based; no performance or typed-SSA claim.
- Package remains `0.0.0.dev0`, no official release.

## 2026-11-07 (Asia/Tashkent) — Value IR stack graph prototype

- Added `samhus/value_ir.py` for named stack-produced values and their uses.
- Added PHI records for stack-slot merges at short-circuit branches/loops.
- Added value-graph reconstruction verifier and CLI `ir FILE --values`.
- Value IR can inspect CFG before/after the opt-in literal optimizer.
- Added 36 regression methods including 180 generated branch/loop programs.
- **Not** full SSA: mutable locals remain opaque; no native code generation.
- Kept `0.0.0.dev0`, with no official 0.0.1 release.

## 2026-11-07 (Asia/Tashkent) — independent tiny Value IR C11 backend

- Added `samhus/native_value_ir.py`, independent of AST-to-C emitter.
- Lowered stack Value IR producers and PHI edge moves to C11 temporaries.
- Used checked 64-bit arithmetic helpers, explicit type/operation rejection.
- Added `emit-ir-c`, `native-ir`, and native sample with 26 regression methods.
- Added VM-native executable comparisons and six-platform smoke test.
- Scope intentionally limited: pure Int/Bool/if/short-circuit; no locals,
  loops, user functions, strings or full-language native parity.
- Package remains `0.0.0.dev0`, official 0.0.1 not released.
