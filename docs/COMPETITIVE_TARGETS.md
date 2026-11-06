# Samhus competitive engineering targets

**Long-term aspiration:** build a mature language usable for real systems,
with quality and capability competitive with established languages. This
document is a target framework, NOT a declaration of parity with C++ or
Python 3.13.

Owner-level goals are now specified more explicitly in [PRODUCT_REQUIREMENTS](PRODUCT_REQUIREMENTS.md)
and [QUALITY_GATES](QUALITY_GATES.md); these do not imply current parity.

## What "competitive" must mean

1. Language correctness: documented semantics, conformance tests,
   independent backend agreement, fuzzing, and bug regression tests.
2. Application capability: modules, collections, generics, errors,
   concurrency, packages, diagnostics and useful standard library.
3. Security: memory model, input validation, audits, vulnerability response
   and explicit boundaries, not vague "zero vulnerabilities".
4. Native performance: actual optimizing native code with reproducible
   workload comparisons, not just Python-hosted bytecode timings.
5. Developer experience: installer, formatter, LSP, debugger, docs,
   dependency registry, compatibility promises and release lifecycle.
6. Platform support: verified Windows, macOS, Linux, WebAssembly and mobile
   targets, not merely CLI execution hosted by Python.
7. Real adoption: pilot projects, public bug reports and maintenance plans.

C++ and Python solve different problems. Benchmark specific workloads with
fixed algorithms, language implementations, optimizations and hardware.

## Stage gates

| Gate | Evidence required | State |
| --- | --- | --- |
| A. Correct bootstrap | Parser, interpreter, tests | Experimental baseline exists |
| B. Independent execution | Bytecode compiler, VM, differential tests | Prototype exists |
| C. Bytecode verification | CFG stack/scope consistency | Prototype exists |
| D. Language substance | Collections, modules, errors, stable types | Not completed |
| E. Native compiler | Machine-code output and optimized builds | Not started |
| F. Production security | Threat model, fuzzing, audits | Not completed |
| G. Complete ecosystem | Stdlib, IDE, packages, deployable apps | Not completed |
| H. Competitive benchmarks | Independent reproducible comparisons | Not completed |

The version number 0.9.9 does not fulfill these gates.

## Benchmark caveat

The local script scripts/benchmark.py compares the tree interpreter and
the bytecode VM **both running on Python** using three workloads. It
validates identical output and prints timings to assist internal
regression analysis. It cannot establish Samhus parity with C++ or CPython.
