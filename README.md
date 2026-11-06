# Samhus — Alsamos programming-language research project

**Samhus** is Alsamos's founder-approved programming-language name.
The current software is **prototype 0.0.9**, not a production-ready language
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

There is **no PyPI package publication or official 0.9.9 release**.
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

## Experimental AI/safety building blocks (0.0.5)

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

New in 0.0.6: a strictly annotated subset of Samhus is compiled to C11 and then
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
- Data structures, modules/packages, exceptions/results, richer types.
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


## Experimental immutable List support (0.0.7)

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

## Finite Float and explicit Null (experimental 0.0.9)

The tree interpreter and bytecode VM support finite binary64 Float,
numeric Int/Float operations, to_float, and separate Null/is_null.
JSON fractional values map to Float, JSON null maps to Null rather
than Unit. Float arithmetic is approximate, NOT precise financial math.
Native C11 remains limited and rejects these new types.

    python -m samhus run examples/float_null.sahu --backend tree --typecheck
    python -m samhus run examples/float_null.sahu --backend vm --typecheck

See [Float and Null experimental semantics](docs/FLOAT_NULL.md).
