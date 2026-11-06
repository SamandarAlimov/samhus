"""Samhus Decimal and Result: exactness, structured failures, tree/VM agreement."""
import random
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from samhus import SamhusError, run_to_string
from samhus.formatter import format_program
from samhus.typecheck import check_types
from samhus.vm import run_vm_to_string
from samhus.lexer import Token
from samhus.decimal_core import make_decimal, operation
from samhus.values import ResultValue, accepts, type_name, structural_equal


def program(body: str) -> str:
    return "fn main() -> Unit {\n" + body + "\n}"


def capture(backend, code):
    try:
        return "ok", backend(code)
    except SamhusError as exc:
        return "error", str(exc)


class DecimalAndResultTests(unittest.TestCase):
    def both(self, code, expected=None, static=True):
        if static:
            check_types(code)
        a = capture(run_to_string, code)
        b = capture(run_vm_to_string, code)
        self.assertEqual(a, b, f"Differential failure for {code!r}:\n{a}\n{b}")
        if expected is not None:
            self.assertEqual(a, ("ok", expected))
        return a

    def runtime_error(self, code, match):
        result = self.both(code, static=False)
        self.assertEqual(result[0], "error", result)
        self.assertIn(match, result[1])

    def static_error(self, code, match):
        with self.assertRaises(SamhusError) as cm:
            check_types(code)
        self.assertIn(match, str(cm.exception))

    def test_decimal_exact_cents(self):
        self.both(program('println(decimal("0.10") + decimal("0.20"))'), "0.30\n")

    def test_decimal_exact_multiplication(self):
        self.both(program('println(decimal("19.99") * 3)'), "59.97\n")

    def test_decimal_exact_subtraction(self):
        self.both(program('println(decimal("100.00") - decimal("0.01"))'), "99.99\n")

    def test_decimal_exact_division(self):
        self.both(program('println(decimal("1.00") / 4)'), "0.25\n")

    def test_decimal_repeating_division_rejected(self):
        self.runtime_error(program('println(decimal("1") / 3)'), "requires rounding")

    def test_decimal_division_by_zero(self):
        self.runtime_error(program('println(decimal("1") / 0)'), "Division by zero")

    def test_decimal_from_integer(self):
        self.both(program('let price: Decimal = decimal(50); println(price)'), "50\n")

    def test_decimal_from_decimal(self):
        self.both(program('println(decimal(decimal("2.50")))'), "2.50\n")

    def test_decimal_decimal_comparison(self):
        self.both(program('println(decimal("1.5") < decimal("1.51"))'), "true\n")

    def test_decimal_int_comparison(self):
        self.both(program('println(decimal("9.5") > 9)'), "true\n")

    def test_decimal_negative(self):
        self.both(program('println(-decimal("1.25"))'), "-1.25\n")

    def test_decimal_zero(self):
        self.both(program('println(decimal("0.00") + decimal("0.00"))'), "0.00\n")

    def test_decimal_invalid(self):
        self.runtime_error(program('println(decimal("abc"))'), "Invalid Decimal literal")

    def test_decimal_nan_rejected(self):
        self.runtime_error(program('println(decimal("NaN"))'), "Decimal must be finite")

    def test_decimal_infinity_rejected(self):
        self.runtime_error(program('println(decimal("Infinity"))'), "Decimal must be finite")

    def test_decimal_float_conversion_forbidden(self):
        self.static_error(program('println(decimal(0.1))'), "decimal expects String, Int or Decimal")
        self.runtime_error(program('println(decimal(0.1))'), "Float conversion is forbidden")

    def test_decimal_bool_forbidden(self):
        self.static_error(program('println(decimal(true))'), "decimal expects String, Int or Decimal")

    def test_decimal_float_arithmetic_forbidden(self):
        self.static_error(program('println(decimal("1") + 1.0)'), "Decimal cannot mix with Float")
        self.runtime_error(program('println(decimal("1") + 1.0)'), "Decimal cannot mix with Float")

    def test_decimal_bounded_input(self):
        self.runtime_error(program('println(decimal("' + '9'*260 + '"))'), "digit budget")

    def test_decimal_bounded_exponent(self):
        self.runtime_error(program('println(decimal("1e999"))'), "exponent budget")

    def test_decimal_typed_declaration(self):
        self.both(program('let amount: Decimal = decimal("3.25"); println(amount + 2)'), "5.25\n")

    def test_decimal_wrong_assignment(self):
        self.static_error(program("let amount: Decimal=1.25"), "expected Decimal, got Float")

    def test_decimal_typed_function(self):
        self.both(
            'fn tax(amount: Decimal) -> Decimal {return amount * decimal("0.10")}\n'
            'fn main() -> Unit {println(tax(decimal("19.99")))}',
            "1.9990\n",
        )

    def test_decimal_equality_is_type_strict(self):
        self.both(program('println(decimal("1")==1); println(decimal("1")==decimal("1.00"))'),
                  "false\ntrue\n")

    def test_decimal_in_list(self):
        self.both(program('let prices: List[Decimal] = [decimal("1.20"),decimal("2.30")];'
                          'println(prices[1])'), "2.30\n")

    def test_decimal_in_map(self):
        self.both(program('let m: Map[String,Decimal]={"price":decimal("2.05")}; println(m["price"])'),
                  "2.05\n")

    def test_decimal_json_encode_explicitly_rejects(self):
        self.runtime_error(program('json_encode(decimal("0.1"))'), "not JSON serializable")

    def test_decimal_string_bridge(self):
        self.both(program('println(json_encode({"amount":str(decimal("0.10"))}))'),
                  '{"amount":"0.10"}\n')

    def test_result_ok(self):
        self.both(program('let r: Result[Int] = result_ok(42); println(r)'), "Ok(42)\n")

    def test_result_error(self):
        self.both(program('let r: Result[Int] = result_err("missing"); println(r)'),
                  'Err("missing")\n')

    def test_result_is_ok(self):
        self.both(program('println(result_is_ok(result_ok(1))); println(result_is_ok(result_err("e")))'),
                  "true\nfalse\n")

    def test_result_value_success(self):
        self.both(program('println(result_value(result_ok("data")))'), "data\n")

    def test_result_value_error(self):
        self.runtime_error(program('println(result_value(result_err("network")))'),
                           "Cannot extract value from Err")

    def test_result_error_string(self):
        self.both(program('println(result_error(result_err("bad payload")))'), "bad payload\n")

    def test_result_error_on_ok(self):
        self.runtime_error(program('result_error(result_ok(10))'), "Cannot extract error from Ok")

    def test_result_default_on_error(self):
        self.both(program('println(result_or(result_err("fail"), 123))'), "123\n")

    def test_result_default_on_ok(self):
        self.both(program('println(result_or(result_ok(7), 123))'), "7\n")

    def test_result_type_mismatch(self):
        self.static_error(program('let r: Result[Int] = result_ok("text")'),
                          "expected Int, got String")
        self.runtime_error(program('let r: Result[Int] = result_ok("text")'),
                           "expected Result[Int]")

    def test_result_err_accepted_for_any_result(self):
        self.both(program('let r: Result[Decimal] = result_err("bad"); println(result_is_ok(r))'),
                  "false\n")

    def test_result_or_mismatched_default(self):
        self.static_error(program('let r: Result[Int] = result_ok(1);'
                                  'println(result_or(r,"x"))'), "expected Int, got String")

    def test_result_nested(self):
        self.both(program('let r: Result[List[Int]] = result_ok([1,2]);'
                          'println(result_value(r)[0])'), "1\n")

    def test_result_nested_map(self):
        self.both(program('let r: Result[Map[String,Decimal]]='
                          'result_ok({"total":decimal("2.50")});'
                          'println(result_value(r)["total"])'), "2.50\n")

    def test_result_error_expects_string(self):
        self.static_error(program('result_err(42)'), "expected String, got Int")
        self.runtime_error(program('result_err(42)'), "expected String, got Int")

    def test_result_must_be_result(self):
        self.runtime_error(program('result_value(10)'), "expects Result")
        self.static_error(program('result_is_ok(10)'), "expects Result")

    def test_result_arity(self):
        self.runtime_error(program('result_ok()'), "expects 1 argument")
        self.static_error(program('result_or(result_ok(1))'), "expects 2 arguments")

    def test_result_equality(self):
        self.both(program('println(result_ok(1)==result_ok(1));'
                          'println(result_ok(1)==result_err("e"));'
                          'println(result_err("e")==result_err("e"))'), "true\nfalse\ntrue\n")

    def test_result_list(self):
        self.both(program('let results: List[Result[Int]]=[result_ok(2),result_err("e")];'
                          'println(result_is_ok(results[1]))'), "false\n")

    def test_result_type_helpers(self):
        value=ResultValue(True,10)
        self.assertTrue(accepts("Result[Int]",value))
        self.assertFalse(accepts("Result[String]",value))
        self.assertTrue(accepts("Result[Decimal]",ResultValue(False,error="e")))
        self.assertEqual(type_name(value),"Result[Int]")
        self.assertTrue(structural_equal(ResultValue(True,1),ResultValue(True,1)))

    def test_try_json_parse_success(self):
        self.both(program(r'let r=try_json_parse("{\"count\":3}");'
                          'println(result_is_ok(r)); println(result_value(r)["count"])'),
                  "true\n3\n")

    def test_try_json_parse_error(self):
        self.both(program('let r=try_json_parse("{broken");'
                          'println(result_is_ok(r));'
                          'println(result_error(r))'), expected=None)
        result=self.both(program('let r=try_json_parse("{broken"); println(result_is_ok(r))'),
                         "false\n")
        self.assertEqual(result[0],"ok")

    def test_try_json_parse_null(self):
        self.both(program('let r=try_json_parse("null"); println(is_null(result_value(r)))'),
                  "true\n")

    def test_try_json_parse_typecheck(self):
        self.static_error(program('try_json_parse(99)'), "expected String, got Int")

    def test_try_json_parse_malformed_safe(self):
        self.both(program('println(result_is_ok(try_json_parse("{bad")))'), "false\n")

    def test_try_json_parse_schema_guard(self):
        self.both(program('let r=try_json_parse("1.5");'
                          'println(result_or(r,0))'), "1.5\n")

    def test_result_type_annotation_nested(self):
        self.both(program('let r: Result[Result[Int]]=result_ok(result_ok(3));'
                          'println(result_value(result_value(r)))'), "3\n")

    def test_result_generic_wrong_type(self):
        self.static_error(program('let r: Result[Decimal]=result_ok(1.25)'),
                          "expected Decimal, got Float")

    def test_output_result_string(self):
        self.both(program('println(str(result_ok("hello")))'), "Ok(hello)\n")

    def test_decimal_formatter(self):
        source=program('let x:Decimal=decimal("1.20");println(x+decimal("2.30"))')
        formatted=format_program(source)
        self.assertEqual(formatted,format_program(formatted))
        self.assertEqual(run_to_string(source),run_to_string(formatted))

    def test_result_formatter(self):
        source=program('let r:Result[Int]=result_ok(1);println(result_or(r,0))')
        formatted=format_program(source)
        self.assertEqual(formatted,format_program(formatted))
        self.assertEqual(run_vm_to_string(source),run_vm_to_string(formatted))

    def test_150_generated_decimal_exact_sums(self):
        rng=random.Random(20261106)
        for _ in range(150):
            cents_a=rng.randint(-100000,100000)
            cents_b=rng.randint(-100000,100000)
            a=Decimal(cents_a)/100
            b=Decimal(cents_b)/100
            src=program(f'println(decimal("{a:.2f}") + decimal("{b:.2f}"))')
            self.both(src, f"{a+b:.2f}\n")

    def test_100_generated_result_cases(self):
        rng=random.Random(1106)
        for _ in range(100):
            n=rng.randint(-1000,1000)
            src=program(f'let r:Result[Int]=result_ok({n});println(result_or(r,0))')
            self.both(src,f"{n}\n")

    def test_cli_decimal_result(self):
        src=program('let money: Decimal=decimal("0.10")+decimal("0.20");'
                    'let data: Result[Decimal]=result_ok(money);'
                    'println(result_value(data))')
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"test.sahu"
            p.write_text(src,encoding="utf-8")
            for backend in ("tree","vm"):
                proc=subprocess.run([sys.executable,"-m","samhus","run",str(p),
                                     "--backend",backend,"--typecheck"],
                                    text=True,capture_output=True,encoding="utf-8")
                self.assertEqual(proc.returncode,0,proc.stderr)
                self.assertEqual(proc.stdout,"0.30\n")


if __name__ == "__main__":
    unittest.main()
