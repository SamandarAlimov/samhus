"""Experimental immutable List regression and cross-backend conformance."""
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from samhus import SamhusError, parse_program, run_to_string
from samhus.bytecode import compile_source
from samhus.formatter import format_program
from samhus.native_c import emit_c
from samhus.typecheck import check_types
from samhus.values import accepts, index_of, structural_equal, type_name
from samhus.vm import run_vm_to_string


def wrap(body: str) -> str:
    return "fn main() {\n" + body + "\n}"


def outcome(engine, source):
    try:
        return "ok", engine(source)
    except SamhusError as exc:
        return "error", str(exc)


class ListLanguageTests(unittest.TestCase):
    def same(self, source: str, expected: str | None = None, typed: bool = True):
        if typed:
            check_types(source)
        a, b = outcome(run_to_string, source), outcome(run_vm_to_string, source)
        self.assertEqual(a, b, f"Different backends:\n{source}\ntree={a}\nvm={b}")
        if expected is not None:
            self.assertEqual(a, ("ok", expected))
        return a

    def error(self, source: str, fragment: str):
        a = self.same(source, typed=False)
        self.assertEqual(a[0], "error")
        self.assertIn(fragment, a[1])

    def static_error(self, source: str, fragment: str):
        with self.assertRaises(SamhusError) as ctx:
            check_types(source)
        self.assertIn(fragment, str(ctx.exception))

    def test_empty_list(self):
        self.same(wrap("let x: List[Int] = []; println(x)"), "[]\n")

    def test_integer_list(self):
        self.same(wrap("let x: List[Int] = [10,20,30]; println(x[1])"), "20\n")

    def test_boolean_list(self):
        self.same(wrap("let x: List[Bool] = [true, false]; println(x[0]); println(x[1])"), "true\nfalse\n")

    def test_string_list(self):
        self.same(wrap('let x: List[String] = ["AI", "Cloud"]; println(x[1])'), "Cloud\n")

    def test_unicode_list(self):
        self.same(wrap('let x: List[String] = ["Oʻzbekiston", "🙂"]; println(x[1])'), "🙂\n")

    def test_nested_list(self):
        self.same(wrap('let x: List[List[Int]] = [[1,2],[3,4]]; println(x[1][0])'), "3\n")

    def test_mixed_dynamic_list(self):
        self.same(wrap('let x: List[Any] = [1, "text", true]; println(x)'), '[1, "text", true]\n')

    def test_list_length(self):
        self.same(wrap("println(len([1, 2, 3]))"), "3\n")

    def test_empty_list_length(self):
        self.same(wrap("println(len([]))"), "0\n")

    def test_string_index(self):
        self.same(wrap('println("Samhus"[0]); println("Samhus"[5])'), "S\ns\n")

    def test_string_unicode_index(self):
        self.same(wrap('println("🙂A"[0]); println("🙂A"[1])'), "🙂\nA\n")

    def test_append_persistent(self):
        self.same(wrap(
            "let first: List[Int] = [1,2]; let second: List[Int] = append(first,3); "
            "println(first); println(second)"
        ), "[1, 2]\n[1, 2, 3]\n")

    def test_append_empty(self):
        self.same(wrap("let x: List[String] = append([], \"hello\"); println(x[0])"), "hello\n")

    def test_append_nested(self):
        self.same(wrap("let x: List[List[Int]] = append([[1]], [2]); println(x[1][0])"), "2\n")

    def test_append_dynamic(self):
        self.same(wrap("let base: List[Any] = [1]; let x: List[Any] = append(base, \"hello\"); println(len(x))"), "2\n")

    def test_append_not_list(self):
        self.error(wrap("println(append(1,2))"), "append expects List")

    def test_append_static_error(self):
        self.static_error(wrap("println(append(1,2))"), "append expects List")

    def test_append_wrong_arity(self):
        self.error(wrap("append([1])"), "append expects 2 arguments")
        self.static_error(wrap("append([1])"), "append expects 2 arguments")

    def test_append_wrong_element(self):
        self.static_error(wrap('let x: List[Int]=[1]; println(append(x,"bad"))'), "expected Int, got String")

    def test_typed_list_literal_mismatch(self):
        self.static_error(wrap('let x: List[Int]=[1, "bad"]'), "expected Int, got String")
        self.error(wrap('let x: List[Int]=[1, "bad"]'), "expected List[Int]")

    def test_nested_typed_mismatch(self):
        self.static_error(wrap('let x: List[List[Int]]=[[1],["bad"]]'), "expected Int, got String")

    def test_typed_function_argument(self):
        self.same(
            "fn total(values: List[Int]) -> Int { var sum: Int=0; var i: Int=0; "
            "while i<len(values) {sum=sum+values[i]; i=i+1}; return sum }\n"
            "fn main() -> Unit { println(total([10, 20, 30])) }",
            "60\n",
        )

    def test_typed_function_return(self):
        self.same(
            "fn items() -> List[Int] {return [1,2,3]}\nfn main() {println(items()[2])}",
            "3\n",
        )

    def test_typed_function_mismatch_static(self):
        self.static_error(
            'fn f(values: List[Int]) -> Int { return values[0] }\n'
            'fn main() { println(f(["wrong"])) }',
            "expected Int, got String",
        )

    def test_typed_function_mismatch_runtime(self):
        self.error(
            'fn f(values: List[Int]) -> Int {return values[0]}\n'
            'fn main() {println(f(["wrong"]))}',
            "expected List[Int]",
        )

    def test_wrong_return_type(self):
        self.static_error(
            'fn wrong() -> List[Int] {return ["bad"]}\nfn main() {}',
            "expected Int, got String",
        )

    def test_dynamic_mismatch_runtime_assign(self):
        self.error(wrap('var a: List[Int]=[1]; a=append(a,"bad")'), "expected List[Int]")

    def test_out_of_bounds_positive(self):
        self.error(wrap("println([1][1])"), "Index out of bounds")

    def test_out_of_bounds_negative(self):
        self.error(wrap("println([1][-1])"), "Index out of bounds")

    def test_out_of_bounds_empty(self):
        self.error(wrap("println([][0])"), "Index out of bounds")

    def test_out_of_bounds_string(self):
        self.error(wrap('println(""[0])'), "Index out of bounds")

    def test_invalid_index_bool(self):
        self.static_error(wrap("println([1][true])"), "expected Int, got Bool")
        self.error(wrap("println([1][true])"), "Index must be Int")

    def test_invalid_index_string(self):
        self.static_error(wrap('println([1]["0"])'), "expected Int, got String")
        self.error(wrap('println([1]["0"])'), "Index must be Int")

    def test_nonindexable_value(self):
        self.static_error(wrap("println(42[0])"), "Indexing requires List or String")
        self.error(wrap("println(42[0])"), "Indexing requires List or String")

    def test_len_noncollection(self):
        self.static_error(wrap("println(len(42))"), "expected String, got Int")
        self.error(wrap("println(len(42))"), "expected String, got Int")

    def test_list_equality(self):
        self.same(wrap("println([1,2]==[1,2]); println([1]!=[2])"), "true\ntrue\n")

    def test_deep_equality(self):
        self.same(wrap("println([[1],[2]]==[[1],[2]])"), "true\n")

    def test_no_boolean_int_coercion(self):
        self.same(wrap("println([true]==[1]); println([[false]]!=[[0]])"), "false\ntrue\n")

    def test_list_string_not_equal(self):
        self.same(wrap('println([1] == "1")'), "false\n")

    def test_nested_dynamic_printing(self):
        self.same(wrap('println([[1,true],["a",false]])'), '[[1, true], ["a", false]]\n')

    def test_str_list(self):
        self.same(wrap('println(str([1,"hi",true]))'), '[1, "hi", true]\n')

    def test_list_alias_unmodified(self):
        self.same(wrap("let a: List[Int]=[1]; let b: List[Int]=a; let c: List[Int]=append(b,2); println(a); println(c)"),
                  "[1]\n[1, 2]\n")

    def test_type_names(self):
        self.assertEqual(type_name((1,2)), "List[Int]")
        self.assertEqual(type_name((1,"x")), "List[Any]")
        self.assertEqual(type_name(((1,), (2,))), "List[List[Int]]")
        self.assertTrue(accepts("List[Int]", ()))
        self.assertTrue(accepts("List[List[Int]]", ((1,),(2,))))
        self.assertFalse(accepts("List[Int]", (True,)))
        self.assertFalse(structural_equal((True,), (1,)))

    def test_type_nesting_rejected(self):
        typ = "List[" * 26 + "Int" + "]" * 26
        with self.assertRaisesRegex(SamhusError, "maximum depth"):
            parse_program(f"fn main() {{let x: {typ} = []}}")

    def test_bare_list_annotation_rejected(self):
        with self.assertRaisesRegex(SamhusError, "Expected"):
            parse_program("fn main() {let x: List=[]}")

    def test_list_ast(self):
        p = parse_program(wrap("println([1,2][0])"))
        expr = p.functions[0].body[0].expr.args[0]
        self.assertEqual(expr.kind, "index")
        self.assertEqual(expr.left.kind, "list")

    def test_disassembly(self):
        bytecode = compile_source(wrap("println([1,2][0])")).disassemble()
        self.assertIn("BUILD_LIST 2", bytecode)
        self.assertIn("INDEX", bytecode)

    def test_formatter_idempotent(self):
        source = wrap('let x:List[List[Int]]=[[1,2],[3,4]];println(x[0][1]);println(append([1],2))')
        first = format_program(source)
        self.assertEqual(format_program(first), first)
        self.assertEqual(run_to_string(source), run_to_string(first))
        self.assertEqual(run_vm_to_string(source), run_vm_to_string(first))

    def test_native_rejects_list(self):
        with self.assertRaisesRegex(SamhusError, "Native subset"):
            emit_c("fn main() -> Unit {println([1,2])}")

    def test_nested_index_error_location(self):
        source = "fn main() {\n  println([[1]][1][0])\n}"
        for engine in (run_to_string, run_vm_to_string):
            with self.assertRaises(SamhusError) as error:
                engine(source)
            self.assertEqual(error.exception.line, 2)

    def test_list_build_limit(self):
        with patch("samhus.values.MAX_LIST_ITEMS", 2):
            self.error(wrap("println([1,2,3])"), "List size limit exceeded")

    def test_append_limit(self):
        with patch("samhus.stdlib.MAX_LIST_ITEMS", 2):
            self.error(wrap("println(append([1,2],3))"), "List size limit exceeded")

    def test_100_deterministic_index_cases(self):
        rnd = random.Random(5175)
        for _ in range(100):
            size = rnd.randint(1, 25)
            data = [rnd.randint(-500, 500) for __ in range(size)]
            index = rnd.randrange(size)
            values = ",".join(str(n) if n >= 0 else f"({n})" for n in data)
            source = wrap(f"let values: List[Int] = [{values}]; println(values[{index}])")
            with self.subTest(size=size, index=index):
                self.same(source, f"{data[index]}\n")

    def test_cli_tree_vm_and_types(self):
        source = wrap("let a: List[Int]=[2,3,4]; println(a[2]); println(len(a))")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "example.sahu"
            path.write_text(source, encoding="utf-8")
            for backend in ("tree", "vm"):
                result = subprocess.run(
                    [sys.executable, "-m", "samhus", "run", str(path),
                     "--backend", backend, "--typecheck"],
                    text=True, encoding="utf-8", capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "4\n3\n")


if __name__ == "__main__":
    unittest.main()
