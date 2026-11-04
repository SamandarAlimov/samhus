# Samhus

**Samhus** is an experimental programming language project by **Alsamos**.

> **Status: 0.0.2 bootstrap interpreter, not a production compiler or finalized language specification.**

The current prototype runs simple Samhus programs with functions and control flow.
It is implemented using the Python standard library so the language design can be evaluated and changed cheaply.
This is **not** a commitment to use Python in the eventual compiler.
The source-file extension **.sahu is provisional**, not a finalized standard.

## Quick start

Requires **Python 3.11+** and no additional dependencies.

~~~bash
git clone https://github.com/SamandarAlimov/samhus.git
cd samhus
python -m samhus run examples/hello.sahu
python -m samhus run examples/functions.sahu
python -m samhus check examples/basics.sahu
python -m unittest discover -s tests -v
~~~

Expected hello-world output:

~~~text
Assalomu alaykum, Alsamos!
~~~

## Samhus source example

The file examples/functions.sahu contains a runnable version of the following program:

~~~text
fn factorial(n) {
    if n <= 1 {
        return 1
    }
    return n * factorial(n - 1)
}

fn main() {
    println(factorial(5))
    var i = 0
    while i < 3 {
        println(i)
        i = i + 1
    }
}
~~~

Output: 120, 0, 1, 2 (one value per line).

## Available prototype features

- Lexer with source-positioned diagnostics, // comments, and escaped strings.
- Multiple named functions, parameters, return statements, calls, recursion, and main entry point.
- Local lexical variable scopes; immutable let and mutable var.
- Statements: declarations, assignment, function calls, if/else and while.
- Values: arbitrary-precision integers, strings, and booleans.
- Arithmetic, integer division (truncated toward zero), comparisons, logic with short-circuit behavior, string concatenation.
- CLI run and syntax-only check; built-in println(value) for output.
- A bounded step counter and function-call depth to catch common runaway programs.
- GitHub Actions and regression tests for Python 3.11 and 3.13.

To limit steps when running a program:

~~~bash
python -m samhus run examples/functions.sahu --max-steps 1000
~~~

**Important limits:** check parses syntax; it does not check types. The interpreter is not a sandbox and **must not** be used with untrusted programs. There are no type annotations, static type checker, imports, floating point numbers, native compilation, WebAssembly backend, package manager, or IDE tooling yet. Function parameters are immutable and variables belong to the current function or nested block. These are experimental semantics, subject to owner-approved language design.

## Repository layout

| Path | Purpose |
| --- | --- |
| samhus/lexer.py | Tokenizer |
| samhus/parser.py | Syntax tree and parser |
| samhus/runtime.py | Experimental interpreter |
| samhus/__main__.py | CLI |
| examples/ | Runnable programs |
| tests/ | Regression tests |
| docs/LANGUAGE.md | Current grammar and semantics |
| docs/DECISIONS.md | Confirmed versus pending decisions |
| docs/ROADMAP.md | Non-binding technical milestones |
| docs/ENGINEERING_LOG.md | Implementation activity log |
| AGENTS.md | Rules for agents and contributors |

## Governance and intellectual property

- **Samhus** is the founder-approved language name.
- **.sahu** is a proposed extension used for experiments; **approval is pending**.
- **No license has been selected.** This public GitHub repository currently has **no LICENSE file**, so public visibility is not a grant of broad open-source reuse rights.
- The long-term syntax, memory model, compiler implementation, platforms, commercial policy, and release plan have not been finalized by the owner.
- This research repository does not modify the existing Alsamos Web/Flutter projects or live backend.

Read the [language draft](docs/LANGUAGE.md) and [decision log](docs/DECISIONS.md) before treating a prototype choice as a language standard.
