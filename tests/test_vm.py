"""Differential conformance between AST interpreter and independent VM backend."""
from contextlib import redirect_stdout
from io import StringIO
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from samhus import SamhusError, run, run_to_string
from samhus.bytecode import compile_source
from samhus.vm import run_vm, run_vm_to_string
from samhus.typecheck import check_types


def wrap(body: str) -> str:
    return f"fn main() {{\n{body}\n}}"


def capture(executor, source: str, limit: int = 100_000):
    output = StringIO()
    try:
        executor(source, output=output, max_steps=limit)
    except SamhusError as ex:
        return ("error", str(ex), output.getvalue())
    return ("ok", output.getvalue())


class DifferentialTests(unittest.TestCase):
    def same(self, source: str, limit: int = 100_000):
        expected = capture(run, source, limit)
        actual = capture(run_vm, source, limit)
        self.assertEqual(actual, expected, f"\nSOURCE:\n{source}\nTREE: {expected}\nVM: {actual}")
        return actual

    def test_hello_world(self):
        self.assertEqual(self.same(wrap('println("Assalomu alaykum, Alsamos!")')), ("ok", "Assalomu alaykum, Alsamos!\n"))

    def test_math_and_precedence(self):
        self.same(wrap("println(2+3*4)\nprintln((2+3)*4)\nprintln(-7/2)"))

    def test_long_integer_no_float_rounding(self):
        self.same(wrap("println(123456789123456789123456789 / 7)"))

    def test_all_binary_ops(self):
        self.same(wrap("""
println(7+2)
println(7-2)
println(7*2)
println(7/2)
println(7<2)
println(7<=7)
println(7>2)
println(7>=7)
println(7==7)
println(7!=2)
println(true==1)
println(true!=1)
"""))

    def test_nested_control_flow(self):
        self.same(wrap("""
var a = 0
while a < 5 {
    if a > 2 {
        println(a + 10)
    } else {
        println(a)
    }
    a = a + 1
}
"""))

    def test_blocks_shadow_bindings(self):
        self.same(wrap("""
let a = 5
if true {
    let a = 7
    println(a)
}
println(a)
"""))

    def test_immutable_binding_error(self):
        self.same(wrap("let a = 2; a = 3"))

    def test_undefined_symbol(self):
        self.same(wrap("println(missing)"))

    def test_undefined_assignment(self):
        self.same(wrap("missing = 2"))

    def test_duplicate_variable(self):
        self.same(wrap("let a = 1; let a = 2"))

    def test_duplicate_variable_rhs_side_effect(self):
        self.same(wrap('let x = 1; let x = println("must not happen")'))

    def test_wrong_types(self):
        for expr in ['"test" - 5', 'true + 1', '1 + "test"', '!1', '-true']:
            with self.subTest(expr=expr):
                self.same(wrap(f"println({expr})"))

    def test_short_circuit_skips_rhs(self):
        self.assertEqual(self.same(wrap("println(false && (1/0==1)); println(true || (1/0==1))")),
                         ("ok", "false\ntrue\n"))

    def test_short_circuit_boolean_type_errors(self):
        for expr in ['1 && true', 'false || 2', '1 || true', 'true && 1']:
            with self.subTest(expr=expr):
                self.same(wrap(f"println({expr})"))

    def test_short_circuit_calls(self):
        source = """fn side() { println("called"); return true }
fn main() { println(false && side()); println(true || side()); println(true && side()); println(false || side()) }"""
        self.same(source)

    def test_function_recursion(self):
        self.same("""fn factorial(n: Int) -> Int {
    if n < 2 { return 1 }
    return n * factorial(n-1)
}
fn main() { println(factorial(8)) }""")

    def test_forward_function(self):
        self.same("""fn main() { println(add(6,7)) }
fn add(a,b) { return a+b }""")

    def test_parameter_shadowing_caller(self):
        self.same("""fn f(x) { println(x); return x+1 }
fn main() { let x = 7; println(f(9)); println(x) }""")

    def test_zero_parameter_calls(self):
        self.same("""fn answer() -> Int { return 42 }
fn main() { println(answer()); println(answer()) }""")

    def test_return_from_while(self):
        self.same("""fn choose(x) {
while true { if x == 4 {return "four"} else {return "other"} }
}
fn main() { println(choose(4)); println(choose(5)) }""")

    def test_implicit_return_is_unit(self):
        self.same("""fn f() -> Unit { println("side") }
fn main() { println(f()) }""")

    def test_types_annotated_success(self):
        source = """fn add(a: Int, b: Int) -> Int { return a + b }
fn main() -> Unit { var x: Int = 3; x = add(x, 9); println(x) }"""
        check_types(source)
        self.same(source)

    def test_types_annotated_failure(self):
        for source in [
            wrap('let x: Int = "text"'),
            wrap('var x: Int = 3; x = "text"'),
            'fn f(x: Int) { println(x) }\nfn main() { f("text") }',
            'fn f() -> Int { return "text" }\nfn main() { f() }',
            'fn f() -> Int {}\nfn main() { f() }',
        ]:
            with self.subTest(source=source):
                self.same(source)

    def test_dynamic_any_to_typed(self):
        self.same('fn f(x: Int) -> Int { return x }\nfn main() { let x: Any = 2; println(f(x)) }')

    def test_bad_function_arity(self):
        self.same("fn f(x) { return x }; fn main() { f() }".replace("}; fn", "}\nfn"))

    def test_unknown_function(self):
        self.same(wrap("unknown(5)"))

    def test_builtin_arity(self):
        self.same(wrap("println(1, 2)"))

    def test_while_loop_budget(self):
        self.same(wrap("while true {}"), 17)

    def test_function_recursion_budget(self):
        self.same("fn f() { return f() }\nfn main() { println(f()) }", 100_000)

    def test_boolean_if_error(self):
        self.same(wrap("if 4 { println(1) }"))

    def test_boolean_while_error(self):
        self.same(wrap('while "hi" {}'))

    def test_multiple_loop_scopes(self):
        self.same(wrap("var i = 0; while i < 3 { let z = i; println(z); i = i + 1 }"))

    def test_empty_if_else(self):
        self.same(wrap("if true {} else {}; if false {} else {}"))

    def test_return_skips_unreachable(self):
        self.same('fn f() -> Int { return 10; println("never") }\nfn main() { println(f()) }')

    def test_operators_equality_cross_type(self):
        self.same(wrap('println(1 == true); println("1" == 1); println(0 != false)'))

    def test_error_location(self):
        self.same(wrap('println("a" - 4)'))

    def test_disassembly_has_locations_and_functions(self):
        data = compile_source('fn f(a: Int) -> Int {return a+3}\nfn main(){println(f(4))}').disassemble()
        self.assertIn("fn f(a)", data)
        self.assertIn("BINARY '+'", data)
        self.assertIn("CALL ('f', 1)", data)

    def test_empty_main(self):
        self.assertEqual(self.same("fn main() {}"), ("ok", ""))

    def test_300_deterministic_arithmetic_cases(self):
        rng = random.Random(1837)
        ops = ["+", "-", "*", "/", "<", "<=", ">", ">=", "==", "!="]
        for _ in range(300):
            left = rng.randint(-10000, 10000)
            right = rng.randint(-10000, 10000)
            operator = rng.choice(ops)
            source = wrap(f"println(({left}) {operator} ({right}))")
            self.same(source)

    def test_200_nested_boolean_cases(self):
        rng = random.Random(5256)
        operators = ["&&", "||"]
        bools = ["true", "false"]
        for _ in range(200):
            a, b, c = (rng.choice(bools) for _ in range(3))
            o1, o2 = rng.choice(operators), rng.choice(operators)
            self.same(wrap(f"println(({a} {o1} {b}) {o2} {c})"))

    def test_100_random_loop_cases(self):
        rng = random.Random(724)
        for _ in range(100):
            maximum = rng.randint(0, 20)
            offset = rng.randint(-10, 10)
            source = wrap(f"var i = 0; var total = {offset}; while i < {maximum} {{ total = total + i; i = i + 1 }}; println(total)")
            self.same(source)

    def test_existing_example_programs(self):
        for name in ("hello", "basics", "functions", "typed"):
            with self.subTest(name=name):
                path = Path(__file__).resolve().parents[1] / "examples" / (name + ".sahu")
                self.same(path.read_text(encoding="utf-8"))

    def test_cli_vm_backend(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "example.sahu"
            path.write_text("fn main() { println(42) }", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "samhus", "run", str(path), "--backend", "vm"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "42\n")

    def test_cli_disasm(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "example.sahu"
            path.write_text("fn main() { println(42) }", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "samhus", "disasm", str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("CALL ('println', 1)", result.stdout)


if __name__ == "__main__":
    unittest.main()
