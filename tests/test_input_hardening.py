"""Adversarial lexical/parser resource tests and deterministic malformed-input corpus."""
import random
import string
import unittest
from unittest.mock import patch

from samhus import SamhusError, parse_program, run_to_string
from samhus.lexer import lex
from samhus.vm import run_vm_to_string


def wrap(body):
    return "fn main() {\n" + body + "\n}"


class InputHardeningTests(unittest.TestCase):
    def test_source_size_rejected(self):
        with patch("samhus.lexer.MAX_SOURCE_CHARS", 30):
            with self.assertRaisesRegex(SamhusError, "Source size limit"):
                lex("x" * 31)

    def test_source_size_boundary(self):
        with patch("samhus.lexer.MAX_SOURCE_CHARS", 5):
            self.assertEqual(lex("true ")[0].text, "true")

    def test_token_limit_rejected(self):
        with patch("samhus.lexer.MAX_TOKENS", 5):
            with self.assertRaisesRegex(SamhusError, "Token count limit"):
                lex("x x x x x x")

    def test_token_limit_boundary(self):
        with patch("samhus.lexer.MAX_TOKENS", 5):
            self.assertEqual(len(lex("x x x x x")), 6)

    def test_numeric_token_oversize(self):
        with patch("samhus.lexer.MAX_NUMBER_CHARS", 16):
            with self.assertRaisesRegex(SamhusError, "Numeric literal length"):
                lex("1" * 17)

    def test_float_token_oversize(self):
        with patch("samhus.lexer.MAX_NUMBER_CHARS", 16):
            with self.assertRaisesRegex(SamhusError, "Numeric literal length"):
                lex("1." + "2" * 20)

    def test_numeric_host_int_limit_not_leaked(self):
        with self.assertRaisesRegex(SamhusError, "Numeric literal length"):
            parse_program(wrap("println(" + "9" * 5000 + ")"))

    def test_string_token_oversize(self):
        with patch("samhus.lexer.MAX_STRING_CHARS", 8):
            with self.assertRaisesRegex(SamhusError, "String literal length"):
                lex('"123456789"')

    def test_string_limit_boundary(self):
        with patch("samhus.lexer.MAX_STRING_CHARS", 8):
            self.assertEqual(lex('"12345678"')[0].text, "12345678")

    def test_expression_parenthesis_nesting(self):
        with patch("samhus.parser.MAX_EXPRESSION_DEPTH", 20):
            with self.assertRaisesRegex(SamhusError, "Expression nesting limit"):
                parse_program(wrap("println(" + "(" * 30 + "1" + ")" * 30 + ")"))

    def test_expression_unary_nesting(self):
        with patch("samhus.parser.MAX_EXPRESSION_DEPTH", 20):
            with self.assertRaisesRegex(SamhusError, "Expression nesting limit"):
                parse_program(wrap("println(" + "-" * 30 + "1)"))

    def test_expression_list_nesting(self):
        with patch("samhus.parser.MAX_EXPRESSION_DEPTH", 20):
            with self.assertRaisesRegex(SamhusError, "Expression nesting limit"):
                parse_program(wrap("println(" + "[" * 30 + "1" + "]" * 30 + ")"))

    def test_expression_mixed_nesting(self):
        with patch("samhus.parser.MAX_EXPRESSION_DEPTH", 20):
            with self.assertRaisesRegex(SamhusError, "Expression nesting limit"):
                parse_program(wrap("println(" + "len(" * 25 + "[1]" + ")" * 25 + ")"))

    def test_expression_depth_counter_restored(self):
        from samhus.parser import Parser
        parser = Parser(wrap("println(1 + 2); println(3)"))
        parsed = parser.parse_program()
        self.assertEqual(len(parsed.functions[0].body), 2)
        self.assertEqual(parser.expression_depth, 0)

    def test_hardening_both_execution_paths(self):
        src = wrap("println(" + "(" * 200 + "1" + ")" * 200 + ")")
        for backend in (run_to_string, run_vm_to_string):
            with self.subTest(backend=backend.__name__):
                with self.assertRaisesRegex(SamhusError, "Expression nesting limit"):
                    backend(src)

    def test_error_position(self):
        with patch("samhus.lexer.MAX_NUMBER_CHARS", 7):
            with self.assertRaises(SamhusError) as cm:
                parse_program(wrap("let a = 1\nprintln(99999999)"))
            self.assertEqual(cm.exception.line, 3)
            self.assertGreater(cm.exception.column, 1)

    def test_valid_program_unchanged(self):
        src = wrap('let a: Int = 12; println(a * 2)')
        self.assertEqual(run_to_string(src), "24\n")
        self.assertEqual(run_vm_to_string(src), "24\n")

    def test_250_malformed_inputs(self):
        rng = random.Random(301126)
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()[]{};:,.?\\'/+-= \n\t🙂"
        for i in range(250):
            value = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 160)))
            try:
                parse_program(wrap("println(" + value + ")"))
            except SamhusError:
                pass
            except Exception as exc:
                self.fail(f"Unexpected {type(exc).__name__} in case {i}: {value!r}")

    def test_100_valid_arithmetic_cases(self):
        rng = random.Random(2027)
        for i in range(100):
            a, b = rng.randint(-300, 300), rng.randint(-300, 300)
            src = wrap(f"println(({a}) + ({b}) * 2)")
            self.assertEqual(run_to_string(src), run_vm_to_string(src),
                             f"Tree/VM mismatch {i}")


if __name__ == "__main__":
    unittest.main()
