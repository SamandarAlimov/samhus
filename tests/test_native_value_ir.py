"""Native C11 generated FROM experimental Value IR (small Int/Bool subset)."""
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

from samhus import SamhusError, parse_program, run_to_string
from samhus.native_value_ir import emit_value_ir_c


def program(body):
    return "fn main() -> Unit {\n" + body + "\n}"


def compiler():
    return next((x for x in ("cc", "gcc", "clang") if shutil.which(x)), None)


class NativeValueIRTests(unittest.TestCase):
    def emit(self, code):
        return emit_value_ir_c(parse_program(code))

    def native(self, code, expected=None):
        compiler_name=compiler()
        if not compiler_name:
            self.skipTest("No C compiler available in PATH")
        ctext=self.emit(code)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            cfile=path/"program.c"
            exe=path/("program.exe" if sys.platform=="win32" else "program")
            cfile.write_text(ctext,encoding="utf-8")
            built=subprocess.run([compiler_name,"-std=c11","-O2",str(cfile),"-o",str(exe)],
                                 text=True,capture_output=True,encoding="utf-8")
            self.assertEqual(built.returncode,0,built.stderr+"\n"+ctext[-9000:])
            done=subprocess.run([str(exe)],text=True,capture_output=True,encoding="utf-8")
            if expected is not None:
                self.assertEqual((done.returncode,done.stdout),(0,expected),done.stderr)
                self.assertEqual(done.stdout,run_to_string(code))
            return done

    def test_simple_add(self):
        self.native(program("println(20+22)"),"42\n")

    def test_literal_arithmetic(self):
        self.native(program("println(2+3*4);println(16/4)"),"14\n4\n")

    def test_bool_output(self):
        self.native(program("println(true);println(false)"),"true\nfalse\n")

    def test_if_true(self):
        self.native(program('if true {println(1)} else {println(2)};println(3)'),"1\n3\n")

    def test_if_false(self):
        self.native(program('if false {println(1)} else {println(2)};println(3)'),"2\n3\n")

    def test_nested_if(self):
        code=program('if 4>2 {if false {println(0)} else {println(42)}} else {println(9)}')
        self.native(code,"42\n")

    def test_and_phi_native(self):
        self.native(program("println(true && false);println(false && true)"),
                    "false\nfalse\n")

    def test_or_phi_native(self):
        self.native(program("println(false || true);println(true || false)"),
                    "true\ntrue\n")

    def test_nested_phi_native(self):
        self.native(program("println((true && false) || (false || true))"),"true\n")

    def test_short_circuit_skips_divide_by_zero(self):
        self.native(program("println(false && (1/0==0));println(true || (1/0==0))"),
                    "false\ntrue\n")

    def test_signed_arithmetic(self):
        self.native(program("println(-15/4);println(-5*4)"),"-3\n-20\n")

    def test_assert_success(self):
        self.native(program("assert(true);println(1)"),"1\n")

    def test_assert_failure(self):
        got=self.native(program("assert(false);println(1)"))
        self.assertEqual(got.returncode,2)
        self.assertIn("Assertion failed",got.stderr)

    def test_checked_division_failure(self):
        got=self.native(program("println(1/0)"))
        self.assertEqual(got.returncode,2)
        self.assertIn("Division by zero",got.stderr)

    def test_checked_overflow_failure(self):
        got=self.native(program("println(9223372036854775807+1)"))
        self.assertEqual(got.returncode,2)
        self.assertIn("integer overflow",got.stderr)

    def test_50_generated_arithmetic_expressions(self):
        rng=random.Random(9760)
        statements=[]
        for _ in range(50):
            a=rng.randint(1,40)
            b=rng.randint(1,40)
            statements.append(f"println(({a}+{b})*2)")
        code=program(";".join(statements))
        self.native(code,run_to_string(code))

    def test_local_variables_in_subset(self):
        self.native(program("let x:Int=2;println(x+40)"),"42\n")

    def test_reject_float(self):
        with self.assertRaisesRegex(SamhusError,"unsupported value type"):
            self.emit(program("println(1.25)"))

    def test_reject_decimal(self):
        with self.assertRaises(SamhusError):
            self.emit(program('println(decimal("1.25"))'))

    def test_reject_string(self):
        with self.assertRaises(SamhusError):
            self.emit(program('println("Hello")'))

    def test_while_in_subset(self):
        self.native(program("var i:Int=0;while i<3 {println(i);i=i+1}"),
                    "0\n1\n2\n")

    def test_reject_function_calls(self):
        with self.assertRaisesRegex(SamhusError,"only main"):
            self.emit("fn add(x:Int,y:Int)->Int{return x+y}\n"+program("println(add(1,2))"))

    def test_reject_big_integer_literal(self):
        with self.assertRaisesRegex(SamhusError,"signed 64-bit"):
            self.emit(program("println(9223372036854775808)"))

    def test_codegen_gotos_and_moves(self):
        emitted=self.emit(program("println(true && false)"))
        self.assertIn("sh_move_",emitted)
        self.assertIn("goto shb_",emitted)
        self.assertIn("shv_",emitted)

    def test_cli_emit_ir_c(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"main.sahu"
            path.write_text(program("println(42)"),encoding="utf-8")
            out=subprocess.run([sys.executable,"-m","samhus","emit-ir-c",str(path)],
                               capture_output=True,text=True,encoding="utf-8")
            self.assertEqual(out.returncode,0,out.stderr)
            self.assertIn("sh_fn_main",out.stdout)

    def test_cli_native_ir(self):
        if not compiler():
            self.skipTest("No C compiler available")
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"main.sahu"
            exe=Path(folder)/("program.exe" if sys.platform=="win32" else "program")
            path.write_text(program("println(true || false);println(21*2)"),encoding="utf-8")
            out=subprocess.run([sys.executable,"-m","samhus","native-ir",str(path),
                                "-o",str(exe)],
                               capture_output=True,text=True,encoding="utf-8")
            self.assertEqual(out.returncode,0,out.stderr)
            compiled=subprocess.run([str(exe)],capture_output=True,text=True,encoding="utf-8")
            self.assertEqual((compiled.returncode,compiled.stdout),(0,"true\n42\n"))


if __name__=="__main__":
    unittest.main()
