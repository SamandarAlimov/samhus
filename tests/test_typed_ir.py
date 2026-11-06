"""Conservative type-flow IR conformance, convergence and CLI tests."""
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from samhus import SamhusError, parse_program
from samhus.ir import compile_ir, lower_ir
from samhus.typed_ir import TypeState, analyze_ir, compile_typed_ir, _join
from samhus.verify import BytecodeValidationError
from samhus.vm import VirtualMachine
from samhus.runtime import Interpreter
from io import StringIO


def main(body):
    return "fn main() -> Unit {\n" + body + "\n}"


def state_after(program, opcode):
    compiled = compile_typed_ir(parse_program(program))
    fn = compiled.cfg.functions[-1]
    code = lower_ir(compiled.cfg).functions[-1].instructions
    mapping = dict(compiled.states[-1])
    for i, inst in enumerate(code):
        if inst.op == opcode:
            return mapping[i + 1] if i + 1 in mapping else mapping[i]
    raise AssertionError("Missing " + opcode)


class TypedIRTests(unittest.TestCase):
    def analyze(self, source):
        return compile_typed_ir(parse_program(source))

    def has_type(self, source, kind):
        analysis = self.analyze(source)
        text = analysis.disassemble()
        self.assertIn(kind, text, text)
        self.assertEqual(analysis.disassemble(), text)
        return analysis

    def test_simple_int(self):
        self.has_type(main("let x: Int=1; println(x+2)"), "x:Int")

    def test_boolean(self):
        self.has_type(main("let ready: Bool=true; if ready {println(1)}"), "ready:Bool")

    def test_string(self):
        self.has_type(main('let name: String="Samhus"; println(name)'), "name:String")

    def test_float(self):
        self.has_type(main("let x: Float=1.25; println(x+2)"), "x:Float")

    def test_decimal(self):
        self.has_type(main('let price: Decimal=decimal("0.10");println(price)'), "price:Decimal")

    def test_null(self):
        self.has_type(main("let nothing: Null=null; println(is_null(nothing))"), "nothing:Null")

    def test_list(self):
        self.has_type(main("let scores: List[Int]=[1,2]; println(scores[0])"), "scores:List[Int]")

    def test_map(self):
        self.has_type(main('let m: Map[String,Int]={"x":2}; println(m["x"])'),
                      "m:Map[String,Int]")

    def test_result(self):
        self.has_type(main('let r: Result[Int]=result_ok(42);println(result_value(r))'),
                      "r:Result[Int]")

    def test_function_parameters(self):
        self.has_type("fn square(x: Int) -> Int {return x*x}\nfn main(){println(square(3))}",
                      "x:Int")

    def test_multi_function(self):
        analysis = self.analyze("fn f(x: Int)->Int{return x*2}\n"
                                "fn g(y: String)->String{return y}\n"
                                "fn main(){println(f(2));println(g(\"ok\"))}")
        self.assertEqual(len(analysis.functions) if hasattr(analysis,"functions")
                         else len(analysis.cfg.functions),3)

    def test_loop_converges(self):
        self.has_type(main("var i: Int=0; while i<10 {i=i+1}; println(i)"), "i:Int")

    def test_nested_loop_converges(self):
        self.has_type(main("var i: Int=0; while i<3 {var j: Int=0; "
                           "while j<4 {j=j+1}; i=i+1}; println(i)"),"i:Int")

    def test_if_else_merge(self):
        self.has_type(main("var i: Int=1; if i>0 {i=i+1} else {i=i-1};println(i)"),
                      "i:Int")

    def test_short_circuit_and(self):
        self.analyze(main("let a: Bool=true; println(a && false)"))

    def test_short_circuit_or(self):
        self.analyze(main("let a: Bool=true; println(a || false)"))

    def test_any_from_json(self):
        self.has_type(main('let obj=json_parse("{\\"x\\":42}");println(obj["x"])'),
                      "obj:Any")

    def test_empty_list(self):
        self.has_type(main("let xs: List[Int]=[];println(xs)"), "xs:List[Int]")

    def test_collection_join_to_any(self):
        a=TypeState(("List[Int]",), ((("x","Int"),),))
        b=TypeState(("List[String]",), ((("x","String"),),))
        joined=_join(a,b,"fn",0)
        self.assertEqual(joined.stack,("Any",))
        self.assertEqual(joined.scopes,((("x","Any"),),))

    def test_join_preserves_matching(self):
        a=TypeState(("Int",), ((("x","Bool"),),))
        self.assertEqual(_join(a,a,"f",0),a)

    def test_join_rejects_scope_shape(self):
        a=TypeState((), ((("x","Int"),),))
        b=TypeState((), ((("y","Int"),),))
        with self.assertRaisesRegex(BytecodeValidationError,"symbol-state mismatch"):
            _join(a,b,"f",0)

    def test_join_rejects_stack_shape(self):
        a=TypeState(("Int",), ((),))
        b=TypeState(("Int","Bool"), ((),))
        with self.assertRaisesRegex(BytecodeValidationError,"shape mismatch"):
            _join(a,b,"f",0)

    def test_static_error_still_reported(self):
        with self.assertRaisesRegex(SamhusError,"Type mismatch"):
            self.analyze(main('let x: Int="wrong"'))

    def test_static_return_error_still_reported(self):
        with self.assertRaisesRegex(SamhusError,"Type mismatch"):
            self.analyze("fn bad() -> Int {return false}\nfn main(){}")

    def test_conservatively_untyped_param(self):
        self.has_type("fn f(v){println(v)}\nfn main(){f(1)}", "v:Any")

    def test_inferred_local(self):
        self.has_type(main("let n=42;println(n)"), "n:Int")

    def test_ir_dynamic_index(self):
        self.analyze(main('let data=json_parse("{\\"a\\":[1,2]}"); println(data["a"][0])'))

    def test_ir_finite_float(self):
        self.analyze(main("println((1.25+1.75)>2.0)"))

    def test_ir_unreachable_return(self):
        self.analyze("fn f() -> Int {return 1;println(2)}\nfn main(){println(f())}")

    def test_analysis_does_not_change_execution(self):
        src=main("var i: Int=0; while i<5 {println(i);i=i+1}")
        ast=parse_program(src)
        analysis=compile_typed_ir(ast)
        bytecode=lower_ir(analysis.cfg)
        vm=StringIO()
        tree=StringIO()
        VirtualMachine(vm).run(bytecode)
        Interpreter(tree).run(ast)
        self.assertEqual(vm.getvalue(), tree.getvalue())
        self.assertEqual(vm.getvalue(),"0\n1\n2\n3\n4\n")

    def test_100_generated_arithmetic(self):
        rng=random.Random(29341)
        for i in range(100):
            a,b=rng.randint(0,100),rng.randint(1,100)
            src=main(f"let a: Int={a};let b: Int={b};println((a+b)*2)")
            with self.subTest(i=i):
                self.analyze(src)

    def test_50_generated_branches(self):
        rng=random.Random(9283)
        for i in range(50):
            n=rng.randint(-40,40)
            src=main(f"var x:Int={n};if x>0 {{x=x+1}} else {{x=x-1}};println(x)")
            with self.subTest(i=i):
                self.analyze(src)

    def test_cli_types(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/"main.sahu"
            p.write_text(main("let value: Int=5;println(value)"),encoding="utf-8")
            result=subprocess.run([sys.executable,"-m","samhus","ir",str(p),"--types"],
                                  text=True,capture_output=True,encoding="utf-8")
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn("value:Int",result.stdout)

    def test_cli_types_bad_program(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/"main.sahu"
            p.write_text(main('let value: Int="bad"'),encoding="utf-8")
            result=subprocess.run([sys.executable,"-m","samhus","ir",str(p),"--types"],
                                  text=True,capture_output=True,encoding="utf-8")
            self.assertNotEqual(result.returncode,0)
            self.assertIn("Type mismatch",result.stderr)


if __name__ == "__main__":
    unittest.main()
