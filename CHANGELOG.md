# Samhus changelog

Prototype iterations, not stable releases.

## 0.0.6 — 2026-11-06 (experimental)

- Added restricted C11 native compilation backend and standalone programs.
- New commands: emit-c and native with -o output.
- Explicit type requirements and checked Int64 overflow behavior.
- Native executable tests including 100 deterministic arithmetic cases.
- Cross-platform native build smoke, documentation and safety limitations.

## 0.0.5 — 2026-11-06 (experimental)

- Typed core builtins for assertions, text length, string conversion,
  and strict JSON syntax validation as an AI workflow building block.
- Shared runtime behavior and opt-in static checker signatures.
- Cross-backend tests for results, errors and invalid JSON inputs.
- Documented combined systems/AI product requirements and quality gates.

## 0.0.4 — 2026-11-06

- In-memory bytecode compiler and independently implemented stack VM.
- New run --backend vm and disasm CLI options.
- Control-flow bytecode verification for stack and scope invariants.
- Differential regression suite including 600 generated program cases.
- Installable local CLI package; 6-environment GitHub Actions matrix.
- Benchmark harness comparing prototype interpreter and VM; not C++ parity.

## 0.0.3 — 2026-11-06

- Experimental static type annotations: Int, String, Bool, Unit, Any.
- Opt-in static checker and runtime enforcement of explicit annotations.
- New CLI commands: typecheck, ast, fmt, and run --typecheck.
- Deterministic formatter with protection against comment loss on --write.
- Expanded tests and CI smoke checks for typed programs.
- Documentation of static analysis limits, design governance and roadmap.

## 0.0.2 — 2026-11-04

- Functions, parameters, return, recursion, while.
- Local scopes and execution-step limits.
- 51 passing tests at end of this milestone.

## 0.0.1 — 2026-11-04

- Initial Python lexer, parser, runtime and CLI.
- 23 passing tests.

The .sahu extension and license have not been approved.
