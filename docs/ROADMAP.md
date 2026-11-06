# Samhus engineering roadmap (proposed, not a release commitment)

## Milestone A — executable bootstrap: complete

- Lexer, source-positioned diagnostics, parser, AST and interpreter.
- Variables, basic expressions, control flow, functions, recursion and scopes.
- CLI, execution budgets, examples, CI and regression suite.

## Milestone B — developer foundation: experimental prototype complete

- Optional type annotations on variables and function signatures.
- Opt-in static type checking with documented limitations.
- Runtime type validation for explicit annotations.
- JSON AST inspection and deterministic source formatter.
- CLI integration, compatibility coverage and GitHub CI.

## Owner-directed strategy (2026-11-06)

Samhus must aim for C++-class practical systems capability, stability and
safety **together with** Python-class AI workflow productivity.
Implementation choices remain open. The measurable product requirements and
quality gates are documented in PRODUCT_REQUIREMENTS.md and QUALITY_GATES.md.

## Milestone C — robust language core: partially prototyped

- Decide language's real first user problem and define approved semantics.
- Improve static analysis and control-flow inference.
- [x] Prototype minimal typed safety/AI JSON validation builtins (not a full stdlib).
- [ ] Explore data structures, modules, error handling and standard library.
- Introduce intermediate representation, diagnostics and conformance
  cases after review.

## Milestone D — compiler backend research: partially prototyped

- [x] Create in-memory bytecode compiler, VM and control-flow verifier.
- [x] Differentially compare tree and VM output across hundreds of generated cases.
- [x] Prototype limited C11 lowering, overflow checks and standalone executable.
- [ ] Preserve arbitrary-precision Int semantics in a full native backend.
- [ ] Compare typed IR, Wasm and LLVM native backends.
- Benchmark real programs and choose architecture after owner approval.
- Validate memory model, ABI, interoperability and portability.

## Milestone E — developer ecosystem: not started

- [x] Installable local Python-hosted CLI package.
- [x] CI on Ubuntu, Windows and macOS with Python 3.11 and 3.13.
- [ ] Explore package manager, LSP/IDE integration, formatter with comment
  preservation, debugger, release management and security audits.
- Evaluate prototypes with actual Alsamos Mini Apps / Cloud needs.

Open founder decisions: .sahu extension, licensing/open-source model,
production type semantics, compiler architecture, target platforms and
investment/release schedule. No date or budget is committed here.


## Data collection milestone — experimental 0.0.7

- [x] Immutable List literals and recursive List[T] annotations in tree/VM.
- [x] Bounds-checked indexing, persistent append, deep equality.
- [x] Differential regression and generated indexing tests.
- [ ] Full native collections with identical runtime semantics.
- [ ] Maps, records, structured JSON, tensor libraries and concurrency.

## Structured data milestone (experimental 0.0.8)

- [x] Immutable Map[String,T], nested typechecking and functional updates.
- [x] Bounded JSON parse/encode and explicit unsupported Float diagnostics.
- [x] Tree/VM differential tests and generated Map lookup cases.
- [ ] Proper Float/Null, schema validation, streaming JSON and Records/Struct.
- [ ] Native backend collection semantics and independent security review.

## Numeric and nullable data (experimental 0.0.9)

- [x] Float literals, binary64 arithmetic and conversion.
- [x] Null distinct from Unit; JSON fractional/null roundtrip.
- [x] Formatter, AST and cross-backend regression coverage.
- [ ] Decimal for money, Option/Result types, structured errors.
- [ ] Full native numerical type equivalence and security review.

## Exact numbers and managed failures (0.0.10 experimental)

- [x] Bounded exact Decimal from String/Int; no implicit binary Float import.
- [x] Explicit rounding and division policies with scale/mode tests.
- [x] Typed Result[T], safe JSON error capture, regression coverage.
- [ ] Native Decimal and Result parity, Option, full error propagation.
- [ ] Independently reviewed accounting algorithms and memory model.

## Forward engineering work

See ENGINEERING_MASTERPLAN.md for the active dependency-based plan.
Prototype feature-count growth is subordinate to correctness, independent
native compilation, a sound typed subset, security and developer adoption.
