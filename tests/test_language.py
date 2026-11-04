"""Executable expectations for the experimental Samhus grammar."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from samhus import SamhusError, parse, run_to_string


def program(body: str) -> str:
    return f"fn main() {{\n{body}\n}}"


class SamhusLanguageTests(unittest.TestCase):
    def test_hello(self):
        self.assertEqual(run_to_string(program('println("Hello, Samhus!")')), "Hello, Samhus!\n")

    def test_arithmetic_precedence(self):
        self.assertEqual(run_to_string(program("println(2 + 3 * 4)\nprintln((2 + 3) * 4)")), "14\n20\n")

    def test_negative_integer_division(self):
        self.assertEqual(run_to_string(program("println(-7 / 2)\nprintln(7 / -2)")), "-3\n-3\n")

    def test_large_integer_division_is_exact(self):
        self.assertEqual(run_to_string(program("println(999999999999999999999 / 3)")), "333333333333333333333\n")

    def test_strings_and_escapes(self):
        self.assertEqual(run_to_string(program(r'println("hello\nworld")')), "hello\nworld\n")

    def test_string_concatenation(self):
        self.assertEqual(run_to_string(program('println("Sam" + "hus")')), "Samhus\n")

    def test_booleans(self):
        self.assertEqual(run_to_string(program("println(true && !false)\nprintln(1 < 2)")), "true\ntrue\n")

    def test_short_circuit(self):
        self.assertEqual(run_to_string(program("println(false && (1 / 0 == 0))\nprintln(true || (1 / 0 == 0))")), "false\ntrue\n")

    def test_let_and_var(self):
        self.assertEqual(run_to_string(program("let a = 10\nvar b = a\nb = b + 2\nprintln(b)")), "12\n")

    def test_if_else(self):
        self.assertEqual(run_to_string(program('if 3 > 4 { println("no") } else { println("yes") }')), "yes\n")

    def test_if_scoping(self):
        self.assertEqual(run_to_string(program('let a = 5\nif true { let a = 6\nprintln(a) }\nprintln(a)')), "6\n5\n")

    def test_branch_can_modify_outer_var(self):
        self.assertEqual(run_to_string(program('var a = 1\nif true { a = 4 }\nprintln(a)')), "4\n")

    def test_immutable_assignment_rejected(self):
        with self.assertRaisesRegex(SamhusError, "immutable"):
            run_to_string(program("let a = 1\na = 2"))

    def test_undefined_name_rejected(self):
        with self.assertRaisesRegex(SamhusError, "Undefined variable"):
            run_to_string(program("println(missing)"))

    def test_duplicate_declaration_rejected(self):
        with self.assertRaisesRegex(SamhusError, "already declared"):
            run_to_string(program("let a = 1\nlet a = 2"))

    def test_zero_division_rejected(self):
        with self.assertRaisesRegex(SamhusError, "Division by zero"):
            run_to_string(program("println(1 / 0)"))

    def test_invalid_type_rejected(self):
        with self.assertRaisesRegex(SamhusError, "requires integers"):
            run_to_string(program('println("a" - 1)'))

    def test_bool_not_an_int(self):
        with self.assertRaisesRegex(SamhusError, "requires integers"):
            run_to_string(program('println(true + 1)'))

    def test_missing_main_rejected(self):
        with self.assertRaisesRegex(SamhusError, r"only 'fn main\(\)'"):
            parse("fn hello() {}")

    def test_unterminated_string_diagnostic(self):
        with self.assertRaises(SamhusError) as failure:
            parse(program('println("oops)'))
        self.assertGreater(failure.exception.line, 0)
        self.assertGreater(failure.exception.column, 0)

    def test_invalid_character_diagnostic(self):
        with self.assertRaisesRegex(SamhusError, "Unexpected character"):
            parse(program("println(@)"))

    def test_comment_and_optional_semicolons(self):
        self.assertEqual(run_to_string(program("let a = 2; // comment\nprintln(a);")), "2\n")

    def test_cli_run_and_check(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.sahu"
            path.write_text(program('println("ok")'), encoding="utf-8")
            for action, expected in (("run", "ok\n"), ("check", "Syntax OK:")):
                result = subprocess.run([sys.executable, "-m", "samhus", action, str(path)], text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected, result.stdout)


if __name__ == "__main__":
    unittest.main()
