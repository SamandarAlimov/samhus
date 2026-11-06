"""Semantics-preserving opt-in CFG IR literal folding regression suite."""
from io import StringIO
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from samhus import parse_program, run_to_string, SamhusError
from samhus.ir import compile_ir, lower_ir
from samhus.optimizer import optimize_ir, OptimizationStats
from samhus.vm import VirtualMachine, run_vm_to_string


def main(body):
    return "fn main() -> Unit {\n" + body + "\n}"


def run_optimized(src, *, max_steps=100_000):
    result,_stats = optimize_ir(compile_ir(parse_program(src)))
    buffer = StringIO()
    VirtualMachine(buffer,max_steps=max_steps).run(lower_ir(result))
    return buffer.getvalue()


def capture(fn, src, **kwargs):
    try:
        return ("ok", fn(src,**kwargs))
    except SamhusError as ex:
        return ("error", str(ex))


class OptimizerTests(unittest.TestCase):
    def compare(self, code, expected=None, *, max_steps=100_000):
        original = capture(run_vm_to_string,code)
        optimized = capture(run_optimized,code,max_steps=max_steps)
        self.assertEqual(original,optimized,code)
        self.assertEqual(original,capture(run_to_string,code),code)
        if expected is not None:
            self.assertEqual(optimized,("ok",expected))
        return optimized

    def optimize(self, code):
        return optimize_ir(compile_ir(parse_program(code)))

    def test_arithmetic_folding(self):
        code=main("println(2+3*4)")
        original=compile_ir(parse_program(code))
        changed,stats=self.optimize(code)
        before=sum(len(block.instructions) for f in original.functions for block in f.blocks)
        after=sum(len(block.instructions) for f in changed.functions for block in f.blocks)
        self.assertLess(after,before)
        self.assertEqual(stats.folded_binary,2)
        self.assertEqual(stats.total,2)
        self.compare(code,"14\n")

    def test_float_math(self):
        self.compare(main("println(1.25+0.75)"),"2.0\n")

    def test_signed_division(self):
        self.compare(main("println(-9/2)"),"-4\n")

    def test_compare_int_float(self):
        self.compare(main("println(3.0>=2)"),"true\n")

    def test_string_concat(self):
        self.compare(main('println("Sam"+"hus")'),"Samhus\n")

    def test_boolean_equality_strict(self):
        self.compare(main("println(1==true);println(1!=true)"),"false\ntrue\n")

    def test_null_equality(self):
        self.compare(main("println(null==null)"),"true\n")

    def test_boolean_not(self):
        self.compare(main("println(!false);println(!true)"),"true\nfalse\n")

    def test_negative_zero_float(self):
        self.compare(main("println(-0.0)"),"-0.0\n")

    def test_overflow_runtime_error_preserved(self):
        self.compare(main("println(1e308 * 1e308)"))
        changed,stats=self.optimize(main("println(1e308 * 1e308)"))
        self.assertEqual(stats.folded_binary,0)
        self.assertIn("BINARY",changed.disassemble())

    def test_division_by_zero_not_folded(self):
        code=main("println(2/0)")
        got=self.compare(code)
        self.assertEqual(got[0],"error")
        self.assertIn("Division by zero",got[1])
        changed,stats=self.optimize(code)
        self.assertEqual(stats.folded_binary,0)
        self.assertIn("BINARY",changed.disassemble())

    def test_non_numeric_addition_unchanged(self):
        code=main('println("x"+4)')
        self.compare(code)
        _ir,stats=self.optimize(code)
        self.assertEqual(stats.folded_binary,0)

    def test_bad_unary_unmodified(self):
        code=main('println(-"abc")')
        self.compare(code)
        _ir,stats=self.optimize(code)
        self.assertEqual(stats.folded_unary,0)

    def test_undefined_variable(self):
        self.compare(main("println(missing)"))

    def test_bad_type_runtime(self):
        self.compare(main('let n: Int = "oops";println(n)'))

    def test_side_effect_call_not_folded(self):
        code=main('println(str(2)+str(3))')
        original=compile_ir(parse_program(code))
        changed,stats=self.optimize(code)
        self.assertEqual(stats.folded_binary,0)
        self.assertEqual(stats.folded_unary,0)
        self.assertEqual(lower_ir(original).disassemble(),lower_ir(changed).disassemble())
        self.compare(code,"23\n")

    def test_function_call_order(self):
        code='fn side(x:Int)->Int {println(x);return x}\n'+main("println(side(1)+side(2))")
        self.compare(code,"1\n2\n3\n")

    def test_while_loop(self):
        self.compare(main("var i=0;while i<4 {println(i+1);i=i+1}"),"1\n2\n3\n4\n")

    def test_branches(self):
        self.compare(main('if 2*3==6 {println(1+2)} else {println(10+20)}'),"3\n")

    def test_short_circuit_and(self):
        self.compare(main('println(false && (1/0 == 1))'),"false\n")

    def test_short_circuit_or(self):
        self.compare(main('println(true || (1/0 == 1))'),"true\n")

    def test_unreachable_return(self):
        code='fn f()->Int{return 4+5;println(1/0)}\n'+main("println(f())")
        self.compare(code,"9\n")

    def test_scope_lookups(self):
        code=main("let x=10;if true {let x=20;println(x+2)};println(x)")
        self.compare(code,"22\n10\n")

    def test_map_literal_with_pure_values(self):
        self.compare(main('let d={"a":1+2};println(d["a"])'),"3\n")

    def test_list_literal_with_pure_values(self):
        self.compare(main("println([1+2,3*4])"),"[3, 12]\n")

    def test_decimal_runtime_not_optimized(self):
        code=main('println(decimal("0.10")+decimal("0.20"))')
        self.compare(code,"0.30\n")
        changed,stats=self.optimize(code)
        self.assertEqual(stats.folded_binary,0)

    def test_result_runtime_unchanged(self):
        self.compare(main('println(result_or(result_err("x"),3+4))'),"7\n")

    def test_float_division_zero(self):
        self.compare(main("println(1.0/0.0)"))

    def test_constant_discard(self):
        code=main("42;println(99)")
        optimized,stats=self.optimize(code)
        self.assertGreaterEqual(stats.discarded_literals,1)
        self.assertNotIn("POP", [ins.op for fn in optimized.functions
                                 for b in fn.blocks for ins in b.instructions
                                 if ins.op=="POP" and ins.arg==42])
        self.compare(code,"99\n")

    def test_source_step_count_preserved(self):
        code=main("var i=0;while i<10 {i=i+1};println(i)")
        self.compare(code,"10\n")

    def test_no_extra_user_call(self):
        code='fn effect()->Int {println(19);return 10}\n'+main("println(effect()+2*3)")
        self.compare(code,"19\n16\n")

    def test_optimizer_idempotent(self):
        code=main("println((1+2)*(3+4))")
        once,_=self.optimize(code)
        twice,stats=optimize_ir(once)
        self.assertEqual(stats.total,0)
        self.assertEqual(once.disassemble(),twice.disassemble())

    def test_ir_verified_after_optimize(self):
        from samhus.ir import verify_ir
        code=main("if true {println((5+5)*2)} else {println(3)}")
        optimized,stats=self.optimize(code)
        verify_ir(optimized)
        self.assertEqual(run_optimized(code),"20\n")

    def test_100_random_arithmetic(self):
        rng=random.Random(97231)
        for i in range(100):
            a,b,c=(rng.randint(-50,50) for _ in range(3))
            code=main(f"println((({a})+({b}))*({c}))")
            with self.subTest(case=i):
                self.compare(code)

    def test_100_random_conditions(self):
        rng=random.Random(413)
        for i in range(100):
            a,b,c=(rng.randint(-50,50) for _ in range(3))
            code=main(f"if ({a})+({b})<({c}) {{println(11+22)}} else {{println(13*3)}}")
            with self.subTest(case=i):
                self.compare(code)

    def test_cli_opt_disassembly(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"example.sahu"
            path.write_text(main("println(2+3*4)"),encoding="utf-8")
            result=subprocess.run([sys.executable,"-m","samhus","ir",str(path),"--optimize"],
                                  text=True,capture_output=True,encoding="utf-8")
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn("PUSH 14",result.stdout)

    def test_cli_run_optimized(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"example.sahu"
            path.write_text(main("println(2+3*4)"),encoding="utf-8")
            result=subprocess.run([sys.executable,"-m","samhus","run",str(path),
                                   "--backend","ir","--optimize","--typecheck"],
                                  text=True,capture_output=True,encoding="utf-8")
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout,"14\n")

    def test_cli_reject_opt_on_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"example.sahu"
            path.write_text(main("println(1)"),encoding="utf-8")
            result=subprocess.run([sys.executable,"-m","samhus","run",str(path),
                                   "--backend","tree","--optimize"],
                                  text=True,capture_output=True,encoding="utf-8")
            self.assertNotEqual(result.returncode,0)
            self.assertIn("--optimize requires --backend ir",result.stderr)

    def test_cli_reject_opt_with_types(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"example.sahu"
            path.write_text(main("println(1)"),encoding="utf-8")
            result=subprocess.run([sys.executable,"-m","samhus","ir",str(path),
                                   "--types","--optimize"],
                                  text=True,capture_output=True,encoding="utf-8")
            self.assertNotEqual(result.returncode,0)

if __name__=="__main__":
    unittest.main()
