# Samhus — Alsamos programming-language research project

**Samhus** is Alsamos's founder-approved programming-language name.
The current software is **unreleased research snapshot (`0.0.0.dev0`)**, not a production-ready language
or an implementation comparable in completeness to C++ or Python 3.13.

A restricted third path can now produce standalone native C11 executables via a system C compiler. The compiler itself still needs Python and this does not support the full Samhus grammar.

Two Python-hosted execution paths remain available for the experimental grammar:

1. **Tree interpreter:** directly evaluates the parsed syntax tree.
2. **Stack bytecode compiler + VM:** compiles parsed code to in-memory
   bytecode instructions, checks control-flow invariants, then executes
   them using a separate Python-hosted virtual machine.

Both use Python as their host. The VM is **not native compilation**, and the
language still needs modules, collections, a production type specification,
an extensive standard library, native/Wasm backends, tooling and hardening.

## No release version yet

The `0.0.0.dev0` identifier is an **internal Python packaging placeholder**,
not the version of a complete Samhus language or a publicly released product.
Historical `0.0.1` through `0.0.10` labels below refer to previous
**research commits only**, not approved releases. We do **not** increment
the package/language version for every added feature. The first `0.0.1`
tag is reserved until the gates in [Release policy](docs/RELEASE_POLICY.md)
are verified and authorized. The existing Git history is preserved.

## Tiny native Value IR backend — experimental

An **independent Value IR -> C11 code generation path** is available
for a restricted typed Int64/Bool subset with `if/else`, short-circuit
booleans, scoped `let`/`var` variables, `while` loops, `println` and `assert`.
It emits PHI edge moves,
uses checked signed-64-bit helpers and produces Python-independent
executables via an external C compiler. General user functions,
Float, String, Map/List, Decimal and Result are **not supported**.
There is a fixed 100000-step native loop/statement budget, but no OS sandbox.

    python -m samhus emit-ir-c examples/native_value_ir.sahu
    python -m samhus native-ir examples/native_value_ir.sahu -o native-demo
    python -m samhus native-ir examples/native_value_ir_locals.sahu -o native-loops

This does not mean full language native compatibility or C++ performance.
See [native Value IR limits](docs/NATIVE_VALUE_IR.md).

## Stack-value IR with PHI joins (experimental)

An **analysis-only Value IR** now gives evaluation-stack values stable
definition IDs, tracks their instruction uses and records explicit
stack PHI nodes at control-flow merges (e.g. short-circuit booleans).
Mutable local variables are **not** SSA and the native backend does
**not** consume these nodes. This is not a fully native/typed SSA compiler.

    python -m samhus ir examples/short_circuit_values.sahu --values
    python -m samhus ir examples/short_circuit_values.sahu --values --optimize

Details: [Value IR boundaries](docs/VALUE_IR.md).

## Opt-in CFG IR constant folding

The experimental optimizer folds bounded, pure literal expressions and
removes unused literal values **only within a basic block**. It keeps
source TICKs, function calls, branching and runtime error behavior.
No native or speed superiority is claimed.

    python -m samhus ir examples/control_flow_ir.sahu --optimize
    python -m samhus run examples/control_flow_ir.sahu --backend ir --optimize --typecheck

See [optimizer design and limits](docs/IR_OPTIMIZATION.md).

## Conservative type-flow IR

Run `python -m samhus ir examples/control_flow_ir.sahu --types` to
inspect inferred stack-value and local variable types at each reachable
CFG instruction. This uses the existing source typechecker and widens
unresolved types to Any; it does not implement typed SSA, native codegen
or a sound static type system.

Read [the typed IR analysis limitations](docs/TYPED_IR.md).

## Validated control-flow IR experiment

An intermediate control-flow representation (CFG IR) now splits VM
bytecode into basic blocks with explicit branch edges and verified
stack/scope entry states. It can compact unreachable blocks, then
lower back to VM bytecode. This is not typed SSA or native codegen.

    python -m samhus ir examples/control_flow_ir.sahu
    python -m samhus run examples/control_flow_ir.sahu --backend ir --typecheck

See docs/CONTROL_FLOW_IR.md for accurate limitations.

## Multi-file program prototype

Local modules now work across the file-aware CLI tools and both Python-hosted
execution backends. For example:

```samhus
import "lib/math.sahu"
fn main() -> Unit {
    println(double(21))
}
```

```bash
python -m samhus run examples/modules/main.sahu --backend vm --typecheck
python -m samhus native examples/modules/native_main.sahu -o native-demo
```

Imports are confined to the entry directory, prohibit cycles, and merge
functions into a temporary global namespace. This is NOT a complete module
system. See [experimental module design](docs/MODULES.md).

## Install and try

Requires Python 3.11+.

