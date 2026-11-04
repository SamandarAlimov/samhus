# Samhus design decision log

This file distinguishes **confirmed user decisions** from **reversible prototype choices**.

| Topic | Status | Detail |
| --- | --- | --- |
| Language name | **Confirmed** | Samhus (selected by project owner). |
| Repository | **Confirmed** | SamandarAlimov/samhus. |
| Source extension | **Pending confirmation** | .sahu proposed and used by the prototype for practical testing. |
| Bootstrap interpreter | **Experimental** | Minimal Python standard-library interpreter, easy to replace. |
| Syntax | **Experimental** | fn, let/var, if/else, while, return, expression calls, recursion and println; see LANGUAGE.md. |
| Runtime limits | **Experimental** | Interpreter step and call depth ceilings, not a security sandbox. |
| Compiler implementation | **Undecided** | Rust, other languages, and LLVM/Wasm backends require technical evaluation. |
| License | **Undecided** | No LICENSE file; public repository does not automatically grant open-source rights. |
| Memory model | **Undecided** | No approved GC, ownership or manual memory model. |
| Static type system | **Undecided** | No type annotations or static checker in this prototype. |
| Platforms | **Undecided** | Future targets must be prioritized and specified. |

To confirm decisions, document the founder's explicit choice, date, rationale, and any impact on compatibility.
Prototypes must never silently promote an experimental choice to a permanent requirement.
