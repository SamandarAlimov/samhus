"""Additional regression tests for the experimental control flow and functions."""
import unittest

from samhus import SamhusError, parse, parse_program, run_to_string


class SamhusFunctionsTests(unittest.TestCase):
    def test_function_call_and_return(self):
        source = """
fn add(a, b) { return a + b }
fn main() { println(add(7, 35)) }
"""
        self.assertEqual(run_to_string(source), "42\n")

    def test_function_declared_after_main(self):
        self.assertEqual(run_to_string('fn main() { println(greet("Samhus")) }\nfn greet(name) { return "Hello, " + name }'), "Hello, Samhus\n")

    def test_nested_calls(self):
        source = "fn double(x) { return x * 2 }\nfn sum(a, b) { return a + b }\nfn main() { println(sum(double(5), double(6))) }"
        self.assertEqual(run_to_string(source), "22\n")

    def test_recursion(self):
        source = """
fn factorial(n) {
    if n <= 1 { return 1 }
    return n * factorial(n - 1)
}
fn main() { println(factorial(6)) }
"""
        self.assertEqual(run_to_string(source), "720\n")

    def test_while_loop(self):
        source = """
fn main() {
    var i = 0
    var total = 0
    while i < 5 {
        total = total + i
        i = i + 1
    }
    println(total)
}
"""
        self.assertEqual(run_to_string(source), "10\n")

    def test_function_side_effect(self):
        source = """
fn greet(name) { println("Hello, " + name) }
fn main() { greet("Alsamos") }
"""
        self.assertEqual(run_to_string(source), "Hello, Alsamos\n")

    def test_function_local_scope(self):
        source = """
fn secret() { let inner = 8; return inner }
fn main() { println(secret()); println(inner) }
"""
        with self.assertRaisesRegex(SamhusError, "Undefined variable"):
            run_to_string(source)

    def test_functions_do_not_see_caller_variables(self):
        source = """
fn test() { return x }
fn main() { let x = 7; println(test()) }
"""
        with self.assertRaisesRegex(SamhusError, "Undefined variable"):
            run_to_string(source)

    def test_nested_return(self):
        source = """
fn choose(x) {
    while true {
        if x == 4 { return "found" }
        return "other"
    }
}
fn main() { println(choose(4)) }
"""
        self.assertEqual(run_to_string(source), "found\n")

    def test_wrong_arity(self):
        source = "fn plus(a, b) { return a + b }\nfn main() { println(plus(1)) }"
        with self.assertRaisesRegex(SamhusError, "expects 2 arguments, got 1"):
            run_to_string(source)

    def test_unknown_function(self):
        with self.assertRaisesRegex(SamhusError, "Undefined function"):
            run_to_string("fn main() { unknown(1) }")

    def test_builtin_arity(self):
        with self.assertRaisesRegex(SamhusError, "println expects 1 argument"):
            run_to_string("fn main() { println(1, 2) }")

    def test_loop_condition_must_be_bool(self):
        with self.assertRaisesRegex(SamhusError, "While condition must be a boolean"):
            run_to_string("fn main() { while 1 { println(1) } }")

    def test_infinite_loop_budget(self):
        with self.assertRaisesRegex(SamhusError, "Execution step limit exceeded"):
            run_to_string("fn main() { while true {} }", max_steps=25)

    def test_recursion_limit(self):
        with self.assertRaisesRegex(SamhusError, "Function call depth limit"):
            run_to_string("fn recurse() { return recurse() }\nfn main() { println(recurse()) }")

    def test_duplicate_function(self):
        with self.assertRaisesRegex(SamhusError, "Duplicate function"):
            parse_program("fn main() {}\nfn main() {}")

    def test_duplicate_parameter(self):
        with self.assertRaisesRegex(SamhusError, "Duplicate parameter"):
            parse_program("fn add(a, a) { return a }\nfn main() {}")

    def test_reserved_builtin_name(self):
        with self.assertRaisesRegex(SamhusError, "reserved builtin"):
            parse_program("fn println(x) { return x }\nfn main() {}")

    def test_entrypoint_arity(self):
        with self.assertRaisesRegex(SamhusError, "zero parameters"):
            parse_program("fn main(x) { return x }")

    def test_parse_preserves_legacy_main_body(self):
        body = parse("fn helper() { return 1 }\nfn main() { println(helper()) }")
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0].kind, "expr")

    def test_parse_program_keeps_functions(self):
        result = parse_program("fn other(x) { return x }\nfn main() {}")
        self.assertEqual([f.name for f in result.functions], ["other", "main"])

    def test_parameters_immutable(self):
        with self.assertRaisesRegex(SamhusError, "immutable"):
            run_to_string("fn edit(x) { x = 2 }\nfn main() { edit(1) }")

    def test_loop_variable_scoping(self):
        with self.assertRaisesRegex(SamhusError, "Undefined variable"):
            run_to_string("fn main() { var i = 0; while i < 1 { let local = 3; i = i + 1 }; println(local) }")

    def test_return_ends_function(self):
        self.assertEqual(run_to_string('fn main() { println("before"); return 1; println("after") }'), "before\n")


if __name__ == "__main__":
    unittest.main()