~~~bash
git clone https://github.com/SamandarAlimov/samhus.git
cd samhus
python -m pip install -e .
samhus --version
samhus run examples/hello.sahu
samhus run examples/bytecode.sahu --backend vm --typecheck
samhus disasm examples/bytecode.sahu
python -m unittest discover -s tests -v
~~~

You can also run without installing:

~~~bash
python -m samhus run examples/hello.sahu --backend vm
python -m samhus run examples/typed.sahu --backend tree --typecheck
~~~

There is **no official Samhus release**, including 0.0.1 or 0.9.9.
The local package name is samhus-prototype to distinguish these experiments
from any future official distribution.

## Long-term Samhus product direction

The founder's goal is **C++-class systems capability, stability and
safe-default behavior alongside Python-class productivity for AI and fast
experimentation**. This is a development objective, NOT a current
performance, memory-safety or ecosystem claim. C++ is not memory-safe
by default; Python's AI strength comes largely from existing libraries.
The accepted implementation approach is still undecided.

Read [Product requirements](docs/PRODUCT_REQUIREMENTS.md) and
[Quality / 0.9.9 evidence gates](docs/QUALITY_GATES.md).

## Experimental AI/safety building blocks (historical research)

The tree interpreter and bytecode VM now both support typed builtins:
assert(Bool), len(String), str(Any) and json_valid(String).
JSON syntax validation rejects malformed JSON and nonstandard numeric
constants; **it does not validate an AI output schema** or connect to
any AI model.

~~~bash
samhus run examples/ai_validation.sahu --typecheck --backend vm
~~~

## Language example

~~~text
fn factorial(n: Int) -> Int {
    if n <= 1 {
        return 1
    }
    return n * factorial(n - 1)
}

fn main() -> Unit {
    println("Alsamos")
    println(factorial(5))
}
~~~

Output:

~~~text
Alsamos
120
~~~

## Experimental native executable backend

Research snapshot: a strictly annotated subset of Samhus is compiled to C11 and then
to a standalone executable using cc/gcc/clang. The output does not need
Python to run. The Samhus compiler itself still needs Python at build time.

~~~bash
samhus emit-c examples/native.sahu > generated.c
samhus native examples/native.sahu -o native-demo
./native-demo
~~~

Native Int in this experiment is checked SIGNED 64-BIT, whereas the existing
tree/VM Int is arbitrary precision. The backend rejects unsupported source,
untyped declarations, and non-supported builtins. It is not a security
sandbox, final ABI or production compiler. See docs/NATIVE_BACKEND.md.

## CLI reference

| Command | Meaning |
| --- | --- |
| samhus run FILE | Run tree interpreter (legacy default) |
| samhus run FILE --backend vm | Run compiled bytecode through VM |
| samhus run FILE --backend vm --typecheck | Opt-in static check then VM execution |
| samhus run FILE --max-steps 1000 | Bound execution steps (not sandboxing) |
| samhus check FILE | Parse syntax only |
| samhus typecheck FILE | Experimental static type check |
| samhus ast FILE | Print JSON syntax tree |
| samhus disasm FILE | Print human-readable bytecode and source positions |
| samhus ir FILE | Inspect validated basic-block control-flow IR |
| samhus run FILE --backend ir | Verify IR, lower it, and execute with existing VM |
| samhus fmt FILE | Print canonical formatting |
| samhus fmt FILE --check | Fail if source is not canonical |
| samhus fmt FILE --write | Rewrite only when no comments would be lost |
| samhus emit-c FILE | Generate research C11 source for strictly typed subset |
| samhus native FILE -o OUTPUT | Build Python-free executable with installed C compiler |

Formatter warning: comments are not preserved by the formatter. To avoid
silently deleting comments, fmt --write refuses files that contain them.

## Validation

- An expanding unittest suite (177 tests at 0.0.4 plus new builtins tests) and a deterministic differential corpus that
  additionally checks 600 generated arithmetic, boolean and loop programs.
- CI tests Python 3.11 and 3.13 on **Ubuntu, Windows and macOS** (6 jobs).
- Each job exercises regression tests, editable CLI packaging, tree/VM runs,
  type checking, bytecode disassembly and a benchmark smoke test.
- Compilation verifies internal bytecode jump targets, stack heights and
  lexical scope consistency before execution.

Check the live GitHub Actions status instead of assuming a green badge:
https://github.com/SamandarAlimov/samhus/actions

## Benchmarking

~~~bash
python scripts/benchmark.py --repeat 5
~~~

This benchmarks two Python-hosted implementations of Samhus; it **cannot**
establish parity with optimized C++ or Python 3.13 language ecosystems.

## Critical outstanding work

- Define and approve stable language semantics and source extension.
- Complete native compiler (LLVM/IR or another backend) beyond the current limited C11 prototype.
- Complete modules/packages, full error propagation, mature data structures and audited type system.
- Static type soundness, memory model, concurrency and system I/O.
- Standard library, debugging/IDE integrations, release management.
- Security review, fuzzing, compatibility and independent benchmarks.

