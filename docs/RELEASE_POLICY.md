# Samhus release policy — official 0.0.1 has NOT shipped

The owner clarified on 2026-11-06 that previously advertised prototype
versions 0.0.1–0.0.10 were premature. Those names remain historical
research-iteration references in Git/CHANGELOG, **not releases**.

The Python-distributed bootstrap now uses `0.0.0.dev0` as an internal,
PEP-440-compatible placeholder. It does not represent a stable language
version. All subsequent development remains in Git without version bumps.

## Minimum requirements before considering first official 0.0.1

1. A coherent and reviewed small language specification: grammar,
   evaluation order, types, numeric behavior, module boundaries and errors.
2. A useful multi-file project compiled/checked/run with a documented
   installation and reproducible CI example.
3. A documented compatibility matrix: interpreter, VM and native subset;
   unsupported features are explicitly rejected, never silently changed.
4. No known blocking compiler crashes in the documented adversarial suite;
   six cross-platform CI jobs green and source-positioned error diagnostics.
5. A reproducible release artifact, changelog, test evidence and
   dependency/license inventory. The open-source/license decision remains
   reserved to the owner and must be explicitly resolved before distribution.
6. Founder explicitly authorizes the release name and requirements.

This is a proposed research milestone, NOT production readiness.
A genuine production/systems/AI release requires substantially stronger
evidence: memory model, complete native semantics, FFI and security design,
benchmarks, developer tooling and independent review.

**Rule:** do not auto-increment the package version for a code commit,
a new builtin, a passing test count, or a planning milestone.

The `.sahu` extension is still provisional; no stable file extension,
C ABI, ownership model, compiler backend or license is silently approved.
