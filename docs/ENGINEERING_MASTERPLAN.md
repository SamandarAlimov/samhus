# Samhus — engineering master plan

Status: proposed engineering program, NOT a release commitment or final language spec.
Owner authorizes proactive planning, implementation and testing toward a
world-class systems+AI language. Compiler backend, memory model, extension,
licensing and irreversible language/ABI decisions remain open pending review.

## North-star product

An independent language that can compile portable performant applications,
has safe-by-default semantics, precise static/runtime diagnostics, a
well-equipped AI/data ecosystem, and a productive beginner-to-expert workflow.
No claim of being faster/safer than all languages is valid without evidence.

## Pillars and acceptance signals

| Pillar | Evidence required |
| --- | --- |
| Core correctness | language specification, reference evaluator, conformance tests, stable diagnostics |
| Safety | threat model, ownership/GC evaluation, explicit unsafe boundary, independent audits |
| Native performance | binary independent of Python, codegen IR, cross-platform ABI, matched benchmarks |
| Data/AI | structured data, typed schemas, streaming models, tensor interfaces, local inference |
| Ergonomics | formatter, LSP, debugger, package manager, helpful errors, offline docs |
| Ecosystem | FFI, governance, reproducible packages, semver, community examples |

## Priority 0 — research bootstrap hardening (NOW)

- [x] Two Python-hosted execution paths and cross-backend regression.
- [x] Restricted C11 standalone executable experiment.
- [x] Data prototypes: List, Map, JSON, Float, Null, Decimal and Result.
- [x] Source/parser length and nesting guards and adversarial regression.
- [ ] Audit the AST, lexer and parser for host exceptions and denial-of-service.
- [ ] Establish stable source corpus, diagnostic fixtures and versioned semantics.
- [ ] Add CI fuzz/property testing and hard limits for output/memory/time.
- [ ] Remove unsafe implicit behaviors and collect all cross-backend mismatches.

Exit gate: zero known crashing compiler inputs in documented regression
corpus; no discrepancy concealed; all CI targets pass.

## Priority 1 — language and type-system foundation

- [ ] Review syntax, lexical rules, scope, effect and error semantics.
- [ ] Define structured Record/Struct and explicit nullable/Option types.
- [ ] Define generics, traits/interfaces, immutable vs mutable collection rules.
- [x] Prototype local multi-file imports under a confined project root.
- [ ] Design proper namespaces, package boundaries and dependency versioning.
- [ ] Move from optional checker to sound typed subset with clear Any boundary.
- [ ] Define numeric precision, conversion and overflow policies.

Exit gate: independently reviewed language reference with machine-readable
conformance cases on all supported reference backends.

## Priority 2 — native compiler architecture (critical path)

- [ ] Evaluate LLVM, portable C, and custom IR prototypes on real workloads.
- [ ] Choose an owner-reviewed intermediate representation and codegen backend.
- [ ] Compile all approved primitive and collection operations correctly.
- [ ] Define runtime/ABI, garbage-collection vs ownership tradeoffs, and FFI.
- [ ] Produce Python-independent compiler distribution (runtime independence
      of binaries is already demonstrated only for the limited C11 subset).
- [ ] Integrate sanitizer, fuzzing and reproducible cross-target builds.

Exit gate: standalone native apps for a defined language subset with measured
correctness, throughput, memory and startup against comparable C++/Rust.

## Priority 3 — batteries-included standard library

- [ ] File, path, process, IO, networking, TLS and HTTP APIs.
- [ ] Cryptography via vetted audited primitives; no homegrown ciphers.
- [ ] Data formats: strict JSON schemas, CSV, protobuf and binary formats.
- [ ] Safe task, cancellation, async and concurrency primitives.
- [ ] Security: capabilities, permissions, sandboxed environments where possible.

Exit gate: independently deployed backend, CLI and GUI applications with tests.

## Priority 4 — first-class AI and scientific workflows

- [ ] Native tensor + device abstraction; explicit CPU/GPU execution.
- [ ] Python and C/C++ interoperability with explicit ownership boundaries.
- [ ] Local AI runtimes and remote model APIs with streaming and timeouts.
- [ ] Typed AI structured-output contracts and schema validation.
- [ ] Build realistic multi-agent and inference examples and benchmark them.

Exit gate: real reproducible AI example working locally without Alsamos Cloud
dependency; honest interoperability and performance comparisons to Python.

## Priority 5 — developer release and ecosystem

- [ ] Single install command; signed official artifacts and offline docs.
- [ ] LSP, VS Code support, formatter, diagnostics, debugger, profiler.
- [ ] Package manager, verified dependency graph and vulnerability process.
- [ ] Browser playground; examples, tutorials and accessible onboarding.
- [ ] Compatibility policy, release notes, public issue templates.
- [ ] Independent developers complete usability study.

Exit gate: users build and deploy useful projects without maintainer help.

## Release policy

The current installable prototype advertises only `0.0.0.dev0`.
`0.0.1` will be the first authorized research release after meeting
RELEASE_POLICY.md acceptance criteria. Do not auto-bump versions.
Native alpha requires
Python-independent runtime and reproducible compiler tests. 0.9.9 is NOT
reserved as a shortcut to maturity: it needs all release readiness gates
defined in QUALITY_GATES.md. Version labels do not certify security.

## Working method

1. Inspect latest main, AGENTS.md and previous CI results.
2. Select highest-risk blocker, define acceptance examples BEFORE editing.
3. Make a reversible change with regression and differential tests.
4. Run six-job CI, investigate all failures; fix before reporting green.
5. Update spec and engineering log; publish the exact commit and limits.
6. Never make or claim irreversible founder decisions without clear approval.

## Important open decisions

- Final source extension (.sahu currently provisional).
- Open-source license and governance model; public repository alone is not a license.
- Memory model, native codegen backend and FFI policy.
- Platform prioritization, production type semantics, standard ABI and module system.

Other Alsamos repositories are out of scope. No autonomous background work
is implied by this document: implementation occurs when the assistant is
actively invoked through available tools or an explicitly configured agent.
