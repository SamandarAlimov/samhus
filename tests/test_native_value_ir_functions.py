"""Native Value IR user functions, scoped calls and recursion conformance."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from samhus import SamhusError, parse_program, run_to_string
from samhus.native_value_ir import emit_value_ir_c

CC = next((name for name in ("cc", "gcc", "clang") if shutil.which(name)), None)


class NativeUserFunctionsTests(unittest.TestCase):
    def emit(self, source):
        return emit_value_ir_c(parse_program(source))

    def native(self, source, expected=None):
        if CC is None:
            self.skipTest("C compiler unavailable")
        c = self.emit(source)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            text=path/"main.c"
            executable=path/("main.exe" if sys.platform=="win32" else "main")
            text.write_text(c,encoding="utf-8")
            built=subprocess.run([CC,"-std=c11","-O2",str(text),"-o",str(executable)],
                                 text=True,capture_output=True,encoding="utf-8")
            self.assertEqual(built.returncode,0,built.stderr+"\n"+c[-8000:])
            completed=subprocess.run([str(executable)],capture_output=True,
                                     text=True,encoding="utf-8",timeout=10)
            if expected is not None:
                self.assertEqual((completed.returncode,completed.stdout),(0,expected),
                                 completed.stderr)
                self.assertEqual(completed.stdout,run_to_string(source))
            return completed

    def test_one_argument(self):
        self.native("fn double(x:Int)->Int{return x*2}\n"
                    "fn main()->Unit{println(double(21))}","42\n")

    def test_two_arguments(self):
        self.native("fn sum(a:Int,b:Int)->Int{return a+b}\n"
                    "fn main()->Unit{println(sum(10,32))}","42\n")

    def test_forward_declaration(self):
        self.native("fn main()->Unit{println(add(20,22))}\n"
                    "fn add(a:Int,b:Int)->Int{return a+b}","42\n")

    def test_bool_return(self):
        self.native("fn is_even(n:Int)->Bool{return n/2*2==n}\n"
                    "fn main()->Unit{println(is_even(8));println(is_even(9))}",
                    "true\nfalse\n")

    def test_recursive_factorial(self):
        self.native("fn fact(n:Int)->Int{if n<=1{return 1};return n*fact(n-1)}\n"
                    "fn main()->Unit{println(fact(6))}","720\n")

    def test_recursive_fibonacci(self):
        self.native("fn fib(n:Int)->Int{if n<=1{return n};return fib(n-1)+fib(n-2)}\n"
                    "fn main()->Unit{println(fib(10))}","55\n")

    def test_multiple_calls_do_not_share_locals(self):
        self.native("fn f(x:Int)->Int{var n:Int=x;n=n+1;return n}\n"
                    "fn main()->Unit{println(f(1));println(f(9))}","2\n10\n")

    def test_nested_calls(self):
        self.native("fn plus(x:Int,y:Int)->Int{return x+y}\n"
                    "fn times(x:Int,y:Int)->Int{return x*y}\n"
                    "fn main()->Unit{println(times(plus(1,2),plus(3,4)))}","21\n")

    def test_unit_function(self):
        self.native("fn greet()->Unit{println(20);println(22)}\n"
                    "fn main()->Unit{greet()}","20\n22\n")

    def test_function_loop(self):
        self.native("fn sum(n:Int)->Int{var i:Int=0;var total:Int=0;"
                    "while i<=n{total=total+i;i=i+1};return total}\n"
                    "fn main()->Unit{println(sum(10))}","55\n")

    def test_unit_function_call_order(self):
        self.native("fn show(x:Int)->Unit{println(x)}\n"
                    "fn main()->Unit{show(1);show(2);show(3)}","1\n2\n3\n")

    def test_recursive_call_limit(self):
        outcome=self.native("fn recurse(n:Int)->Int{return recurse(n+1)}\n"
                            "fn main()->Unit{println(recurse(0))}")
        self.assertEqual(outcome.returncode,2)
        self.assertIn("Function call depth limit exceeded (128)",outcome.stderr)

    def test_recursion_returns_without_leaking_depth(self):
        self.native("fn f(n:Int)->Int{if n==0{return 0};return 1+f(n-1)}\n"
                    "fn main()->Unit{println(f(10));println(f(10))}","10\n10\n")

    def test_mutual_recursion(self):
        self.native("fn even(n:Int)->Bool{if n==0{return true};return odd(n-1)}\n"
                    "fn odd(n:Int)->Bool{if n==0{return false};return even(n-1)}\n"
                    "fn main()->Unit{println(even(10));println(odd(7))}",
                    "true\ntrue\n")

    def test_call_arguments_preserve_evaluation_order(self):
        self.native("fn trace(n:Int)->Int{println(n);return n}\n"
                    "fn add(a:Int,b:Int)->Int{return a+b}\n"
                    "fn main()->Unit{println(add(trace(1),trace(2)))}","1\n2\n3\n")

    def test_function_returns_from_nested_if(self):
        self.native("fn classify(n:Int)->Int{if n<0{return 1}"
                    "else{if n==0{return 2}else{return 3}}}\n"
                    "fn main()->Unit{println(classify(-3));"
                    "println(classify(0));println(classify(3))}","1\n2\n3\n")

    def test_untyped_parameter_rejected(self):
        with self.assertRaises(SamhusError):
            self.emit("fn f(n)->Int{return n}\nfn main()->Unit{println(f(1))}")

    def test_unsupported_string_parameter_rejected(self):
        with self.assertRaises(SamhusError):
            self.emit('fn f(n:String)->Unit{println(n)}\nfn main()->Unit{f("x")}')

    def test_wrong_argument_type_rejected(self):
        with self.assertRaises(SamhusError):
            self.emit("fn f(n:Int)->Int{return n}\nfn main()->Unit{println(f(true))}")

    def test_wrong_return_rejected(self):
        with self.assertRaises(SamhusError):
            self.emit("fn f()->Int{return true}\nfn main()->Unit{println(f())}")

    def test_missing_nonunit_return_rejected(self):
        with self.assertRaises(SamhusError):
            self.emit("fn f(n:Int)->Int{if n>0{return 1}}\n"
                      "fn main()->Unit{println(f(1))}")

    def test_reject_variable_mutation_of_parameter(self):
        with self.assertRaises(SamhusError):
            self.emit("fn f(n:Int)->Int{n=n+1;return n}\n"
                      "fn main()->Unit{println(f(2))}")

    def test_all_prototypes_precede_bodies(self):
        code=self.emit("fn main()->Unit{println(f(2))}\n"
                       "fn f(x:Int)->Int{return x+40}")
        self.assertLess(code.index("static int64_t sh_fn_1(int64_t);"),
                        code.index("static void sh_fn_main(void) {"))

    def test_cli_native_ir_user_function(self):
        if CC is None:
            self.skipTest("C compiler unavailable")
        source="fn square(n:Int)->Int{return n*n}\nfn main()->Unit{println(square(7))}"
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/"program.sahu"
            exe=Path(directory)/("prog.exe" if sys.platform=="win32" else "prog")
            file.write_text(source,encoding="utf-8")
            built=subprocess.run([sys.executable,"-m","samhus","native-ir",str(file),
                                  "-o",str(exe)],capture_output=True,text=True)
            self.assertEqual(built.returncode,0,built.stderr)
            executed=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual((executed.returncode,executed.stdout),(0,"49\n"))


if __name__ == "__main__":
    unittest.main()
