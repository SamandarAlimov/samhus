"""Stack value IR proof-of-concept: explicit producers, uses and join PHIs.

The value graph is a VERIFIED analysis overlay, not an executable SSA backend.
"""
from dataclasses import replace
from io import StringIO
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from samhus import SamhusError, parse_program, run_to_string
from samhus.ir import compile_ir, lower_ir
from samhus.optimizer import optimize_ir
from samhus.value_ir import analyze_value_ir, compile_value_ir, verify_value_ir
from samhus.verify import BytecodeValidationError
from samhus.vm import VirtualMachine, run_vm_to_string


def main(body):
    return "fn main() -> Unit {\n" + body + "\n}"


def run_cfg(cfg):
    output=StringIO()
    VirtualMachine(output).run(lower_ir(cfg))
    return output.getvalue()


def all_operations(value):
    return [op for fn in value.functions for block in fn.blocks
            for op in block.operations]


def all_phis(value):
    return [phi for fn in value.functions for block in fn.blocks
            for phi in block.phis]


class ValueIRTests(unittest.TestCase):
    def compile(self, source):
        value=compile_value_ir(parse_program(source))
        verify_value_ir(value)
        return value

    def differential(self, source, expected=None, optimized=False):
        parsed=parse_program(source)
        cfg=compile_ir(parsed)
        if optimized:
            cfg,_=optimize_ir(cfg)
        analysis=analyze_value_ir(cfg)
        verify_value_ir(analysis)
        tree=run_to_string(source)
        vm=run_vm_to_string(source)
        lowered=run_cfg(analysis.cfg)
        self.assertEqual(tree,vm)
        self.assertEqual(vm,lowered)
        if expected is not None:
            self.assertEqual(lowered,expected)
        return analysis

    def test_literal_producer(self):
        v=self.compile(main("println(42)"))
        op=next(o for o in all_operations(v) if o.instruction.op=="PUSH")
        self.assertIsNotNone(op.output)
        self.assertEqual(op.output_type,"Int")

    def test_binary_has_explicit_operands(self):
        v=self.compile(main("println(2+3)"))
        ops=all_operations(v)
        adds=[o for o in ops if o.instruction.op=="BINARY"]
        self.assertEqual(len(adds),1)
        add=adds[0]
        self.assertEqual(len(add.inputs),2)
        self.assertTrue(all(x.startswith("%") for x in add.inputs))
        self.assertEqual(add.output_type,"Int")
        self.differential(main("println(2+3)"),"5\n")

    def test_unary_has_operand(self):
        v=self.compile(main("println(-2)"))
        op=next(o for o in all_operations(v) if o.instruction.op=="UNARY")
        self.assertEqual(len(op.inputs),1)
        self.assertEqual(op.output_type,"Int")

    def test_call_arguments_recorded(self):
        v=self.compile(main("println(1+2)"))
        call=next(o for o in all_operations(v) if o.instruction.op=="CALL")
        self.assertEqual(len(call.inputs),1)

    def test_zero_arg_call(self):
        source="fn number()->Int{return 7}\n"+main("println(number())")
        v=self.compile(source)
        call=next(o for o in all_operations(v) if o.instruction.op=="CALL"
                  and o.instruction.arg[0]=="number")
        self.assertEqual(call.inputs,())
        self.assertEqual(call.output_type,"Int")
        self.differential(source,"7\n")

    def test_list_inputs(self):
        v=self.compile(main("println([1,2,3])"))
        op=next(o for o in all_operations(v) if o.instruction.op=="BUILD_LIST")
        self.assertEqual(len(op.inputs),3)

    def test_map_inputs(self):
        v=self.compile(main('println({"a":1,"b":2})'))
        op=next(o for o in all_operations(v) if o.instruction.op=="BUILD_MAP")
        self.assertEqual(len(op.inputs),4)

    def test_index_inputs(self):
        v=self.compile(main("println([1,2][1])"))
        op=next(o for o in all_operations(v) if o.instruction.op=="INDEX")
        self.assertEqual(len(op.inputs),2)

    def test_result_type(self):
        v=self.compile(main('let r: Result[Int]=result_ok(12);println(result_value(r))'))
        self.assertIn("Result[Int]",v.disassemble())
        self.differential(main('println(result_or(result_ok(7),9))'),"7\n")

    def test_decimal_type(self):
        v=self.compile(main('let amount: Decimal=decimal("0.10");println(amount)'))
        self.assertIn("Decimal",v.disassemble())

    def test_float_type(self):
        v=self.compile(main("let x: Float=1.5;println(x*2.0)"))
        self.assertIn("Float",v.disassemble())

    def test_null_type(self):
        v=self.compile(main("println(is_null(null))"))
        self.assertIn("Null",v.disassemble())

    def test_string_concat(self):
        v=self.compile(main('println("Sam"+"hus")'))
        self.assertIn("String",v.disassemble())

    def test_if_branch_has_two_successors(self):
        v=self.compile(main('if true {println(1)} else {println(2)}'))
        self.assertTrue(any(len(b.successors)==2 for fn in v.functions for b in fn.blocks))
        self.differential(main('if true {println(1)} else {println(2)}'),"1\n")

    def test_if_merge_empty_stack_does_not_need_phi(self):
        v=self.compile(main('if true {println(1)} else {println(2)};println(3)'))
        self.assertEqual(all_phis(v),[])

    def test_and_creates_stack_phi(self):
        code=main("let a: Bool = true; println(a && false)")
        v=self.compile(code)
        phis=all_phis(v)
        self.assertTrue(phis,v.disassemble())
        self.assertEqual(phis[0].type_name,"Bool")
        self.assertEqual(len(phis[0].incoming),2)
        self.assertEqual(len(set(name for name,_ in phis[0].incoming)),2)
        self.differential(code,"false\n")

    def test_or_creates_stack_phi(self):
        code=main("let b: Bool = false; println(b || true)")
        v=self.compile(code)
        phis=all_phis(v)
        self.assertTrue(phis,v.disassemble())
        self.assertEqual(phis[0].type_name,"Bool")
        self.differential(code,"true\n")

    def test_nested_phi(self):
        code=main("println((true && false) || (false || true))")
        v=self.compile(code)
        self.assertGreaterEqual(len(all_phis(v)),2)
        self.differential(code,"true\n")

    def test_short_circuit_preserves_errors(self):
        self.differential(main("println(false && (1/0 == 1))"),"false\n")
        self.differential(main("println(true || (1/0 == 1))"),"true\n")

    def test_while_loop(self):
        code=main("var i: Int=0;while i<5 {i=i+1};println(i)")
        v=self.compile(code)
        self.assertTrue(len(v.functions[0].blocks)>1)
        self.differential(code,"5\n")

    def test_loop_with_short_circuit_phis(self):
        code=main("var i: Int=0;while i<4 {println(i<2 && true);i=i+1}")
        v=self.compile(code)
        self.assertTrue(all_phis(v),v.disassemble())
        self.differential(code,"true\ntrue\nfalse\nfalse\n")

    def test_loop_with_nested_scope(self):
        code=main("var i: Int=0;while i<2 {let j=10;println(j+i);i=i+1}")
        self.differential(code,"10\n11\n")

    def test_multi_function(self):
        code="fn add(x:Int,y:Int)->Int{return x+y}\n"+main("println(add(20,22))")
        v=self.compile(code)
        self.assertEqual(tuple(f.name for f in v.functions),("add","main"))
        self.differential(code,"42\n")

    def test_optimized_cfg_value_graph(self):
        code=main("println(2+3*4)")
        ir,_=optimize_ir(compile_ir(parse_program(code)))
        values=analyze_value_ir(ir)
        ops=all_operations(values)
        self.assertEqual(sum(op.instruction.op=="BINARY" for op in ops),0)
        self.assertTrue(any(op.instruction.op=="PUSH" and op.instruction.arg==14 for op in ops))
        self.differential(code,"14\n",optimized=True)

    def test_duplicate_producers_never_share_id(self):
        v=self.compile(main("println(1);println(1);println(1)"))
        outputs=[op.output for op in all_operations(v) if op.output]
        self.assertEqual(len(outputs),len(set(outputs)))

    def test_phi_incoming_defined(self):
        v=self.compile(main("println(true && false)"))
        f=v.functions[0]
        outs={b.label:b.exit_stack for b in f.blocks}
        for b in f.blocks:
            for phi in b.phis:
                for pred, name in phi.incoming:
                    self.assertIn(name,outs[pred])

    def test_phi_position_stable(self):
        code=main("println(true && false)")
        one=self.compile(code)
        two=self.compile(code)
        self.assertEqual(one.disassemble(),two.disassemble())

    def test_tampered_phi_source_rejected(self):
        v=self.compile(main("println(true && false)"))
        fn=v.functions[0]
        blocks=list(fn.blocks)
        for index,block in enumerate(blocks):
            if block.phis:
                p=block.phis[0]
                invalid=replace(p,incoming=(("fake", "%fake"),)+p.incoming[1:])
                blocks[index]=replace(block,phis=(invalid,)+block.phis[1:])
                bad=replace(v,functions=(replace(fn,blocks=tuple(blocks)),))
                with self.assertRaisesRegex(BytecodeValidationError,"Invalid value IR"):
                    verify_value_ir(bad)
                return
        self.fail("Expected PHI")

    def test_tampered_operand_rejected(self):
        v=self.compile(main("println(2+3)"))
        fn=v.functions[0]
        blocks=list(fn.blocks)
        for index,block in enumerate(blocks):
            ops=list(block.operations)
            for j,op in enumerate(ops):
                if op.instruction.op=="BINARY":
                    ops[j]=replace(op,inputs=("%wrong",))
                    blocks[index]=replace(block,operations=tuple(ops))
                    bad=replace(v,functions=(replace(fn,blocks=tuple(blocks)),))
                    with self.assertRaisesRegex(BytecodeValidationError,"Invalid value IR"):
                        verify_value_ir(bad)
                    return
        self.fail("Expected binary")

    def test_tampered_result_type_rejected(self):
        v=self.compile(main("println(2+3)"))
        fn=v.functions[0]
        block=fn.blocks[0]
        ops=list(block.operations)
        first=next(i for i,o in enumerate(ops) if o.output)
        ops[first]=replace(ops[first],output_type="Float")
        bad=replace(v,functions=(replace(fn,blocks=(replace(block,operations=tuple(ops)),)+fn.blocks[1:]),))
        with self.assertRaisesRegex(BytecodeValidationError,"Invalid value IR"):
            verify_value_ir(bad)

    def test_static_checker_required(self):
        with self.assertRaises(SamhusError):
            self.compile(main('let n:Int="wrong"'))

    def test_120_generated_branch_cases(self):
        rng=random.Random(63814)
        for index in range(120):
            left=bool(rng.randint(0,1))
            right=bool(rng.randint(0,1))
            op=rng.choice(("&&","||"))
            src=main(f"println({'true' if left else 'false'} {op} {'true' if right else 'false'})")
            with self.subTest(case=index):
                self.differential(src,("true\n" if (left and right if op=="&&" else left or right) else "false\n"))

    def test_60_generated_loops(self):
        rng=random.Random(729)
        for index in range(60):
            bound=rng.randint(0,12)
            src=main(f"var i:Int=0;while i<{bound} {{i=i+1}};println(i)")
            with self.subTest(case=index):
                self.differential(src,f"{bound}\n")

    def test_cli_values(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/"main.sahu"
            file.write_text(main("println(true && false)"),encoding="utf-8")
            result=subprocess.run([sys.executable,"-m","samhus","ir",str(file),"--values"],
                                  text=True,capture_output=True,encoding="utf-8")
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn("phi(",result.stdout)
            self.assertIn("predecessors=",result.stdout)

    def test_cli_optimized_values(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/"main.sahu"
            file.write_text(main("println(2+3*4)"),encoding="utf-8")
            result=subprocess.run([sys.executable,"-m","samhus","ir",str(file),
                                   "--values","--optimize"],
                                  text=True,capture_output=True,encoding="utf-8")
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn("PUSH 14",result.stdout)

    def test_cli_values_and_types_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/"main.sahu"
            file.write_text(main("println(2)"),encoding="utf-8")
            result=subprocess.run([sys.executable,"-m","samhus","ir",str(file),
                                   "--values","--types"],
                                  text=True,capture_output=True,encoding="utf-8")
            self.assertNotEqual(result.returncode,0)
            self.assertIn("--values and --types",result.stderr)


if __name__=="__main__":
    unittest.main()
