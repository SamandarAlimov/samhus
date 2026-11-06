# Samhus quality and release gates — draft metrics

A version label (including proposed 0.9.9) cannot substitute for evidence.
A release is allowed to claim only what it has actually demonstrated.

## Immediate experimental CI gate (currently reachable)

- Every changed file compiles/imports on all supported Python CI versions.
- 100% existing unit and differential regression tests pass.
- Python-hosted tree interpreter and VM produce equivalent output and
  diagnostics on the regression corpus.
- Cross-platform CLI packaging succeeds on Ubuntu, Windows and macOS.
- Tests exercise new standard-library functions on BOTH backends.
- A regression is not marked fixed unless the failing example is captured.

**This is a prototype quality gate, not a production security gate.**

## Proposed native alpha gate (future)

- Emit standalone binaries for full approved language semantics, not just the restricted C11 subset.
- Build reproducible end-to-end programs without installed Python.
- Verify parser/semantic consistency and predictable error behavior.
- Publish sanitizer and fuzz-testing results, including known limitations.
- Run documented memory/resource stress tests; define cleanup/shutdown rules.
- Document C ABI and platform dependencies.

## Proposed AI alpha gate (future)

- Parse real structured outputs into typed, validated structures.
- Provide a small but reliable HTTP + streaming and JSON toolchain.
- Exercise local and remote inference providers through adapters.
- Demonstrate exception/time-out/retry handling and cancellation.
- Cross-check structured output parsing with malformed/adversarial inputs.
- Provide a minimal end-to-end getting-started guide.

## Proposed 0.9.9 readiness gate (NOT met)

- Owner-approved language semantics and compatibility policy.
- Safe-by-default memory model with a clearly specified unsafe boundary.
- Functional native compiler and verified platform matrix.
- Practical standard library, package management and IDE support.
- Meaningful AI tooling demonstrated independently by developers.
- Serious security process: threat modeling, fuzzing, audit findings tracked.
- Measured startup, latency, throughput, memory and compiler time on matched
  workloads against explicit versions of C++ and Python implementations.
- No *known release-blocking* defects under published severity policy;
  zero-defect or zero-vulnerability guarantees are not credible.
- Reproducible releases, supply-chain checks, documented regressions.

## Proposed benchmark protocol

For every benchmark record:
1. Workload/source and input fixture version.
2. Hardware, CPU/architecture, OS, memory, compiler and runtime versions.
3. C++ compiler flags (including optimization) and exact Python 3.13 build.
4. Warm-up, number of repetitions and variance.
5. Correctness check of outputs first, then speed and memory measurement.
6. Comparative results for at least two relevant workloads; no cherry-picking.
7. Limitations, missing features and failure cases visible with the results.

Do not compare a Python-hosted Samhus VM microbenchmark with optimized
compiled C++ to claim native Samhus speed. The host interpreter dominates
that measurement.

## Explicit nonclaims today

- No complete native machine-code backend; only restricted experimental C11 lowering.
- No defined memory-safety model or verified sandbox.
- No AI inference or model framework integrated into the language.
- No C++ performance parity or Python ecosystem parity.
- No reliable complete feature set for a 0.9.9 release.

Current implementation is an experimental stepping stone.
