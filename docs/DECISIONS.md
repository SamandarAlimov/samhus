# Samhus design decision log

Only owner-approved decisions are final. Technical prototypes are reversible.

| Topic | Status | Detail |
| --- | --- | --- |
| Programming language name | Confirmed | Samhus, selected by project owner. |
| Long-term product objective | Confirmed | Aim for C++-class systems capability, stability and safety alongside Python-class AI productivity; these are goals, not current capabilities. |
| Repository | Confirmed | SamandarAlimov/samhus. |
| Source extension | Pending confirmation | .sahu is proposed and used for experiments. |
| Prototype implementation | Experimental | Python standard-library interpreter. |
| Syntax | Experimental | fn, let/var, if/else, while, return, calls and primitive expressions. |
| Optional type annotations | Experimental | Int, String, Bool, Unit, Any; runtime guards and opt-in typecheck. |
| Static type system | Undecided | Current checker is a conservative prototype only. |
| Safe-core builtins | Experimental | assert, len, str and json_valid are provisional and tested across tree/VM; not approved stable stdlib. |
| Formatting conventions | Experimental | AST formatter; does not preserve comments. |
| Runtime limits | Experimental | Step/call depth ceilings; not a sandbox. |
| Compiler implementation language | Undecided | Python bootstrap does not decide final compiler technology. |
| Bytecode compiler and VM | Experimental | Python-hosted in-memory compilation and VM; not approved as final backend. |
| Bytecode verification | Experimental | Checks internal jump, stack and scope invariants. |
| Experimental C11 native subset | Experimental | Typed, checked signed-64-bit lowering and standalone executable using a C compiler; not full language parity. |
| LLVM/Wasm/native targets | Undecided | No selected production backend architecture. |
| License and open-source policy | Undecided | No LICENSE file; public repo is not automatically open-source. |
| Memory model | Undecided | No approved GC, ownership or manual memory model. |
| Platform priorities | Undecided | Require explicit prioritization. |

To confirm a decision, record the founder's explicit choice, the date,
the rationale, and any compatibility impact. Do not silently promote
prototype behavior into a permanent specification.
