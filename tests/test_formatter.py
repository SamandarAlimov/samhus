"""Formatter, AST inspection, and new CLI command tests."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from samhus.astdump import dump_ast
from samhus.formatter import format_program
from samhus.typecheck import check_types
from samhus import run_to_string


class FormatterTests(unittest.TestCase):
    def test_simple_format(self):
        self.assertEqual(format_program('fn main(){println("Hi")}'), 'fn main() {\n    println("Hi")\n}\n')

    def test_blank_lines_between_functions(self):
        result = format_program('fn one(){return 1}fn main(){println(one())}')
        self.assertIn("}\n\nfn main()", result)

    def test_typed_function_format(self):
        source = "fn twice(n:Int)->Int{return n*2}fn main(){println(twice(9))}"
        result = format_program(source)
        self.assertIn("fn twice(n: Int) -> Int {", result)
        self.assertEqual(run_to_string(result), "18\n")
        check_types(result)

    def test_if_else_semantics_preserved(self):
        source = "fn main(){if 2>3{println(1)}else{println(42)}}"
        result = format_program(source)
        self.assertEqual(run_to_string(source), run_to_string(result))
        self.assertIn("} else {", result)

    def test_nested_precedence_preserved(self):
        source = "fn main(){println(4*(2+3)-1)}"
        result = format_program(source)
        self.assertEqual(run_to_string(result), "19\n")

    def test_idempotent(self):
        source = "fn plus(a:Int,b:Int)->Int{return(a+b)}fn main(){var x:Int=4;while x<6 {println(plus(x,2));x=x+1}}"
        once = format_program(source)
        twice = format_program(once)
        self.assertEqual(once, twice)
        check_types(once)

    def test_comments_are_not_preserved(self):
        self.assertNotIn("//", format_program("fn main() { // hello\nprintln(4) }"))

    def test_string_escaping(self):
        source = r'fn main(){println("a\n\"b\"")}'
        result = format_program(source)
        self.assertEqual(run_to_string(source), run_to_string(result))

    def test_unicode_preserved(self):
        source = 'fn main() { println("Assalomu alaykum") }'
        self.assertIn("Assalomu", format_program(source))

    def test_ast_json(self):
        data = json.loads(dump_ast("fn main() { println(1) }"))
        self.assertEqual(data["functions"][0]["name"], "main")
        self.assertEqual(data["functions"][0]["body"][0]["kind"], "expr")

    def test_cli_typecheck_success(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "demo.sahu"
            p.write_text("fn main(){let x:Int=4;println(x)}")
            out = subprocess.run([sys.executable, "-m", "samhus", "typecheck", str(p)], text=True, capture_output=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("Type check OK", out.stdout)

    def test_cli_typecheck_failure(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "demo.sahu"
            p.write_text('fn main(){let x:Int="wrong"}')
            out = subprocess.run([sys.executable, "-m", "samhus", "typecheck", str(p)], text=True, capture_output=True)
            self.assertEqual(out.returncode, 1)
            self.assertIn("expected Int", out.stderr)

    def test_cli_run_with_typecheck(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "demo.sahu"
            p.write_text("fn main(){let x:Int=4;println(x)}")
            out = subprocess.run([sys.executable, "-m", "samhus", "run", str(p), "--typecheck"], text=True, capture_output=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(out.stdout, "4\n")

    def test_cli_ast_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "demo.sahu"
            p.write_text("fn main() {}")
            out = subprocess.run([sys.executable, "-m", "samhus", "ast", str(p)], text=True, capture_output=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(json.loads(out.stdout)["functions"][0]["name"], "main")

    def test_cli_fmt_dry_run(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "demo.sahu"
            p.write_text('fn main(){println(42)}')
            out = subprocess.run([sys.executable, "-m", "samhus", "fmt", str(p)], text=True, capture_output=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("    println(42)", out.stdout)
            self.assertEqual(p.read_text(), 'fn main(){println(42)}')

    def test_cli_fmt_check_failure(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "demo.sahu"
            p.write_text('fn main(){println(42)}')
            out = subprocess.run([sys.executable, "-m", "samhus", "fmt", str(p), "--check"], text=True, capture_output=True)
            self.assertEqual(out.returncode, 1)
            self.assertIn("Needs formatting", out.stderr)

    def test_cli_fmt_write_then_check(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "demo.sahu"
            p.write_text("fn main(){println(42)}")
            write = subprocess.run([sys.executable, "-m", "samhus", "fmt", str(p), "--write"], text=True, capture_output=True)
            self.assertEqual(write.returncode, 0, write.stderr)
            check = subprocess.run([sys.executable, "-m", "samhus", "fmt", str(p), "--check"], text=True, capture_output=True)
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertIn("Formatting OK", check.stdout)



    def test_cli_fmt_write_rejects_comment_loss(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "demo.sahu"
            source = "fn main() { // important note\n println(42) }"
            p.write_text(source)
            out = subprocess.run([sys.executable, "-m", "samhus", "fmt", str(p), "--write"], text=True, capture_output=True)
            self.assertEqual(out.returncode, 1)
            self.assertIn("does not preserve comments", out.stderr)
            self.assertEqual(p.read_text(), source)

    def test_cli_fmt_accepts_comment_marker_inside_string(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "demo.sahu"
            p.write_text('fn main(){println("https://alsamos.com")}')
            out = subprocess.run([sys.executable, "-m", "samhus", "fmt", str(p), "--write"], text=True, capture_output=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("https://alsamos.com", p.read_text())

if __name__ == "__main__":
    unittest.main()
