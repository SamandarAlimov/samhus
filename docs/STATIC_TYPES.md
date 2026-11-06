# Static type checking — experimental design

Samhus 0.0.3 includes a proof-of-concept analyzer. The project owner has
**not** approved these type semantics as a final language standard.

## How to use it

~~~bash
python -m samhus typecheck examples/typed.sahu
python -m samhus run examples/typed.sahu --typecheck
python -m samhus check examples/typed.sahu
~~~

Check is deliberately syntax-only for backwards compatibility.

## Current type syntax

~~~text
fn add(a: Int, b: Int) -> Int { return a + b }

fn main() -> Unit {
    var count: Int = 1
    count = count + add(2, 3)
    println(count)
}
~~~

Available primitive annotations: Int, Float, String, Bool, Null, Unit, Any.
Experimental collection annotations: List[T], Map[String,T].
Unknown annotations are parser errors, not silently treated as dynamic types.

## Analyzer checks

- Types of literals, known variables and primitive operators.
- Function arity, argument and return types when annotated.
- Immutable and mutable assignments.
- Variable scoping, duplicate declarations and undefined names.
- Boolean conditions for if/while.
- Conservative may-exit-without-return checks for functions with declared
  non-Unit and non-Any return types.
- Explicit runtime annotation enforcement on function arguments, returns,
  declarations and assignments.

Unannotated parameters and returns are treated as Any. Local unannotated
variables infer types from their initial expressions for analysis.
Expressions depending on Any can remain Any.

## Important caveats

- This is **not a sound static type system**. Any can hide type errors
  caught only by runtime checks or ordinary operation errors.
- No generics, user-defined types, nullability, unions, interfaces,
  borrow checking, modules, flow-sensitive narrowing, ownership or
  definite assignment analysis.
- For return paths, if/else is recognized when both branches definitely
  return. While loops never prove a return even with literal true.
- The checker skips statements after a guaranteed return; unreachable-code
  warnings are not implemented.
- The checker may reject valid-looking programs and miss errors outside
  the supported subset. Never run untrusted programs.
- No decision has been made about whether the production language will
  require static annotations or which checker architecture will be used.

Design experiments and tests are in tests/test_typecheck.py.


## Nested List[T] experimental checking

List[T] accepts recursive type arguments. Typed List literals are checked
at their known element types, including nested ones and function arguments.
Index results infer the element type, and append preserves typed List type
where known. Dynamic Any remains an incomplete static safety boundary.

## Experimental Float and Null checking (0.0.9)

Float is a finite binary64 type. Known mixed Int/Float numeric arithmetic
produces Float; known pure Int arithmetic remains Int; comparisons return
Bool. Null is an explicit type distinct from Unit. Direct Int-to-Float
assignment needs to_float(Int), and is_null(Any) returns Bool. Dynamic Any
can still obscure type errors until execution. Native C11 lacks both types.
