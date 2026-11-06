# Security threat model — first research draft

Samhus is not a sandbox for untrusted code. Python-hosted interpreter and
bytecode VM share the Python process; native C generation depends on the
installed trusted C toolchain. These facts are release blockers for hostile
multi-tenant execution.

## Assets at risk

- Source and derived code; credentials in build environments.
- Host memory/CPU, filesystem, network and process privileges.
- Model provider secrets, API tokens, structured AI responses.
- Compiler artifact integrity and dependency provenance.

## Threats and current limits

- Very long code/literals: basic lexer size limits; not a heap quota.
- Deep nesting: parser depth guard; not a complete stack bound.
- Infinite loops: step budget; no wall-time or operating-system limit.
- Memory exhaustion: List/Map/JSON guards; no global allocation budget.
- Arbitrary host exceptions: partial regression coverage; full fuzz pending.
- Unsafe native FFI: not yet designed or proven safe.
- Malicious package: registry/signing and dependency policy absent.
- Model prompt injection/untrusted AI output: JSON syntax is not trust.

## Security acceptance requirements

1. All public parsing APIs report controlled diagnostics for invalid text.
2. Native artifacts do not expose unsafe capabilities implicitly.
3. Explicit resource boundaries for compilation AND runtime, not source only.
4. Threat-model review and fuzzing are required before service execution.
5. Use vetted cryptographic dependencies; do not invent cryptographic algorithms.
6. Independent audits and responsible disclosure precede production claims.

Prototype safety tests are in tests/test_input_hardening.py.
