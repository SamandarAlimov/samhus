"""Experimental native C backend tests, semantics, and unsupported-case safety."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from samhus import SamhusError
from samhus.native_c import emit_c


def main(body: str) -> str:
    return f"fn main() -> Unit {{\n{body}\n}}"


class NativeEmissionTests(unittest.TestCase):
    def test_simple_hello(self):
        output = emit_c(main('println("Hello, Samhus!")'))
        self.assertIn("sh_fn_main", output)
        self.assertIn("int main(void)", output)
        self.assertIn("puts", output)

    def test_forward_call(self):
        source = main("println(square(6))") + "\nfn square(x: Int) -> Int {return x*x}"
        result = emit_c(source)
        self.assertIn("sh_fn_square", result)

    def test_name_collision_with_runtime_helper(self):
        source = main("println(add(1,2))") + "\nfn add(a: Int,b: Int)->Int{return a+b}"
        c = emit_c(source)
        self.assertIn("sh_fn_add", c)
        self.assertIn("static int64_t sh_add", c)

    def test_literals_at_edge(self):
        emit_c(main("println(9223372036854775807)"))
        emit_c(main("println(-9223372036854775808)"))

    def test_literal_out_of_range_rejected(self):
        with self.assertRaisesRegex(SamhusError, "64-bit range"):
            emit_c(main("println(9223372036854775808)"))

    def test_integer_semantics_not_silently_truncated(self):
        with self.assertRaisesRegex(SamhusError, "64-bit range"):
            emit_c(main("println(999999999999999999999999999)"))

    def test_no_implicit_any(self):
        with self.assertRaisesRegex(SamhusError, "explicit return type"):
            emit_c("fn main() {}")

    def test_untyped_parameters_rejected(self):
        with self.assertRaisesRegex(SamhusError, "every native parameter"):
            emit_c(main("println(helper(1))") + "\nfn helper(x) -> Int {return x}")

    def test_implicit_variable_type_rejected(self):
        with self.assertRaisesRegex(SamhusError, "require explicit"):
            emit_c(main("var x = 3; println(x)"))

    def test_mismatch_detected(self):
        with self.assertRaisesRegex(SamhusError, "Type mismatch"):
            emit_c(main('let x: Int = "hi"'))

    def test_string_concat_rejected(self):
        with self.assertRaisesRegex(SamhusError, "restricted to Int"):
            emit_c(main('println("a" + "b")'))

    def test_ai_json_builtin_rejected(self):
        with self.assertRaisesRegex(SamhusError, "unsupported"):
            emit_c(main('println(json_valid("[]"))'))

    def test_builtin_str_rejected(self):
        with self.assertRaisesRegex(SamhusError, "unsupported"):
            emit_c(main('println(str(42))'))

    def test_nul_text_rejected(self):
        with self.assertRaisesRegex(SamhusError, "NUL"):
            emit_c(main('println("a\x00b")'))

    def test_unit_return_expression_rejected(self):
        with self.assertRaisesRegex(SamhusError, "Unit functions"):
            emit_c(main("return println(2)"))

    def test_wrong_main_return_rejected(self):
        with self.assertRaisesRegex(SamhusError, "native main"):
            emit_c("fn main() -> Int { return 42 }")

    def test_immutable_assignment_rejected(self):
        with self.assertRaisesRegex(SamhusError, "immutable"):
            emit_c(main("let x: Int = 1; x = 2"))

    def test_compiler_output_includes_overflow_guards(self):
        c = emit_c(main("println(2*3)"))
        self.assertIn('sh_fail("integer overflow")', c)
        self.assertIn("INT64_MIN", c)
        self.assertIn("sh_mul", c)

    def test_logic_and_branch(self):
        result = emit_c(main("if true && false { println(1) } else { println(2) }"))
        self.assertIn("sh_tmp_", result)

    def test_unique_generated_variables(self):
        result = emit_c(main("var tmp_1: Int=3; println(tmp_1+2)"))
        self.assertIn("sh_var_tmp_1", result)
        self.assertIn("sh_tmp_", result)


@unittest.skipUnless(
    shutil.which("cc") or shutil.which("gcc") or shutil.which("clang"),
    "A C11 compiler is needed for native executable tests",
)
class NativeExecutableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")

    def build_run(self, source: str):
        with tempfile.TemporaryDirectory() as directory:
            cfile = Path(directory) / "sample.c"
            output = Path(directory) / ("sample.exe" if sys.platform == "win32" else "sample")
            cfile.write_text(emit_c(source), encoding="utf-8")
            compile_result = subprocess.run(
                [self.cc, "-std=c11", "-O2", str(cfile), "-o", str(output)],
                text=True, capture_output=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            return subprocess.run([str(output)], text=True, encoding="utf-8", capture_output=True)

    def test_native_hello(self):
        r = self.build_run(main('println("Hello, Samhus!")'))
        self.assertEqual((r.returncode, r.stdout), (0, "Hello, Samhus!\n"))

    def test_native_factorial(self):
        s = """fn factorial(n: Int) -> Int {
if n <= 1 { return 1 }
return n * factorial(n - 1)
}
fn main() -> Unit { println(factorial(7)) }"""
        r = self.build_run(s)
        self.assertEqual((r.returncode, r.stdout), (0, "5040\n"))

    def test_native_loop_and_sums(self):
        s = main("var i: Int=0; var n: Int=0; while i<10 { n=n+i*i; i=i+1 }; println(n)")
        r = self.build_run(s)
        self.assertEqual((r.returncode, r.stdout), (0, "285\n"))

    def test_native_string_and_unicode(self):
        r = self.build_run(main('let x: String = "Assalomu alaykum, Oʻzbekiston!"; println(x)'))
        self.assertEqual((r.returncode, r.stdout), (0, "Assalomu alaykum, Oʻzbekiston!\n"))

    def test_native_boolean_short_circuit(self):
        s = main("println(true && false); println(false || true); println(true || false); println(false && true)")
        r = self.build_run(s)
        self.assertEqual((r.returncode, r.stdout), (0, "false\ntrue\ntrue\nfalse\n"))

    def test_native_shadowing(self):
        r = self.build_run(main("let x: Int=5; if true {let x: Int=8; println(x)}; println(x)"))
        self.assertEqual((r.returncode, r.stdout), (0, "8\n5\n"))

    def test_native_string_equal(self):
        r = self.build_run(main('println("Samhus"=="Samhus"); println("Samhus"!="Rust")'))
        self.assertEqual((r.returncode, r.stdout), (0, "true\ntrue\n"))

    def test_native_checked_division_zero(self):
        r = self.build_run(main("println(4/0)"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("Division by zero", r.stderr)

    def test_native_add_overflow(self):
        r = self.build_run(main("println(9223372036854775807+1)"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("integer overflow", r.stderr)

    def test_native_mul_overflow(self):
        r = self.build_run(main("println(3037000500*3037000500)"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("integer overflow", r.stderr)

    def test_native_neg_min_overflow(self):
        r = self.build_run(main("println(-(-9223372036854775808))"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("integer overflow", r.stderr)

    def test_native_nonnegative_max(self):
        r = self.build_run(main("println(9223372036854775807)"))
        self.assertEqual((r.returncode, r.stdout), (0, "9223372036854775807\n"))

    def test_native_minimum_int(self):
        r = self.build_run(main("println(-9223372036854775808)"))
        self.assertEqual((r.returncode, r.stdout), (0, "-9223372036854775808\n"))

    def test_native_assert_pass(self):
        r = self.build_run(main('assert(3 < 4); println("passed")'))
        self.assertEqual((r.returncode, r.stdout), (0, "passed\n"))

    def test_native_assert_fail(self):
        r = self.build_run(main("assert(false)"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("Assertion failed", r.stderr)

    def test_native_multi_functions(self):
        s = """fn add(a: Int, b: Int) -> Int {return a+b}
fn multiply(a: Int, b: Int) -> Int {return a*b}
fn main() -> Unit { println(multiply(add(2,3), add(4,5))) }"""
        r = self.build_run(s)
        self.assertEqual((r.returncode, r.stdout), (0, "45\n"))

    def test_native_multiple_calls_order(self):
        s = """fn first() -> Int { println("first"); return 3 }
fn second() -> Int { println("second"); return 7 }
fn sum(a: Int, b: Int) -> Int { return a+b }
fn main() -> Unit { println(sum(first(), second())) }"""
        r = self.build_run(s)
        self.assertEqual((r.returncode, r.stdout), (0, "first\nsecond\n10\n"))

    def test_native_subtraction_overflow(self):
        r = self.build_run(main("println((-9223372036854775808)-1)"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("integer overflow", r.stderr)

    def test_native_division_min_overflow(self):
        r = self.build_run(main("println((-9223372036854775808)/(-1))"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("integer overflow", r.stderr)

    def test_native_false_branch_lazy(self):
        r = self.build_run(main("println(false && (1/0==1)); println(true || (1/0==1))"))
        self.assertEqual((r.returncode, r.stdout), (0, "false\ntrue\n"))


if __name__ == "__main__":
    unittest.main()
