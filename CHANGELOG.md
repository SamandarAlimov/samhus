# Samhus changelog

**Archive of prior prototype iteration labels only.** They were not
official Samhus releases. On 2026-11-06 the repository switched to the
unreleased `0.0.0.dev0` packaging placeholder; no official `0.0.1` has
been approved or tagged. Future changes are tracked by Git commits and
measured engineering milestones rather than incrementing a pseudo-version.

## Unreleased research — local String store SSA-like graph

- Added verified Value IR overlay identifying deterministic local String
  store versions and per-predecessor PHI edges for branch/loop merges.
- Exposed `samhus ir --local-ssa`, regression tests, README and CI smoke.
- No native retain/drop lowering, final typed SSA, or ownership guarantee.

## Unreleased research — lexical String lifetime analysis

- Added read-only lexical binding identity and scoped cleanup obligations
  over verified CFG Value IR, including nested shadowing and early returns.
- Computes monotone may-reaching String assignments across branches and loops
  and reports potential owner joins without claiming SSA or safety.
- Tests cover rebinds, shadowing, stable branches, loop backedges and
  escaping return aliases. No executable releases or ABI decision.

## Unreleased research — read-only String ownership obligations IR

- Added verified Value IR overlay with String create/borrow/retain/transfer
  and candidate drop events, plus explicit blockers to executable lowering.
- Exposed `samhus ir --ownership`, with a re-derived report verifier,
  CLI regressions and interpreter/VM differential checks.
- No backend codegen or automatic release of memory. The owned C11 runtime
  continues to be a separate manual experiment.

## Unreleased research — independent refcounted C11 String API

- Added a manual C11 owned UTF-8 runtime with explicit retain/drop,
  code-point slices retaining their backing allocations, concatenation,
  and last-reference memory reclamation.
- Added a 1 MiB concurrently live payload limit and strict UTF-8 validation.
- Added 12 regression cases compiling and executing independent C11 programs
  on the cross-platform CI matrix.
- This runtime is not integrated with native Value IR, does not guarantee
  arbitrary C handle safety, and is not a permanent memory-model decision.

## Unreleased research — native String arena content reuse

- Added a bounded 4096-slot direct-mapped intern cache in the native
  concat arena, reusing identical UTF-8 result storage on cache hits.
- Full hash + byte comparisons preserve correctness under hash collisions.
- Prior String views survive cache replacement; novel results still consume
  arena bytes until process exit. No GC, heap or general reclamation.
- Added long-loop memory-pressure, collision and Unicode differential tests.

## Unreleased research — bounded native String concat

- Value IR -> C11 supports String + String using an opt-in 8 MiB static arena.
- Checked cumulative budget, stable immutable views; no malloc/free or GC.
- Added cross-backend Unicode, loop, call, indexing and exhaustion tests.
- No approved memory model, FFI, native ABI or official release.

## Unreleased research — length-tracked native UTF-8 String views

- Bounded `String[Int]` Unicode code-point indexing on borrowed static literals.
- C11 pointer+byte-length view, checked index errors and safe view returns.
- Length-aware equality/print/len; Unicode differential tests and native smoke.
- No heap, concatenation or permanent ownership decision; still 0.0.0.dev0.

## Unreleased research — borrowed native UTF-8 literal Strings

- Static-lifetime UTF-8 `String` literals, locals, returns and typed calls.
- Unicode codepoint len, content equality, println; strict octal C escaping.
- Rejects NUL, oversized literals and dynamic String operations.
- No heap/GC/FFI, no final memory model, no 0.0.1 version bump.

## Unreleased research — native typed functions and guarded recursion

- Typed Int/Bool parameters and Int/Bool/Unit return values on native IR.
- Function prototypes, forward and recursive calls with call-local state.
- CFG-edge lexical scope analysis for early returns.
- 128-frame call guard; builtin invocation step counting.
- Native/VM differential regressions and recursive function binary smoke.
- Still unreleased 0.0.0.dev0, no official 0.0.1.

## Unreleased research — scoped locals and loops in native Value IR

- Int/Bool local variables, lexical shadowing, assignment and nested while.
- Native 100000-step TICK limit prevents infinite source loops from hanging.
- New scope/loop regression cases and cross-platform native binary smoke.
- No general functions, native types, ownership or 0.0.1 release.

## Unreleased research — independent tiny Value IR -> C11

- Separate native code generator from Value IR producer IDs and PHI edge moves.
- Checked Int64 and Bool/if/short-circuit subset; unsupported features rejected.
- `emit-ir-c` and `native-ir` CLI plus VM-to-native cross-platform tests.
- No full-language native equivalence or release version increase.

