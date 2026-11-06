# Samhus — experimental programming language

**Samhus** is a new programming-language research project for **Alsamos**.

> **Prototype 0.0.3** — a Python-based research interpreter with optional
> type annotations, static analysis and developer tooling.
> **Not** a production language, native compiler, security sandbox, or final specification.

The name **Samhus** is confirmed by the project owner. The file extension
**.sahu is provisional** and the license remains **undecided**.

## Run Samhus today

Requires **Python 3.11+**. No extra dependencies.

~~~bash
git clone https://github.com/SamandarAlimov/samhus.git
cd samhus
python -m samhus run examples/hello.sahu
python -m samhus run examples/functions.sahu
python -m samhus run examples/typed.sahu --typecheck
python -m samhus typecheck examples/typed.sahu
python -m unittest discover -s tests -v
~~~

Example:

~~~text
fn factorial(n: Int) -> Int {
    if n <= 1 {
        return 1
    }
    return n * factorial(n - 1)
}

fn main() -> Unit {
    let company: String = "Alsamos"
    println(company)
    println(factorial(5))
}
~~~

Output:

~~~text
Alsamos
120
~~~

## Commands

| Command | Behavior |
| --- | --- |
| python -m samhus run FILE | Interpret a trusted local program. |
| python -m samhus run FILE --typecheck | Run the experimental static analyzer before interpreting. |
| python -m samhus run FILE --max-steps 1000 | Set an execution step budget, not a sandbox. |
| python -m samhus check FILE | Syntax-only check, kept compatible with previous releases. |
| python -m samhus typecheck FILE | Opt-in static checker, accepts dynamic Any values. |
| python -m samhus ast FILE | Dump the full AST as JSON for experiments and tooling. |
| python -m samhus fmt FILE | Output canonical source to stdout without changing the file. |
| python -m samhus fmt FILE --check | Exit non-zero if source differs from formatter output. |
| python -m samhus fmt FILE --write | Rewrite source only if it contains no comments; comments are not preserved by the formatter. |
| python -m unittest discover -s tests -v | Run regression tests. |

The formatter adds parentheses around compound expressions.
It is deterministic/idempotent but does **not** preserve comments; therefore
the CLI refuses to overwrite files containing comments. Review formatter
stdout before editing files manually.

## Features in this prototype

- Lexer, recursive-descent parser, source-location errors and AST model.
- Named functions, parameter passing, forward references, recursion, return.
- Lexical scopes, let/var bindings, if/else, while.
- Integers, strings, booleans, arithmetic, comparisons, logic, short-circuiting.
- Optional Int, String, Bool, Unit, Any annotations on
  declarations and function parameters, plus -> Type return annotations.
- Conservative opt-in static type checking; type annotations are also
  checked at runtime for function arguments/results and variable values.
- Developer tools: typed example, syntax checker, JSON AST viewer, safe
  canonical formatter, test suite and CI on Python 3.11/3.13.

## Important limitations

1. Static checking is **not sound or complete**: Any/unannotated inputs can
   conceal errors until runtime; it does not guarantee program termination.
2. The prototype has no imports/modules, classes/structs, arrays, floats,
   async functions, native executable output, Wasm/LLVM compiler, package
   registry or IDE extension.
3. Resource and recursion limits are **not** a security boundary. Do not
   run untrusted Samhus programs.
4. Syntax, memory model, license, compiler implementation language, source
   extension and target platforms have not been finalized.

## Documentation and governance

- [Language reference (experimental)](docs/LANGUAGE.md)
- [Type checker design and caveats](docs/STATIC_TYPES.md)
- [Decision log](docs/DECISIONS.md)
- [Roadmap](docs/ROADMAP.md)
- [Engineering log](docs/ENGINEERING_LOG.md)
- [Agent/contributor rules](AGENTS.md)

No LICENSE file has been added: a publicly visible repository is not the
same thing as an open-source grant. Only confirmed founder decisions are
recorded as such; prototype choices remain reversible. Other Alsamos repos
and the live backend have not been modified.
