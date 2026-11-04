# Samhus language draft — experimental 0.0.2

These notes describe only the **currently implemented interpreter**.
They are not a founder-approved, stable language specification.

## Grammar sketch

~~~text
program      = function* EOF
function     = "fn" IDENT "(" (IDENT ("," IDENT)*)? ")" block
block        = "{" statement* "}"
statement    = ("let" | "var") IDENT "=" expression ";"?
             | IDENT "=" expression ";"?
             | expression-call ";"?
             | "return" expression ";"?
             | "if" expression block ("else" block)?
             | "while" expression block
expression   = literals, names, function calls, unary and binary operations
~~~

Top-level declarations are functions only. A parameterless fn main() is mandatory,
and function names must be unique. The builtin function println(value) cannot
be redefined. A function without an explicit return produces an internal
no-value result. Return works from inside if and while.

Semicolons are optional; line breaks alone do not delimit statements. Comments
begin with // and continue to the end of the line.

## Example

~~~text
fn square(value) {
    return value * value
}

fn main() {
    let name = "Alsamos"
    var count = 0
    while count < 3 {
        if count == 2 {
            println(name + "!")
        } else {
            println(square(count))
        }
        count = count + 1
    }
}
~~~

## Values, operators and behavior

- Int: arbitrary-precision signed integers; integer division truncates toward zero.
- String: double quoted with escaped quote, slash, newline, carriage return, and tab.
- Bool: true and false.
- Arithmetic: +, -, *, / on integers; + also concatenates two strings.
- Ordering: < <= > >= for integers.
- Equality: == != considers values equal only when their types match.
- Logical: !, &&, || on booleans. Both binary logical operators short-circuit.
- Precedence, high to low: unary; multiplication/division; addition/subtraction;
  ordering; equality; &&; ||.
- Function arguments are evaluated left to right; wrong arity is a runtime error.
- let declares an immutable variable; var declares a mutable variable.
- Parameters are immutable. Nested blocks have their own lexical scopes.
- Each function invocation has an independent local scope; caller locals
  are not visible to the called function (no closures or global variables).
- If/while conditions must be booleans, not integers.
- A while body has a new block scope per iteration.
- Calls support forward references and recursion. Evaluation has an internal
  call-depth limit, and a global execution-step budget.

## APIs and diagnostics

~~~bash
python -m samhus run examples/functions.sahu
python -m samhus run examples/functions.sahu --max-steps 1000
python -m samhus check examples/functions.sahu
~~~

check performs **syntactic parsing only**; it does not prove types or safe execution.
Runtime or parse errors contain line and column numbers.

The Python API parse(source) is kept for backwards compatibility and returns
the entry function's body after parsing all definitions; parse_program(source)
returns the full Program with all function declarations.

## Not implemented

Static types, type annotations, overloaded functions, modules, imports,
user-defined data types, arrays, dictionaries, floats, async/await, filesystem,
network access, native compiler, LLVM/Wasm, package registry and IDE tooling.

**Security:** bounded steps and calls are *not* a general resource or security
sandbox. Large integers, deep expressions or host runtime behavior can still
consume resources. Only run trusted test programs.
