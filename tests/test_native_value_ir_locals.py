"""End-to-end local variable, lexical scope, and loop tests for native Value IR."""
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from samhus import SamhusError, parse_program, run_to_string
from samhus.native_value_ir import emit_value_ir_c

CC = next((x for x in ("cc", "gcc", "clang") if shutil.which(x)), None)


def main(body):
    return "fn main() -> Unit {\n" + body + "\n}"


class NativeLocalTests(unittest.TestCase):
    def native(self, source, expected=None):
        if not CC:
            self.skipTest("C11 compiler unavailable")
        c = emit_value_ir_c(parse_program(source))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            path=root/"test.c"
            binary=root/("test.exe" if sys.platform=="win32" else "test")
            path.write_text(c, encoding="utf-8")
            build=subprocess.run([CC,"-std=c11","-O2",str(path),"-o",str(binary)],
                                 text=True,capture_output=True,encoding="utf-8")
            self.assertEqual(build.returncode,0,build.stderr+"\n"+c[-6000:])
            result=subprocess.run([str(binary)],text=True,capture_output=True,encoding="utf-8")
            if expected is not None:
                self.assertEqual((result.returncode,result.stdout),(0,expected),result.stderr)
                self.assertEqual(result.stdout,run_to_string(source))
            return result

    def test_inferred_immutable(self):
        self.native(main("let number=12;println(number*3)"),"36\n")

    def test_typed_mutable(self):
        self.native(main("var number:Int=12;number=number+30;println(number)"),"42\n")

    def test_bool_mutable_toggle(self):
        self.native(main("var on:Bool=false;on=!on;println(on)"),"true\n")

    def test_inner_shadowing(self):
        self.native(main("let n:Int=1;if true {let n:Int=2;println(n)};println(n)"),
                    "2\n1\n")

    def test_deep_shadowing(self):
        self.native(main("let n:Int=1;if true {let n:Int=2;"
                         "if true {let n:Int=3;println(n)};println(n)};println(n)"),
                    "3\n2\n1\n")

    def test_branch_scopes(self):
        self.native(main("if false {let n:Int=1;println(n)}"
                         "else {let n:Int=2;println(n)}"),"2\n")

    def test_branch_assignment(self):
        self.native(main("var value:Int=3;if value<4 {value=value*14} "
                         "else {value=1};println(value)"),"42\n")

    def test_boolean_branch(self):
        self.native(main("var ok:Bool=true;if ok && true {ok=false};println(ok)"),
                    "false\n")

    def test_zero_iterations(self):
        self.native(main("var i:Int=7;while false {i=i+1};println(i)"),"7\n")

    def test_sum_1_to_10(self):
        self.native(main("var i:Int=0;var total:Int=0;"
                         "while i<=10 {total=total+i;i=i+1};println(total)"),
                    "55\n")

    def test_nested_loops(self):
        self.native(main("var i:Int=0;while i<3 {var j:Int=0;"
                         "while j<2 {println(i*10+j);j=j+1};i=i+1}"),
                    "0\n1\n10\n11\n20\n21\n")

    def test_loop_local_reinit(self):
        self.native(main("var i:Int=0;while i<3 {let twice:Int=i*2;"
                         "println(twice);i=i+1}"),"0\n2\n4\n")

    def test_loop_if_else(self):
        self.native(main("var i:Int=0;while i<4 {if i<2 {println(i)}"
                         "else {println(i*2)};i=i+1}"),"0\n1\n4\n6\n")

    def test_loop_short_circuit(self):
        self.native(main("var i:Int=0;while i<4 {println(i<2 && true);i=i+1}"),
                    "true\ntrue\nfalse\nfalse\n")

    def test_loop_overflow_error(self):
        result=self.native(main("var i:Int=9223372036854775807;"
                                "while i>0 {i=i+1}"))
        self.assertEqual(result.returncode,2)
        self.assertIn("integer overflow",result.stderr)

    def test_native_step_budget(self):
        result=self.native(main("while true {}"))
        self.assertEqual(result.returncode,2)
        self.assertIn("Execution step limit exceeded (100000)",result.stderr)

    def test_constant_immutable_reassign_error(self):
        with self.assertRaises(SamhusError):
            emit_value_ir_c(parse_program(main("let a:Int=1;a=2;println(a)")))

    def test_undefined_variable_error(self):
        with self.assertRaises(SamhusError):
            emit_value_ir_c(parse_program(main("println(unknown)")))

    def test_scope_escape_error(self):
        with self.assertRaises(SamhusError):
            emit_value_ir_c(parse_program(main("if true {let n:Int=1};println(n)")))

    def test_duplicate_declaration_error(self):
        with self.assertRaises(SamhusError):
            emit_value_ir_c(parse_program(main("let n:Int=1;let n:Int=2")))

    def test_incompatible_assignment_error(self):
        with self.assertRaises(SamhusError):
            emit_value_ir_c(parse_program(main("var n:Int=1;n=true")))

    def test_25_generated_scopes_single_executable(self):
        cases=[]
        for i in range(25):
            cases.append(f"if {i}<13 {{let z:Int={i};println(z)}}"
                         f"else {{let z:Int={i}*2;println(z)}}")
        source=main(";".join(cases))
        self.native(source,run_to_string(source))

    def test_100_iteration_sum(self):
        source=main("var i:Int=0;var t:Int=0;"
                    "while i<100 {t=t+i;i=i+1};println(t)")
        self.native(source,"4950\n")

    def test_randomized_arithmetic_in_loop(self):
        rng=random.Random(20261107)
        loops=[]
        for _ in range(15):
            limit=rng.randint(0,20)
            loops.append(f"var i:Int=0;var sum:Int=0;"
                         f"while i<{limit} {{sum=sum+i;i=i+1}};"
                         "println(sum)")
        source=main(";".join(loops))
        self.native(source,run_to_string(source))

    def test_source_tick_budget_matches_default_vm(self):
        # The native source TICK budget is fixed at 100000 for this prototype.
        # An infinite loop must fail instead of hanging indefinitely.
        code=emit_value_ir_c(parse_program(main("while true {}")))
        self.assertIn("sh_tick();",code)
        self.assertIn("100000",code)


if __name__ == "__main__":
    unittest.main()
