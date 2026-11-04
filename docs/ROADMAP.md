# Samhus research roadmap (proposed, not committed)

## Milestone 0 — executable bootstrap: complete

Lexer, parser, evaluator, CLI, examples, tests and GitHub Actions.
Current interpreter is experimental and intentionally narrow.

## Milestone 1 — language design review: pending

- Define the specific real-world problem that Samhus must solve.
- Compare proposed grammar, ownership and types with existing languages.
- Obtain explicit owner decisions for the .sahu extension and licensing.
- Draft a stable, testable conformance specification before 1.0 claims.

## Milestone 2 — stronger semantics: partially prototyped

- [x] Multiple functions, parameters and return expressions.
- [x] Local lexical scopes, recursion and while loops.
- [x] Execution budget and call-depth diagnostics.
- [ ] Decide and prototype a static type system.
- [ ] Add user-defined data structures and modules.
- [ ] Build deterministic semantics and compatibility tests.
- [ ] Evaluate error recovery and source spans for tooling.

## Milestone 3 — compilation experiments: not started

Benchmark interpreter vs bytecode, WebAssembly and native compilation.
Evaluate LLVM integration, ABI/runtime costs and cross-platform feasibility,
and select architecture only after technical evidence and owner approval.

## Milestone 4 — developer experience: not started

Propose formatter, LSP, package manager, project templates, documentation,
security review and pilot Alsamos SDK integrations.

Dates, budgets, production-readiness and future platform targets are **not** approved by this roadmap.
