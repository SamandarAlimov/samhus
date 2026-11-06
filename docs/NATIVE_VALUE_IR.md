# Native Value IR -> C11 prototype (STRICT EXPERIMENTAL SUBSET)

The `native-ir` command now lowers verified stack-value IR (including
short-circuit PHI nodes) to standalone C11 programs, then invokes an
external C compiler. This is separate from the older AST-to-C prototype.

## Supported syntax and behavior

- Precisely one `fn main() -> Unit` function; no user functions.
- Int literals within signed 64-bit range and Bool literals.
- Checked Int64 addition, subtraction, multiplication, division and negation.
- Int comparisons/equality, Bool equality and !.
- `if / else`, nested branches and short-circuit `&& / ||`.
- `println(Int|Bool)`, `assert(Bool)`.
- Explicit PHI moves on CFG edges with parallel-move staging.

## Explicitly rejected

- Mutable or immutable variable declarations and variable loads.
- While loops, function calls other than println/assert.
- Floats, Strings, Decimals, Null, Result, List, Map and any dynamic Any.
- Unsupported integer literals, unsupported opcodes or user-defined calls.

Unsupported code fails during compilation with a source-positioned
`Native Value IR subset:` diagnostic; there is NO silent fallback.

## Numeric semantics

General Samhus Int supports arbitrary precision, whereas native IR
Int is checked **signed 64-bit**. Integer overflow in arithmetic
and division by zero cause a native process error rather than truncation.
This limited native subset is not fully semantically equivalent to the
interpreter for arbitrary-precision programs. Long-running/resource
limits, full source checks and comprehensive runtime isolation are absent.

## Usage

    python -m samhus emit-ir-c examples/native_value_ir.sahu
    python -m samhus native-ir examples/native_value_ir.sahu -o native-ir-demo
    ./native-ir-demo

Expected sample output: 14, false, true on separate lines.
Python and an external C compiler are still required at *compile time*.
The generated executable runs independently of Python.

## Backend architecture

Source -> AST -> verified bytecode -> CFG -> Value IR -> verified C11 ->
system C compiler -> standalone executable.

The Value IR output registers (including PHI nodes) are mapped to
temporary C Int64 variables. PHI merges are lowered into parallel
edge moves before control-flow `goto` transfers. The existing checked
Int64 helper functions from the AST C backend are shared to avoid
reimplementing overflow logic.

This implementation is a bridge and proof of compiler structure, NOT
a final production code generator or independently validated SSA.
IR identity and type hints are still derived from Python bootstrap.

Next objectives: variable SSA with proper scope/lifetime rules, loops,
typed functions, sound effects, general backend runtime, C ABI and
cross-platform production builds with fuzzing and sanitized tests.

Version remains unreleased `0.0.0.dev0`; file extension is provisional.
