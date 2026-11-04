# Samhus design decision log

This file distinguishes **confirmed user decisions** from **reversible prototype choices**.

| Topic | Status | Detail |
| --- | --- | --- |
| Language name | **Confirmed** | Samhus (selected by project owner). |
| Repository | **Confirmed** | SamandarAlimov/samhus. |
| Source extension | **Pending confirmation** | .sahu proposed and used by the prototype for practical testing. |
| Bootstrap interpreter | **Experimental** | Minimal Python standard-library interpreter, easy to replace. |
| Syntax | **Experimental** | fn main(), let, var, println, and if/else for initial validation only. |
| Compiler implementation | **Undecided** | Rust, other languages, and possible LLVM/Wasm backends require technical evaluation. |
| License | **Undecided** | No LICENSE file. Public repository is not automatically open-source. |
| Memory model | **Undecided** | No approved GC, ownership or manual memory model. |
| Platforms | **Undecided** | Future targets must be prioritized and specified. |

To confirm decisions, document the founder's explicit choice, date, rationale, and any impact on compatibility.
