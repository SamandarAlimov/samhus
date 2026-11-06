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

## Milestone C — robust language core: not started

- Decide language's real first user problem and define approved semantics.
- Improve static analysis and control-flow inference.
- Explore data structures, modules, error handling and standard library.
- Introduce intermediate representation, diagnostics and conformance
  cases after review.

## Milestone D — compiler backend research: not started

- Compare typed IR, bytecode VM, Wasm and LLVM native backends.
- Benchmark real programs and choose architecture after owner approval.
- Validate memory model, ABI, interoperability and portability.

## Milestone E — developer ecosystem: not started

- Explore package manager, LSP/IDE integration, formatter with comment
  preservation, debugger, release management and security audits.
- Evaluate prototypes with actual Alsamos Mini Apps / Cloud needs.

Open founder decisions: .sahu extension, licensing/open-source model,
production type semantics, compiler architecture, target platforms and
investment/release schedule. No date or budget is committed here.