## Unreleased research — Value IR stack graph (no version bump)

- Named evaluation-stack producers/uses and PHI nodes at CFG merges.
- CLI `ir FILE --values`, with optional `--optimize` for inspection.
- Verified reconstructed graph and cross-engine branch/loop regression.
- Not full typed SSA, native codegen or a 0.0.1 release.

## Unreleased research — verified IR literal folding

- Opt-in local constant folding for bounded pure expressions.
- IR optimize CLI and optimized VM execution, with differential tests.
- Runtime errors and source-location semantics preserved; no native IR backend.

## Unreleased research — CFG stack-value type analysis

- Experimental data-flow annotations for stack and locals in CFG IR.
- New `samhus ir FILE --types` command; type hints are conservative.
- No native compiler, sound typed SSA, or release version changes.

## Unreleased research — control-flow IR (no version bump)

- Added CFG middle-end: basic blocks, branch edges, entry state verification.
- Unreachable block pruning; VM lowering and IR inspection CLI.
- Differential conformance and malformed IR regression tests.
- Native still AST-based; this is not typed SSA.

## Unreleased research — version policy correction & local modules

- Reset package metadata and CLI version to 0.0.0.dev0, not a released 0.0.1.
- Added experimental local multi-file import/linking on both Python backends,
  source diagnostics, path/cycle limitations, typechecking and native C11 subset.
- Git commit history remains authoritative; previous 0.0.x names below
  are research iteration labels, not genuine published releases.

## Historical research iteration 0.0.10 — 2026-11-06 (experimental)

- Bounded exact Decimal and explicit rounding/division helpers.
- Result[T] typed Ok/Err helpers and JSON parse failure capture.
- Tree/VM tests, generated cases and cross-platform smoke commands.
- Native Decimal/Result and production safety are not implemented.

## 0.0.9 — 2026-11-06 (experimental)

- Finite Float, exponent literals, mixed Int/Float arithmetic and to_float.
- Explicit Null distinct from Unit; is_null helper.
- JSON Float/Null support, strict nonfinite and division checks.
- Cross-backend tests, AST/formatter and CI integration.

## 0.0.8 — 2026-11-06 (experimental)

- Immutable Map[String,T], map_set, map_has, map_keys, len and indexed access.
- Strict JSON parse/encode bridge, explicit unsupported Float errors.
- Static typechecker, parser, VM, verifier, formatter and regression updates.

## 0.0.7 — 2026-11-06 (experimental)

- Immutable List literals, nested List[T], index and bounds checks.
- len(List), append(List, item), deep equality and friendly printing.
- Tree/VM bytecode and static checker integration, generated tests.
- Native C11 remains a deliberately limited subset.

## 0.0.6 — 2026-11-06 (experimental)

- Added restricted C11 native compilation backend and standalone programs.
- New commands: emit-c and native with -o output.
- Explicit type requirements and checked Int64 overflow behavior.
- Native executable tests including 100 deterministic arithmetic cases.
- Cross-platform native build smoke, documentation and safety limitations.

## 0.0.5 — 2026-11-06 (experimental)

- Typed core builtins for assertions, text length, string conversion,
  and strict JSON syntax validation as an AI workflow building block.
- Shared runtime behavior and opt-in static checker signatures.
- Cross-backend tests for results, errors and invalid JSON inputs.
- Documented combined systems/AI product requirements and quality gates.

## 0.0.4 — 2026-11-06

- In-memory bytecode compiler and independently implemented stack VM.
- New run --backend vm and disasm CLI options.
- Control-flow bytecode verification for stack and scope invariants.
- Differential regression suite including 600 generated program cases.
- Installable local CLI package; 6-environment GitHub Actions matrix.
- Benchmark harness comparing prototype interpreter and VM; not C++ parity.

## 0.0.3 — 2026-11-06

- Experimental static type annotations: Int, String, Bool, Unit, Any.
- Opt-in static checker and runtime enforcement of explicit annotations.
- New CLI commands: typecheck, ast, fmt, and run --typecheck.
- Deterministic formatter with protection against comment loss on --write.
- Expanded tests and CI smoke checks for typed programs.
- Documentation of static analysis limits, design governance and roadmap.

## 0.0.2 — 2026-11-04

- Functions, parameters, return, recursion, while.
- Local scopes and execution-step limits.
- 51 passing tests at end of this milestone.

## 0.0.1 — 2026-11-04

- Initial Python lexer, parser, runtime and CLI.
- 23 passing tests.

The .sahu extension and license have not been approved.
