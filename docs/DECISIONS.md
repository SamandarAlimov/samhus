# Samhus design decision log

Only owner-approved decisions are final. Technical prototypes are reversible.

| Topic | Status | Detail |
| --- | --- | --- |
| Programming language name | Confirmed | Samhus, selected by project owner. |
| Repository | Confirmed | SamandarAlimov/samhus. |
| Source extension | Pending confirmation | .sahu is proposed and used for experiments. |
| Prototype implementation | Experimental | Python standard-library interpreter. |
| Syntax | Experimental | fn, let/var, if/else, while, return, calls and primitive expressions. |
| Optional type annotations | Experimental | Int, String, Bool, Unit, Any; runtime guards and opt-in typecheck. |
| Static type system | Undecided | Current checker is a conservative prototype only. |
| Formatting conventions | Experimental | AST formatter; does not preserve comments. |
| Runtime limits | Experimental | Step/call depth ceilings; not a sandbox. |
| Compiler implementation language | Undecided | Python bootstrap does not decide final compiler technology. |
| LLVM/Wasm/native targets | Undecided | No selected backend architecture. |
| License and open-source policy | Undecided | No LICENSE file; public repo is not automatically open-source. |
| Memory model | Undecided | No approved GC, ownership or manual memory model. |
| Platform priorities | Undecided | Require explicit prioritization. |

To confirm a decision, record the founder's explicit choice, the date,
the rationale, and any compatibility impact. Do not silently promote
prototype behavior into a permanent specification.
