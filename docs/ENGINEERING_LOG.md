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
