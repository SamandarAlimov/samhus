# Samhus language reference — experimental 0.0.3

This is **observed prototype behavior**, not a finalized language standard.

## Grammar (informal)

~~~text
program        := function*
function       := "fn" NAME "(" parameters? ")" ("->" type)? block
parameters     := parameter ("," parameter)*
parameter      := NAME (":" type)?
type           := Int | String | Bool | Unit | Any
block          := "{" statement* "}"
statement      := ("let" | "var") NAME (":" type)? "=" expression ";"?
                | NAME "=" expression ";"?
                | call_expression ";"?
                | "return" expression ";"?
                | "if" expression block ("else" block)?
                | "while" expression block
expression     := literals | variables | unary | binary | calls | "(" expression ")"
~~~

Type names are case sensitive. The return type uses the arrow ->.
Parameter, variable, and function return annotations are optional.
The entrypoint fn main() must exist and must take zero arguments.

Semicolons are optional; comments start with // outside string literals.
The language currently accepts no top-level variables, modules or classes.

## Example

~~~text
fn add(a: Int, b: Int) -> Int {
    return a + b
}

fn main() -> Unit {
    let name: String = "Samhus"
    var total: Int = 0
    while total < 3 {
        total = total + 1
    }
    println(name)
    println(add(total, 39))
}
~~~

Output: Samhus and 42, each on a separate line.

## Primitive types

- Int: arbitrary precision signed integer; / truncates toward zero.
- String: double-quoted Unicode string, with escaped newline, carriage return,
  tab, double quote and backslash.
- Bool: true and false.
- Unit: the no-value result of println or a function without return.
  There is no Unit literal at present.
- Any: dynamic type marker accepted by the optional type checker.

The boolean true is not an Int; numeric operators reject booleans at runtime.

## Operators

- Unary: -, !
- Multiplicative: *, /
- Additive: +, -; + also joins two strings.
- Ordering: <, <=, >, >= on integers.
- Equality: ==, != (different runtime types compare unequal).
- Boolean short-circuit operators: &&, ||.
- Parentheses alter precedence.

## Functions and scopes

- Functions can be defined before or after main.
- Function calls evaluate arguments left-to-right.
- Parameters are immutable local bindings, and functions cannot access
  the caller's local variables.
- let cannot be reassigned; var can. Typed variables are runtime-checked
  on declarations and assignments.
- Each block creates a lexical scope; while bodies create one per iteration.
- Explicit annotated function arguments and returns are runtime checked.
- Return without an expression is not yet supported.

## Compiler and checks

This project is currently a tree-walking Python interpreter, not a native
compiler. The check command validates syntax only; typecheck runs an additional
experimental semantic analysis. Run --typecheck enables both analysis and
execution; run without the flag still enforces explicit runtime type annotations.
See [STATIC_TYPES](STATIC_TYPES.md) for limitations.

For low-level inspection: python -m samhus ast examples/typed.sahu.
For canonical formatting: python -m samhus fmt examples/typed.sahu.

## Safety

Execution-step and recursion depth checks exist for educational experiments,
but cannot prevent all resource exhaustion and are not a security sandbox.
Never execute untrusted source code with this interpreter.


## Experimental core functions (prototype 0.0.5)

- println(value: Any) -> Unit: print one value.
- assert(condition: Bool) -> Unit: fail with a source-positioned error if false.
- len(text: String) -> Int: return Unicode code-point count for a string.
- str(value: Any) -> String: convert primitive/Unit value to text.
- json_valid(payload: String) -> Bool: check strict JSON syntax,
  rejecting malformed JSON, NaN and Infinity.

These shared builtins work in both the tree and bytecode VM execution
paths. They are NOT an official AI SDK, schema validator, memory-safety
guarantee, complete standard library, or stable final syntax.
