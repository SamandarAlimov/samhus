# Samhus design decision log

Only owner-approved decisions are final. Technical prototypes are reversible.

| Topic | Status | Detail |
| --- | --- | --- |
| Programming language name | Confirmed | Samhus, selected by project owner. |
| Long-term product objective | Confirmed | Aim for C++-class systems capability, stability and safety alongside Python-class AI productivity; these are goals, not current capabilities. |
| Repository | Confirmed | SamandarAlimov/samhus. |
| Source extension | Pending confirmation | .sahu is proposed and used for experiments. |
| Release identity | Owner-directed correction | 0.0.0.dev0 is an internal *unreleased* placeholder; prior 0.0.1–0.0.10 labels were research iterations only, no released Samhus 0.0.1. |
| Local file imports | Experimental | Confined string path imports, flat global function linking. Namespace/package syntax undecided. |
| Prototype implementation | Experimental | Python standard-library interpreter. |
| Syntax | Experimental | fn, let/var, if/else, while, return, calls and primitive expressions. |
| Optional type annotations | Experimental | Int, String, Bool, Unit, Any; runtime guards and opt-in typecheck. |
| Static type system | Undecided | Current checker is a conservative prototype only. |
| List[T] collections | Experimental | Immutable literals, indexing and append on tree/VM; syntax not final, native unsupported. |
| Map[String,T] and JSON | Experimental | Immutable Maps, json_parse/json_encode now with Float/Null; no stable semantics approved. |
| Float and Null types | Experimental | Finite binary64 Float with mixed arithmetic; explicit Null distinct from Unit. No permanent numeric/nullable model selected. |
| Decimal with explicit rounding | Experimental | Exact bounded base-10 arithmetic, explicit half_even/half_up/down modes. No approved financial or precision guarantee. |
| Result[T] values | Experimental | Typed Ok/Err helpers and try_json_parse, not a final language error model. |
| Safe-core builtins | Experimental | assert, len, str and json_valid are provisional and tested across tree/VM; not approved stable stdlib. |
| Formatting conventions | Experimental | AST formatter; does not preserve comments. |
| Runtime limits | Experimental | Step/call depth ceilings; not a sandbox. |
| Compiler implementation language | Undecided | Python bootstrap does not decide final compiler technology. |
| Bytecode compiler and VM | Experimental | Python-hosted in-memory compilation and VM; not approved as final backend. |
| CFG intermediate representation | Experimental | Verified basic-block CFG with VM lowering; not typed SSA, native, or finalized. |
| Stack-value IR with PHI | Experimental | Explicit stack def/use and edge PHIs; mutable locals not SSA, API/ABI not approved. |
| Native C11 from Value IR | Experimental | Restricted checked Int64/Bool/if/locals/while/function codegen with fixed step and call-depth limits; no full language or approved ABI design. |
| Bytecode verification | Experimental | Checks internal jump, stack and scope invariants. |
| Experimental C11 native subset | Experimental | Typed, checked signed-64-bit lowering and standalone executable using a C compiler; not full language parity. |
| LLVM/Wasm/native targets | Undecided | No selected production backend architecture. |
| License and open-source policy | Undecided | No LICENSE file; public repo is not automatically open-source. |
| Memory model | Undecided | No approved GC, ownership or manual memory model. |
| Platform priorities | Undecided | Require explicit prioritization. |

To confirm a decision, record the founder's explicit choice, the date,
the rationale, and any compatibility impact. Do not silently promote
prototype behavior into a permanent specification.

**Research note, not a founder decision (2026-11-07):** the restricted
Value IR-to-C11 backend now uses `const char*` borrowed references to
compiler-created, static-lifetime UTF-8 literals. This does not decide
the Samhus memory/ownership model, or allow pointer-based FFI.

**Research note (2026-11-07, not founder-approved):** native Value IR uses
compiler-managed static UTF-8 storage and bounded borrowed views (data pointer
+ length). This is a reversible internal prototype, **not** the approved
Samhus ownership, borrowing or FFI design.