See [Engineering targets](docs/COMPETITIVE_TARGETS.md) for measurable gates.
No version number implies quality or completeness without satisfying them.

## Source and governance

- [Native C11 research backend](docs/NATIVE_BACKEND.md)
- [Bytecode architecture](docs/BYTECODE.md)
- [Experimental language reference](docs/LANGUAGE.md)
- [Static type checker notes](docs/STATIC_TYPES.md)
- [Roadmap](docs/ROADMAP.md)
- [Decision log](docs/DECISIONS.md)
- [Engineering log](docs/ENGINEERING_LOG.md)
- [Changelog](CHANGELOG.md)
- [AGENTS.md](AGENTS.md)

**Samhus** is the confirmed name. **.sahu** is a provisional file suffix
used only for experiments; formal approval is pending. No LICENSE has been
selected, so this public repository is **not automatically open-source**.
Python bootstrapping, VM opcodes, type rules, and target platforms are
reversible research choices, not founder-approved production commitments.

No other Alsamos repository, Superapp or production backend was changed.


## Experimental immutable List support (research)

Samhus now supports nested List[T] annotations, immutable collection
literals, bounds-checked zero-based indexing, len(List) and append(List, value)
that returns a NEW list, leaving the original unchanged. Supported in
tree interpreter and bytecode VM only.

~~~sahu
fn main() -> Unit {
    let scores: List[Int] = [10, 20, 30]
    let updated: List[Int] = append(scores, 40)
    println(updated[2])
    println(len(updated))
}
~~~

Output: 30 and 4.

~~~bash
samhus run examples/lists.sahu --backend tree --typecheck
samhus run examples/lists.sahu --backend vm --typecheck
~~~

The C11 native subset does NOT support List; that path rejects it.
Read [List design and caveats](docs/LISTS.md). No production
generics, tensor API, GPU acceleration or memory-safety claim is made.

## Immutable Map and JSON bridge (0.0.8, experimental)

Samhus now supports Map[String,T] literals, String-key indexing,
map_set, map_has, map_keys and len(Map) in both tree and VM backends.
JSON text can be converted to/from nested immutable Map/List values using
json_parse and json_encode. Unsupported fractional JSON numbers fail
explicitly rather than silently losing precision. Duplicated keys,
invalid input and resource limits generate source-positioned errors.
Native C11 does not support Maps or JSON; this is not production AI tooling.

    samhus typecheck examples/maps_json.sahu
    samhus run examples/maps_json.sahu --backend tree --typecheck
    samhus run examples/maps_json.sahu --backend vm --typecheck

See [Map and JSON limitations](docs/MAPS_JSON.md). This syntax and the
.sahu suffix remain provisional.

## Finite Float and explicit Null (experimental)

The tree interpreter and bytecode VM support finite binary64 Float,
numeric Int/Float operations, to_float, and separate Null/is_null.
JSON fractional values map to Float, JSON null maps to Null rather
than Unit. Float arithmetic is approximate, NOT precise financial math.
Native C11 remains limited and rejects these new types.

    python -m samhus run examples/float_null.sahu --backend tree --typecheck
    python -m samhus run examples/float_null.sahu --backend vm --typecheck

See [Float and Null experimental semantics](docs/FLOAT_NULL.md).

## Exact Decimal and Result[T] experiments

Decimal supports bounded exact base-10 arithmetic from String/Int,
with explicit decimal_round and decimal_div scale/mode; Float conversion
is forbidden. Result[T] offers typed Ok/Err values and try_json_parse
converts JSON decoding errors into inspected Result values.

    python -m samhus typecheck examples/decimal_result.sahu
    python -m samhus run examples/decimal_result.sahu --backend tree --typecheck
    python -m samhus run examples/decimal_result.sahu --backend vm --typecheck

See [Decimal and Result limitations](docs/DECIMAL_RESULT.md).
These are NOT native or audited financial/security primitives.

## Engineering master plan and safety policy

The long-term goal is a native, safe-by-default systems language with
productive AI/data workflows and usable developer tooling. These are
measurable engineering goals, NOT claims of achieved parity with C++, Rust
or Python. Read [engineering plan](docs/ENGINEERING_MASTERPLAN.md),
[threat model](docs/THREAT_MODEL.md), and [input guards](docs/INPUT_SAFETY.md).
Run adversarial tests through the existing cross-platform CI matrix.

## Current release state

**Unreleased `0.0.0.dev0`**, not 0.0.1. The earlier prototype labels
are archived for engineering history, not published versions. The first real
release follows [the release policy](docs/RELEASE_POLICY.md) and must be
explicitly approved.
