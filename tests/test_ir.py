"""CFG IR smoke, structural verification, and differential execution tests."""
from dataclasses import replace
from io import StringIO
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from samhus import SamhusError, parse_program, run_to_string
from samhus.bytecode import compile_ast, compile_source, Instruction
from samhus.ir import BasicBlock, FunctionIR, compile_ir, from_bytecode, lower_ir, verify_ir
from samhus.modules import load_program
from samhus.typecheck import TypeChecker
from samhus.verify import BytecodeValidationError, verify_bytecode
from samhus.vm import VirtualMachine, run_vm_to_string


def main(body):
    return "fn main() -> Unit {\n" + body + "\n}"


def run_ir(source: str) -> str:
    p = parse_program(source)
    code = lower_ir(compile_ir(p))
    out = StringIO()
    VirtualMachine(out).run(code)
    return out.getvalue()


def result(engine, source):
    try:
        return "ok", engine(source)
    except SamhusError as exc:
        return "error", str(exc)


class IRTests(unittest.TestCase):
    def equivalent(self, source, expected=None):
        tree, vm, ir = (result(engine, source)
                        for engine in (run_to_string, run_vm_to_string, run_ir))
        self.assertEqual(tree, vm, source)
        self.assertEqual(tree, ir, source)
        if expected is not None:
            self.assertEqual(tree, ("ok", expected), source)
        return tree

    def test_straight_line(self):
        self.equivalent(main("println(1+2)"), "3\n")

    def test_entry_block(self):
        ir = compile_ir(parse_program(main("println(1)")))
        block = ir.functions[0].blocks[0]
        self.assertEqual(block.label, "b0000")
        self.assertEqual((block.entry_stack, block.entry_scopes), (0,0))
        self.assertEqual(block.successors, ())
        self.assertEqual(block.instructions[-1].op, "RETURN_VOID")

    def test_signed_int_arithmetic(self):
        self.equivalent(main("println(-15/4); println(42*3)"), "-3\n126\n")

    def test_while_loop(self):
        self.equivalent(main("var n: Int=0; while n<5 {println(n); n=n+1}"),
                        "0\n1\n2\n3\n4\n")

    def test_nested_loop(self):
        self.equivalent(main("var i=0; while i<3 {var j=0; while j<2 "
                             "{println(i*10+j);j=j+1};i=i+1}"),
                        "0\n1\n10\n11\n20\n21\n")

    def test_if_true(self):
        self.equivalent(main('if true {println("yes")} else {println("no")}'), "yes\n")

    def test_if_false(self):
        self.equivalent(main('if false {println("yes")} else {println("no")}'), "no\n")

    def test_while_false(self):
        self.equivalent(main('while false {println("never")}; println("done")'), "done\n")

    def test_short_circuit_and(self):
        self.equivalent(main('println(false && (1/0 == 0))'), "false\n")

    def test_short_circuit_or(self):
        self.equivalent(main('println(true || (1/0 == 0))'), "true\n")

    def test_boolean_dynamic_condition(self):
        self.equivalent(main('if 1 {println(0)}'))

    def test_string_comparison(self):
        self.equivalent(main('println("samhus"=="samhus")'), "true\n")

    def test_function_call(self):
        self.equivalent("fn double(n: Int) -> Int {return n*2}\n"
                        "fn main() -> Unit {println(double(21))}", "42\n")

    def test_recursion(self):
        self.equivalent("fn fact(n: Int)->Int {if n<=1{return 1};return n*fact(n-1)}\n"
                        "fn main()->Unit{println(fact(6))}", "720\n")

    def test_type_enforcement(self):
        self.equivalent(main('let x: Int = "wrong"'))

    def test_immutable_binding_error(self):
        self.equivalent(main("let n=1; n=2"))

    def test_undefined_variable_error(self):
        self.equivalent(main("println(missing)"))

    def test_list_and_index(self):
        self.equivalent(main("let nums: List[Int]=[5,10,15];println(nums[2])"), "15\n")

    def test_map_and_index(self):
        self.equivalent(main('let data: Map[String,Int]={"x":1}; println(data["x"])'), "1\n")

    def test_float(self):
        self.equivalent(main("println(1.25+0.75)"), "2.0\n")

    def test_decimal(self):
        self.equivalent(main('println(decimal("0.10")+decimal("0.20"))'), "0.30\n")

    def test_result(self):
        self.equivalent(main('let r: Result[Int]=result_ok(42);'
                             'println(result_value(r))'), "42\n")

    def test_null(self):
        self.equivalent(main('println(is_null(null))'), "true\n")

    def test_json(self):
        self.equivalent(main('println(json_encode({"success":true,"count":2}))'),
                        '{"success":true,"count":2}\n')

    def test_ir_print_contains_control_flow(self):
        text=compile_ir(parse_program(main("var i=0;while i<2 {i=i+1}"))).disassemble()
        self.assertIn("BRANCH_FALSE",text)
        self.assertIn("stack=",text)
        self.assertIn("scopes=",text)
        self.assertIn("b0000",text)

    def test_ir_no_unreachable_instructions(self):
        source="fn value()->Int{return 1; println(99)}\nfn main()->Unit{println(value())}"
        ir=compile_ir(parse_program(source))
        original=compile_source(source)
        reduced=lower_ir(ir)
        initial=len(original.functions[0].instructions)
        after=len(reduced.functions[0].instructions)
        self.assertLess(after,initial)
        self.assertNotIn("POP", [inst.op for inst in reduced.functions[0].instructions])
        self.equivalent(source,"1\n")

    def test_ir_roundtrip_verified(self):
        source=main('let data=[10,20];if true {println(data[1])} else {println(3)}')
        ir=compile_ir(parse_program(source))
        code=lower_ir(ir)
        verify_bytecode(code)
        self.assertEqual(run_ir(source), "20\n")

    def test_ir_function_signatures(self):
        ir=compile_ir(parse_program('fn run(a: List[Int])->Int{return a[0]}'
                                    '\nfn main()->Unit{println(run([2]))}'))
        fn=ir.functions[0]
        self.assertEqual(fn.params,("a",))
        self.assertEqual(fn.param_types,("List[Int]",))
        self.assertEqual(fn.return_type,"Int")

    def test_malformed_successor_rejected(self):
        ir=compile_ir(parse_program(main("println(1)")))
        function=ir.functions[0]
        block=replace(function.blocks[0],successors=("b9999",))
        bad=replace(ir,functions=(replace(function,blocks=(block,)),))
        with self.assertRaises(BytecodeValidationError):
            verify_ir(bad)

    def test_malformed_stack_state_rejected(self):
        ir=compile_ir(parse_program(main("println(1)")))
        function=ir.functions[0]
        block=replace(function.blocks[0],entry_stack=10)
        bad=replace(ir,functions=(replace(function,blocks=(block,)),))
        with self.assertRaises(BytecodeValidationError):
            lower_ir(bad)

    def test_malformed_scope_state_rejected(self):
        ir=compile_ir(parse_program(main("println(1)")))
        function=ir.functions[0]
        block=replace(function.blocks[0],entry_scopes=3)
        bad=replace(ir,functions=(replace(function,blocks=(block,)),))
        with self.assertRaises(BytecodeValidationError):
            verify_ir(bad)

    def test_malformed_duplicate_block_rejected(self):
        ir=compile_ir(parse_program(main("println(1)")))
        function=ir.functions[0]
        bad=replace(ir,functions=(replace(function,blocks=(
            function.blocks[0], function.blocks[0])),))
        with self.assertRaises(BytecodeValidationError):
            verify_ir(bad)

    def test_missing_entry_rejected(self):
        ir=compile_ir(parse_program(main("println(1)")))
        function=ir.functions[0]
        bad=replace(ir,functions=(replace(function,blocks=()),))
        with self.assertRaises(BytecodeValidationError):
            verify_ir(bad)

    def test_unknown_opcode_rejected(self):
        ir=compile_ir(parse_program(main("println(1)")))
        function=ir.functions[0]
        block=function.blocks[0]
        inst=replace(block.instructions[0],op="UNKNOWN")
        bad=replace(ir,functions=(replace(function,blocks=(
            replace(block,instructions=(inst,)+block.instructions[1:]),)),))
        with self.assertRaises(BytecodeValidationError):
            lower_ir(bad)

    def test_unknown_jump_label_rejected(self):
        ir=compile_ir(parse_program(main("if true {println(1)}")))
        function=ir.functions[0]
        blocks=list(function.blocks)
        for i,block in enumerate(blocks):
            for j,inst in enumerate(block.instructions):
                if inst.op=="JUMP":
                    patched=list(block.instructions)
                    patched[j]=replace(inst,arg="b9999")
                    blocks[i]=replace(block,instructions=tuple(patched),
                                      successors=("b9999",))
                    bad=replace(ir,functions=(replace(function,blocks=tuple(blocks)),))
                    with self.assertRaises(BytecodeValidationError):
                        lower_ir(bad)
                    return
        self.fail("Expected JUMP in compiled if")

    def test_200_randomized_expression_parity(self):
        rng=random.Random(58370)
        operators=("+","-","*","/","<",">","<=",">=","==","!=")
        for i in range(200):
            a=rng.randint(-500,500)
            b=rng.randint(-500,500)
            op=rng.choice(operators)
            s=main(f"println(({a}) {op} ({b}))")
            with self.subTest(case=i):
                self.equivalent(s)

    def test_100_randomized_control_flow_parity(self):
        rng=random.Random(775)
        for i in range(100):
            start=rng.randint(0,10)
            stop=start+rng.randint(0,8)
            s=main(f"var i={start};while i<{stop}{{if i=={start+1}"
                   "{println(i)} else {println(i*2)};i=i+1}")
            with self.subTest(case=i):
                self.equivalent(s)

    def test_multifile_ir(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            (path/"lib.sahu").write_text("fn mul(x:Int)->Int{return x*3}",encoding="utf-8")
            (path/"main.sahu").write_text('import "lib.sahu"\n'
                                          'fn main()->Unit{println(mul(14))}',encoding="utf-8")
            program=load_program(path/"main.sahu")
            TypeChecker(program).check()
            ir=compile_ir(program)
            code=lower_ir(ir)
            out=StringIO()
            VirtualMachine(out).run(code)
            self.assertEqual(out.getvalue(),"42\n")

    def test_cli_ir(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"prog.sahu"
            source.write_text(main("println(19+23)"),encoding="utf-8")
            result=subprocess.run([sys.executable,"-m","samhus","ir",str(source)],
                                  text=True,encoding="utf-8",capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn("b0000:",result.stdout)

    def test_cli_run_ir(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"prog.sahu"
            source.write_text(main("println(19+23)"),encoding="utf-8")
            result=subprocess.run([sys.executable,"-m","samhus","run",str(source),
                                   "--backend","ir","--typecheck"],
                                  text=True,encoding="utf-8",capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout,"42\n")


if __name__ == "__main__":
    unittest.main()
