"""Finite Float and distinct Null value conformance for tree, VM, JSON and CLI."""
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from samhus import SamhusError, run_to_string
from samhus.astdump import dump_ast
from samhus.formatter import format_program
from samhus.native_c import emit_c
from samhus.typecheck import check_types
from samhus.vm import run_vm_to_string


def main(body: str) -> str:
    return "fn main() -> Unit {\n" + body + "\n}"


def capture(engine, src: str):
    try:
        return ("ok", engine(src))
    except SamhusError as ex:
        return ("error", str(ex))


class FloatNullTests(unittest.TestCase):
    def both(self, source: str, expected: str | None = None, *, static=True):
        if static:
            check_types(source)
        ref, vm = capture(run_to_string, source), capture(run_vm_to_string, source)
        self.assertEqual(ref, vm, f"Tree/VM disagree:\n{source}\n{ref}\n{vm}")
        if expected is not None:
            self.assertEqual(ref, ("ok", expected))
        return ref

    def fails(self, source: str, message: str):
        outcome = self.both(source, static=False)
        self.assertEqual(outcome[0], "error", outcome)
        self.assertIn(message, outcome[1])

    def static_fails(self, source: str, message: str):
        with self.assertRaises(SamhusError) as ex:
            check_types(source)
        self.assertIn(message, str(ex.exception))

    def test_float_literal(self):
        self.both(main("println(1.25)"), "1.25\n")

    def test_scientific_literal(self):
        self.both(main("println(2e3); println(1.5E-2)"), "2000.0\n0.015\n")

    def test_float_zero(self):
        self.both(main("println(0.0); println(-0.0)"), "0.0\n-0.0\n")

    def test_null_literal(self):
        self.both(main("println(null); println(str(null))"), "null\nnull\n")

    def test_null_vs_unit(self):
        self.both(main("println(null == assert(true)); println(is_null(null)); println(is_null(assert(true)))"),
                  "false\ntrue\nfalse\n")

    def test_null_equality(self):
        self.both(main("println(null==null); println(null!=null); println(null==false)"),
                  "true\nfalse\nfalse\n")

    def test_null_typed(self):
        self.both(main("let n: Null = null; println(is_null(n))"), "true\n")

    def test_null_typed_fail(self):
        self.static_fails(main("let n: Null = 10"), "expected Null, got Int")

    def test_null_condition_fail(self):
        self.static_fails(main("if null { println(1) }"), "expected Bool, got Null")
        self.fails(main("if null { println(1) }"), "If condition must be a boolean")

    def test_float_type(self):
        self.both(main("let x: Float = 1.25; println(x)"), "1.25\n")

    def test_float_type_mismatch(self):
        self.static_fails(main("let x: Float = 1"), "expected Float, got Int")
        self.fails(main("let x: Float = 1"), "expected Float, got Int")

    def test_float_conversion(self):
        self.both(main("let x: Float = to_float(10); println(x)"), "10.0\n")

    def test_float_conversion_from_float(self):
        self.both(main("println(to_float(1.5))"), "1.5\n")

    def test_float_conversion_wrong_type(self):
        self.static_fails(main('println(to_float("3"))'), "expects Int or Float")
        self.fails(main('println(to_float("3"))'), "expects Int or Float")

    def test_float_conversion_large_int(self):
        large = "9" * 400
        self.fails(main(f"println(to_float({large}))"), "too large to convert")

    def test_float_conversion_wrong_arity(self):
        self.static_fails(main("to_float()"), "expects 1 argument")
        self.fails(main("to_float()"), "expects 1 argument")

    def test_int_division_compatibility(self):
        self.both(main("println(7/2); println(-7/2)"), "3\n-3\n")

    def test_mixed_float_division(self):
        self.both(main("println(7/2.0); println(7.0/2); println(7.0/2.0)"),
                  "3.5\n3.5\n3.5\n")

    def test_float_addition(self):
        self.both(main("println(1.5+2.0); println(2+1.5)"), "3.5\n3.5\n")

    def test_float_subtraction(self):
        self.both(main("println(4.5-2); println(7-1.5)"), "2.5\n5.5\n")

    def test_float_multiplication(self):
        self.both(main("println(1.25*4); println(2.0*2.5)"), "5.0\n5.0\n")

    def test_float_unary(self):
        self.both(main("println(-1.25); println(-(-2.5))"), "-1.25\n2.5\n")

    def test_float_comparisons(self):
        self.both(main("println(1.5>1); println(1.5>=1.5); println(1.5<2)"), "true\ntrue\ntrue\n")

    def test_numeric_equality_strict(self):
        self.both(main("println(1==1.0); println(1!=1.0); println(1.0==1.0)"),
                  "false\ntrue\ntrue\n")

    def test_float_wrong_bool_arithmetic(self):
        self.static_fails(main("println(1.5+true)"), "expected Int, got Bool")
        self.fails(main("println(1.5+true)"), "requires integers or floats")

    def test_float_plus_string_fails(self):
        self.fails(main('println(1.5+"bad")'), "requires integers or floats")

    def test_float_divide_by_zero(self):
        self.fails(main("println(1.5/0.0)"), "Division by zero")
        self.fails(main("println(1.5/0)"), "Division by zero")

    def test_float_overflow(self):
        self.fails(main("println(1e308*1e308)"), "Non-finite Float result")

    def test_float_literal_overflow(self):
        with self.assertRaisesRegex(SamhusError, "Float literal out of range"):
            check_types(main("println(1e309)"))

    def test_float_literal_fraction_digits(self):
        with self.assertRaisesRegex(SamhusError, "requires digits"):
            check_types(main("println(1.)"))

    def test_float_literal_exponent_digits(self):
        with self.assertRaisesRegex(SamhusError, "exponent requires digits"):
            check_types(main("println(2e+)"))

    def test_float_list(self):
        self.both(main("let xs: List[Float] = [1.5,2.5]; println(xs[1])"), "2.5\n")

    def test_float_list_wrong_type(self):
        self.static_fails(main("let xs: List[Float]=[1.5,2]"), "expected Float, got Int")

    def test_null_list(self):
        self.both(main("let xs: List[Null] = [null,null]; println(xs[1])"), "null\n")

    def test_float_map(self):
        self.both(main('let obj: Map[String,Float]={"score":9.5}; println(obj["score"])'),
                  "9.5\n")

    def test_null_map(self):
        self.both(main('let obj: Map[String,Null]={"missing":null}; println(is_null(obj["missing"]))'),
                  "true\n")

    def test_mixed_dynamic_list(self):
        self.both(main('println([1,1.0,null,true,"AI"])'), '[1, 1.0, null, true, "AI"]\n')

    def test_nested_dynamic_map(self):
        self.both(main('let obj: Map[String,Any]={"a":null,"b":1.5}; println(json_encode(obj))'),
                  '{"a":null,"b":1.5}\n')

    def test_json_float_parse(self):
        self.both(main('println(json_parse("12.75"))'), "12.75\n")

    def test_json_float_exponent(self):
        self.both(main('println(json_parse("1e2"))'), "100.0\n")

    def test_json_float_roundtrip(self):
        self.both(main('println(json_encode(json_parse("[1.25,2.5,null]")))'),
                  '[1.25,2.5,null]\n')

    def test_json_typed_float(self):
        self.both(main('let values: List[Float]=json_parse("[1.0,2.5]"); println(values[0])'),
                  "1.0\n")

    def test_json_int_does_not_coerce_float(self):
        self.fails(main('let values: List[Int] = json_parse("[1.5]")'), "expected List[Int]")

    def test_json_null_type(self):
        self.both(main('let value: Null = json_parse("null"); println(is_null(value))'), "true\n")

    def test_json_null_not_unit(self):
        self.fails(main('let value: Unit = json_parse("null")'), "expected Unit, got Null")

    def test_json_nonfinite_rejection(self):
        self.fails(main('println(json_parse("1e309"))'), "non-finite Float literal")
        self.fails(main('println(json_parse("NaN"))'), "nonstandard numeric constant")

    def test_json_boolean_not_float(self):
        self.fails(main('let value: Float = json_parse("true")'), "expected Float, got Bool")

    def test_json_encode_dynamic_value(self):
        self.both(main('println(json_encode({"float":1.5, "null":null, "integer":2}))'),
                  '{"float":1.5,"null":null,"integer":2}\n')

    def test_json_preserves_negative_zero(self):
        self.both(main('println(json_encode(-0.0))'), "-0.0\n")

    def test_function_float_signature(self):
        self.both("fn area(x: Float) -> Float { return x * 2.0 }\n"
                  "fn main() -> Unit { println(area(3.5)) }", "7.0\n")

    def test_function_float_argument_error(self):
        self.static_fails("fn area(x: Float) -> Float {return x}\nfn main(){area(2)}",
                          "expected Float, got Int")

    def test_function_null_return(self):
        self.both("fn nil() -> Null {return null}\nfn main(){println(is_null(nil()))}",
                  "true\n")

    def test_formatter_roundtrip(self):
        source=main('let x: Float = 2.5; let n: Null = null; println(x); println(n)')
        formatted=format_program(source)
        self.assertEqual(format_program(formatted),formatted)
        self.assertEqual(run_to_string(source),run_to_string(formatted))
        self.assertEqual(run_vm_to_string(source),run_vm_to_string(formatted))

    def test_ast_float(self):
        data=json.loads(dump_ast(main("println(1.25)")))
        literal=data["functions"][0]["body"][0]["expr"]["args"][0]
        self.assertEqual(literal["value"],1.25)

    def test_ast_null(self):
        data=json.loads(dump_ast(main("println(null)")))
        literal=data["functions"][0]["body"][0]["expr"]["args"][0]
        self.assertIsNone(literal["value"])

    def test_native_float_rejected(self):
        with self.assertRaisesRegex(SamhusError, "Native subset"):
            emit_c(main("println(1.5)"))

    def test_native_null_rejected(self):
        with self.assertRaisesRegex(SamhusError, "Native subset"):
            emit_c(main("println(null)"))

    def test_100_generated_float_arithmetic(self):
        rng=random.Random(9401)
        operators=("+","-","*","/")
        for _ in range(100):
            a=rng.randint(-10000,10000)/4
            b=rng.randint(1,10000)/8
            op=rng.choice(operators)
            expression=f"({a}) {op} ({b})"
            self.both(main("println("+expression+")"))

    def test_100_generated_json_float_values(self):
        rng=random.Random(288)
        for _ in range(100):
            number=rng.randint(-100000,100000)/16
            self.both(main(f'println(json_encode(json_parse("{number}")))'), f"{number}\n")

    def test_cli_float_null(self):
        source=main('let data: Map[String,Any] = json_parse("{\\"ratio\\":1.25,\\"missing\\":null}"); '
                    'println(data["ratio"]); println(is_null(data["missing"]))')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"float_null.sahu"
            path.write_text(source,encoding="utf-8")
            for backend in ("tree","vm"):
                out=subprocess.run([sys.executable,"-m","samhus","run",str(path),
                                   "--backend",backend,"--typecheck"],
                                   text=True,capture_output=True,encoding="utf-8")
                self.assertEqual(out.returncode,0,out.stderr)
                self.assertEqual(out.stdout,"1.25\ntrue\n")


if __name__=="__main__":
    unittest.main()
