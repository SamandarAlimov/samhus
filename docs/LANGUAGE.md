# Samhus syntax draft — experimental v0.0.1

**Not a final standard.** These rules describe only the working bootstrap interpreter.

## Entry point and statements

~~~sahu
fn main() {
    let name = "Alsamos"  // immutable variable
    var count = 2         // mutable variable
    count = count + 1
    if count == 3 {
        println(name)
    } else {
        println("Unexpected")
    }
}
~~~

The prototype requires exactly one fn main() with no parameters. Semicolons after statements are optional; // comments extend to the end of the line. Only declarations, assignments, println(expr), and if/else are supported.

## Types and expressions

- Int: arbitrary precision signed integers; integer division truncates toward zero.
- String: double-quoted strings, with backslash, double quote, newline, carriage return, and tab escapes.
- Bool: true, false.
- + - * / arithmetic; + also concatenates two strings.
- < <= > >= compare integers; == != compare values of the same type (otherwise unequal).
- ! && || accept booleans; && and || short-circuit.
- Precedence: unary, multiplication/division, addition/subtraction, ordering, equality, &&, ||.
- Nested blocks have lexical variable scopes. let cannot be reassigned; var can.

## Error handling and limitations

Syntax and runtime errors report source positions. The check command **parses syntax only**; it is not a static type checker. There are no real functions beyond main, modules, file/network APIs, native compilation, security sandbox, or user-defined types yet. The interpreter is for trusted local experiments only.
