# Samhus

**Samhus** is an experimental programming language project by **Alsamos**.

> **Status: `0.0.1` bootstrap proof of concept — not a production compiler or a finalized language specification.**

We have started with a tiny, executable interpreter to validate syntax and semantics before committing to a long-term compiler architecture. The prototype is implemented in Python using only the standard library; this is a reversible research choice, **not** a decision about the language's final implementation. The file extension `.sahu` is provisional until explicitly approved by the project owner.

## Try it

Requires Python **3.11+**. From the repository root:

```bash
python -m samhus run examples/hello.sahu
python -m samhus check examples/basics.sahu
python -m unittest discover -s tests -v
```

Expected output:

```text
Assalomu alaykum, Alsamos!
```

Example file (`examples/hello.sahu`):

```text
fn main() {
    let company = "Alsamos"
    println("Assalomu alaykum, " + company + "!")
}
```

## What works today

- Lexer with source-positioned errors, comments and escaped strings.
- Parser for `fn main() { ... }`, `let`, `var`, assignment, `println`, and `if`/`else`.
- Integers, strings, booleans, arithmetic, comparisons, logical expressions and block scopes.
- Runtime diagnostics, `run` and `check` commands, automated unit tests and CI.

**Not yet included:** user-defined functions, modules, floats, static type checking, native compiler, LLVM/Wasm backend, package manager, IDE integration, or security guarantees. Do not use this prototype to execute untrusted code.

## Project governance

- Name **Samhus**: confirmed by project owner.
- Extension **`.sahu`**: proposed; not finalized.
- License/open-source policy: **not decided**. This public repository currently has **no license**, so public visibility does not grant broad reuse rights.
- Syntax, memory management, compiler implementation, platforms, and 1.0 promises remain open design decisions.
- See [DECISIONS](docs/DECISIONS.md), [language draft](docs/LANGUAGE.md), [roadmap](docs/ROADMAP.md), and [agent instructions](AGENTS.md).

Other Alsamos projects are unaffected by this repository.
