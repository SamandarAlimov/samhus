# Samhus — product requirements: reliable systems + AI development

## Owner-stated product objective (2026-11-06)

The owner wants Samhus to combine two ambitions:
1. **C++-class systems capability:** stable long-lived software, performance,
   low-level control where needed, and rigorous safety.
2. **Python-class AI productivity:** quick experimentation, model interfaces,
   data handling, modern AI workloads and access to useful libraries.

Samhus should aim to make the best practical trade-offs of these areas rather
than copying C++ syntax or executing Python behind a different syntax.

This objective is confirmed; **the implementation choices are not**.

## Important engineering distinctions

- C++ is mature and often fast; it does **not** provide memory safety by default.
  For Samhus, "C++-class" does NOT mean copying C++ memory-unsafety.
- Python is strong in AI due largely to NumPy/PyTorch and ecosystem
  integrations. A "Python-like" syntax alone cannot reproduce these benefits.
- No real compiler can guarantee zero bugs, zero vulnerabilities or universal
  superiority over every mature language on every workload.
- Runtime quality, safe-by-default design, stable interfaces, software audits
  and long-term maintenance must be measured separately.

## Non-negotiable product-level requirements (targets, not implemented claims)

| ID | Requirement | Objective acceptance evidence |
| --- | --- | --- |
| SYS-01 | Native executable output | Program runs without Python installed |
| SYS-02 | Predictable error handling | Documented language semantics and consistent diagnostics |
| SYS-03 | Safe-default execution | Memory-management model reviewed, unsafe escape hatches explicit |
| SYS-04 | C/C++ interoperability | Tested ABI boundary and ownership/error conversion |
| SYS-05 | Cross-platform products | Native test builds on supported OS/CPU targets |
| REL-01 | Robustness | Conformance, differential, fuzz, sanitizer and long-running tests |
| REL-02 | Stability | Compatibility policy, standard library versioning and regression suite |
| REL-03 | Secure dependencies | Provenance, signed artifacts when feasible, vulnerability response |
| AI-01 | Structured data | JSON, schemas, collections and precise error diagnostics |
| AI-02 | AI interoperability | Model APIs, streaming, embeddings/tensor libraries and Python ecosystem bridge |
| AI-03 | AI developer experience | Local workflow, typed SDK, examples, reliable package management |
| AI-04 | Offline AI workflows | Optional local inference integrations with explicit CPU/GPU requirements |
| DX-01 | Accessible entry point | Installer, CLI, examples, IDE diagnostics, docs and playground |
| DX-02 | Ecosystem portability | Samhus code does not require an Alsamos account or cloud |
| PERF-01 | Repeatable benchmarks | Fixed workloads compared with native C++ and CPython/Python 3.13 |
| PERF-02 | Transparent trade-offs | Public results show where Samhus is slower, consumes more memory or lacks features |

## Proposed technical experiments (NOT final decisions)

- **Memory safety:** compare an ownership/borrowing approach, managed memory
  approach, and hybrid approaches with explicit unsafe FFI. Select only after
  use-case benchmarks and security review.
- **Code generation:** compare LLVM native, simpler native C/IR bootstrap,
  and WebAssembly; consider complexity, portability and runtime costs.
- **AI bridge:** compare a native Python FFI bridge, a plugin protocol, and
  C ABI calls into model runtimes. Do not assume importing Python packages
  is the same as native Samhus execution.
- **Type system:** evaluate an ergonomic typed core with explicit dynamic
  boundaries for JSON/AI outputs; do not silently trust model responses.
- **Concurrency:** benchmark event-driven async, message passing, thread
  models and structured concurrency with measurable data-race protection.

## Two realistic capability demonstrations

**Systems:** compile a small CPU-intensive service or CLI to a standalone
binary, use C libraries through a checked ABI, run crash/security tests and
publish latency, throughput, startup and memory measurements against matching
C++ versions.

**AI:** parse structured model output, validate a declared schema, run an
inference client (remote or local), stream responses, convert errors to
well-defined results, and publish a minimal reproducible installation.

Neither demonstration currently exists in full.

## Architecture/governance boundary

The above are product requirements, not approval to pick a permanent memory
model, backend, source extension, open-source license, syntax or platform
priority. Only the founder can finalize those decisions. See DECISIONS.md.
