"""Coverage of opt-in typed syntax, static diagnostics and runtime guards."""
import unittest

from samhus import SamhusError, parse_program, run_to_string
from samhus.typecheck import check_types


def main(body: str, return_type: str = "") -> str:
    return f"fn main(){' -> ' + return_type if return_type else ''} {{ {body} }}"


class TypedSamhusTests(unittest.TestCase):
    def assert_valid(self, source: str, output: str | None = None):
        check_types(source)
        if output is not None:
            self.assertEqual(run_to_string(source), output)

    def assert_static_error(self, source: str, pattern: str):
        with self.assertRaisesRegex(SamhusError, pattern):
            check_types(source)

    def test_typed_integer(self):
        self.assert_valid(main("let n: Int = 42; println(n)"), "42\n")

    def test_typed_string(self):
        self.assert_valid(main('let n: String = "Samhus"; println(n)'), "Samhus\n")

    def test_typed_boolean(self):
        self.assert_valid(main("let b: Bool = true; println(!b)"), "false\n")

    def test_typed_functions(self):
        self.assert_valid(
            "fn add(a: Int, b: Int) -> Int { return a + b }\n"
            "fn main() { println(add(17, 25)) }", "42\n",
        )

    def test_typed_returns(self):
        self.assert_valid(
            'fn greeting(name: String) -> String { return "Hi, " + name }\n'
            'fn main() { println(greeting("Alsamos")) }',
            "Hi, Alsamos\n",
        )

    def test_bool_return(self):
        self.assert_valid(
            "fn positive(x: Int) -> Bool { return x > 0 }\n"
            "fn main() { println(positive(7)) }", "true\n",
        )

    def test_unit_return_implicit(self):
        self.assert_valid(
            'fn greet() -> Unit { println("hello") }\n'
            "fn main() -> Unit { greet() }", "hello\n",
        )

    def test_unit_return_explicit(self):
        self.assert_valid(
            "fn noop() -> Unit { return println(42) }\n"
            "fn main() { noop() }", "42\n",
        )

    def test_dynamic_legacy_syntax(self):
        self.assert_valid(
            "fn twice(x) { return x * 2 }\n"
            "fn main() { println(twice(21)) }", "42\n",
        )

    def test_mutable_typed_var(self):
        self.assert_valid(main("var x: Int = 2; x = 4; println(x)"), "4\n")

    def test_shadowed_typed_var(self):
        self.assert_valid(main("let x: Int = 1; if true { let x: String = \"two\"; println(x) }; println(x)"), "two\n1\n")

    def test_typed_if_else_both_return(self):
        self.assert_valid(
            "fn choose(x: Int) -> Int { if x > 5 { return 10 } else { return 20 } }\n"
            "fn main() { println(choose(3)) }", "20\n",
        )

    def test_typed_recursion(self):
        self.assert_valid(
            "fn factorial(n: Int) -> Int { if n <= 1 { return 1 }; return n * factorial(n - 1) }\n"
            "fn main() { println(factorial(5)) }", "120\n",
        )

    def test_typed_while(self):
        self.assert_valid(main("var x: Int = 0; while x < 3 { x = x + 1 }; println(x)"), "3\n")

    def test_forward_declared_type(self):
        self.assert_valid("fn main() { println(ok(7)) }\nfn ok(x: Int) -> Int { return x }", "7\n")

    def test_any_type_accepts_dynamic(self):
        self.assert_valid(main('let x: Any = 1; var y: Any = "hello"; y = x; println(y)'), "1\n")

    def test_annotated_parameter_from_any(self):
        self.assert_valid(
            "fn get(x) { return x }\n"
            "fn double(n: Int) -> Int { return n * 2 }\n"
            "fn main() { println(double(get(21))) }", "42\n",
        )

    def test_parser_annotations_ast(self):
        p = parse_program("fn add(x: Int, y: String) -> Bool { return true }\nfn main() {}")
        self.assertEqual(p.functions[0].param_types, ("Int", "String"))
        self.assertEqual(p.functions[0].return_type, "Bool")

    def test_parser_mixed_parameters(self):
        p = parse_program("fn combine(x, y: Int) { return y }\nfn main() {}")
        self.assertEqual(p.functions[0].param_types, (None, "Int"))

    def test_declaration_ast_type(self):
        p = parse_program(main("var count: Int = 1"))
        self.assertEqual(p.functions[0].body[0].declared_type, "Int")

    def test_declared_value_mismatch(self):
        self.assert_static_error(main('let n: Int = "no"'), "Type mismatch: expected Int, got String")

    def test_declared_bool_mismatch(self):
        self.assert_static_error(main("let n: Bool = 1"), "expected Bool, got Int")

    def test_declared_string_mismatch(self):
        self.assert_static_error(main("let n: String = true"), "expected String, got Bool")

    def test_function_argument_mismatch(self):
        self.assert_static_error(
            'fn add(n: Int) -> Int { return n }\nfn main() { println(add("wrong")) }',
            "expected Int, got String",
        )

    def test_function_return_mismatch(self):
        self.assert_static_error(
            'fn bad() -> Int { return "wrong" }\nfn main() { bad() }',
            "expected Int, got String",
        )

    def test_missing_typed_return(self):
        self.assert_static_error(
            'fn wrong() -> Int { println(1) }\nfn main() { wrong() }',
            "may exit without returning Int",
        )

    def test_missing_branch_return(self):
        self.assert_static_error(
            'fn wrong(x: Bool) -> Int { if x { return 1 } }\nfn main() {}',
            "may exit without returning Int",
        )

    def test_while_not_proven_return(self):
        self.assert_static_error(
            'fn wrong() -> Int { while true { return 1 } }\nfn main() {}',
            "may exit without returning Int",
        )

    def test_wrong_if_condition(self):
        self.assert_static_error(main("if 1 { println(1) }"), "expected Bool, got Int")

    def test_wrong_while_condition(self):
        self.assert_static_error(main('while "yes" { println(1) }'), "expected Bool, got String")

    def test_wrong_operator(self):
        self.assert_static_error(main('println(1 - "oops")'), "expected Int, got String")

    def test_string_plus_integer(self):
        self.assert_static_error(main('println("hello" + 2)'), "expected Int, got String")

    def test_boolean_plus_integer(self):
        self.assert_static_error(main("println(true + 1)"), "expected Int, got Bool")

    def test_and_requires_booleans(self):
        self.assert_static_error(main("println(true && 3)"), "expected Bool, got Int")

    def test_not_requires_boolean(self):
        self.assert_static_error(main("println(!42)"), "expected Bool, got Int")

    def test_negative_requires_integer(self):
        self.assert_static_error(main('println(-"hi")'), "expected Int, got String")

    def test_immutable_assignment_static(self):
        self.assert_static_error(main("let x: Int = 1; x = 2"), "immutable")

    def test_assignment_type_mismatch(self):
        self.assert_static_error(main('var x: Int = 1; x = "wrong"'), "expected Int, got String")

    def test_inferred_type_mismatch(self):
        self.assert_static_error(main('var x = 1; x = "wrong"'), "expected Int, got String")

    def test_duplicate_symbol(self):
        self.assert_static_error(main("let x = 1; let x = 2"), "already declared")

    def test_undefined_symbol(self):
        self.assert_static_error(main("println(unknown)"), "Undefined variable")

    def test_out_of_scope_symbol(self):
        self.assert_static_error(main("if true { let x = 1 }; println(x)"), "Undefined variable")

    def test_undefined_function(self):
        self.assert_static_error(main("missing()"), "Undefined function")

    def test_wrong_function_arity(self):
        self.assert_static_error("fn one(x: Int) -> Int { return x }\nfn main() { one() }", "expects 1 arguments")

    def test_wrong_print_arity(self):
        self.assert_static_error(main("println(1, 2)"), "println expects 1 argument")

    def test_unknown_parameter_type(self):
        self.assert_static_error("fn test(x: Integer) { return x }\nfn main() {}", "Unknown type")

    def test_unknown_return_type(self):
        self.assert_static_error("fn main() -> Stringy {}", "Unknown type")

    def test_unknown_variable_type(self):
        self.assert_static_error(main("let x: Foo = 3"), "Unknown type")

    def test_runtime_typed_argument_without_static_pass(self):
        with self.assertRaisesRegex(SamhusError, "expected Int, got String"):
            run_to_string('fn f(x: Int) { println(x) }\nfn main() { f("oops") }')

    def test_runtime_typed_return_without_static_pass(self):
        with self.assertRaisesRegex(SamhusError, "expected Int, got String"):
            run_to_string('fn f() -> Int { return "oops" }\nfn main() { f() }')

    def test_runtime_typed_assignment_without_static_pass(self):
        with self.assertRaisesRegex(SamhusError, "expected Bool, got Int"):
            run_to_string(main("var x: Bool = true; x = 1"))

    def test_runtime_missing_typed_return(self):
        with self.assertRaisesRegex(SamhusError, "expected Int, got Unit"):
            run_to_string('fn f() -> Int {}\nfn main() { f() }')

    def test_runtime_type_guard_accepts_any(self):
        self.assert_valid(main('var x: Any = 1; x = "okay"; println(x)'), "okay\n")


if __name__ == "__main__":
    unittest.main()
