"""End-to-end experiments for reliability and basic AI data-boundary helpers.

Assert / len / str / json_valid are research-prototype builtins, not a
final standard-library specification. Both backends must agree.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from samhus import SamhusError, run_to_string, parse_program
from samhus.typecheck import check_types
from samhus.vm import run_vm_to_string


def wrap(body: str) -> str:
    return "fn main() {\n" + body + "\n}"


class StandardLibraryParityTests(unittest.TestCase):
    def assert_both(self, source: str, expected: str):
        self.assertEqual(run_to_string(source), expected)
        self.assertEqual(run_vm_to_string(source), expected)
        check_types(source)

    def assert_runtime_error(self, source: str, pattern: str):
        for engine in (run_to_string, run_vm_to_string):
            with self.subTest(backend=engine.__name__):
                with self.assertRaisesRegex(SamhusError, pattern):
                    engine(source)

    def assert_static_error(self, source: str, pattern: str):
        with self.assertRaisesRegex(SamhusError, pattern):
            check_types(source)

    def test_assert_true(self):
        self.assert_both(wrap('assert(true); println("okay")'), "okay\n")

    def test_assert_false_is_failure(self):
        self.assert_runtime_error(wrap("assert(false)"), "Assertion failed")

    def test_assert_failure_source_line(self):
        source = 'fn main() {\n    assert(false)\n}'
        for engine in (run_to_string, run_vm_to_string):
            with self.assertRaises(SamhusError) as e:
                engine(source)
            self.assertEqual(e.exception.line, 2)

    def test_assert_wrong_type_runtime(self):
        self.assert_runtime_error(wrap("assert(1)"), "expected Bool, got Int")

    def test_assert_wrong_type_static(self):
        self.assert_static_error(wrap('assert("hello")'), "expected Bool, got String")

    def test_assert_wrong_arity(self):
        self.assert_runtime_error(wrap("assert(true, false)"), "assert expects 1 argument, got 2")
        self.assert_static_error(wrap("assert()"), "assert expects 1 argument, got 0")

    def test_assert_return_is_unit(self):
        self.assert_both(wrap("let x: Unit = assert(true); println(x)"), "None\n")

    def test_len_simple_string(self):
        self.assert_both(wrap('println(len("Samhus"))'), "6\n")

    def test_len_unicode_codepoints(self):
        self.assert_both(wrap('println(len("🙂"))'), "1\n")

    def test_len_empty_string(self):
        self.assert_both(wrap('println(len(""))'), "0\n")

    def test_len_wrong_type(self):
        self.assert_runtime_error(wrap("println(len(123))"), "expected String, got Int")
        self.assert_static_error(wrap("len(true)"), "expected String, got Bool")

    def test_len_return_type(self):
        self.assert_both(wrap('let n: Int = len("abc"); println(n + 2)'), "5\n")

    def test_len_wrong_arity(self):
        self.assert_runtime_error(wrap("len()"), "len expects 1 argument, got 0")

    def test_str_integer(self):
        self.assert_both(wrap('println(str(42) + "!")'), "42!\n")

    def test_str_boolean(self):
        self.assert_both(wrap('println(str(true)); println(str(false))'), "true\nfalse\n")

    def test_str_string(self):
        self.assert_both(wrap('println(str("value"))'), "value\n")

    def test_str_unit(self):
        self.assert_both(wrap('println(str(assert(true)))'), "unit\n")

    def test_str_wrong_arity(self):
        self.assert_static_error(wrap("str()"), "str expects 1 argument, got 0")

    def test_json_object(self):
        self.assert_both(wrap(r'println(json_valid("{\"model\":\"Alsahu\",\"tokens\":12}"))'), "true\n")

    def test_json_array(self):
        self.assert_both(wrap('println(json_valid("[1,2,3]"))'), "true\n")

    def test_json_integer(self):
        self.assert_both(wrap('println(json_valid("42"))'), "true\n")

    def test_json_boolean(self):
        self.assert_both(wrap('println(json_valid("true"))'), "true\n")

    def test_json_invalid(self):
        self.assert_both(wrap('println(json_valid("{broken"))'), "false\n")

    def test_json_trailing_comma(self):
        self.assert_both(wrap('println(json_valid("[1,2,]"))'), "false\n")

    def test_json_empty(self):
        self.assert_both(wrap('println(json_valid(""))'), "false\n")

    def test_json_wrong_type(self):
        self.assert_runtime_error(wrap("json_valid(true)"), "expected String, got Bool")
        self.assert_static_error(wrap("json_valid(10)"), "expected String, got Int")

    def test_json_arity(self):
        self.assert_runtime_error(wrap("json_valid()"), "json_valid expects 1 argument, got 0")

    def test_json_nonfinite_strict(self):
        for item in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(item=item):
                self.assert_both(wrap(f'println(json_valid("{item}"))'), "false\n")

    def test_nested_calls(self):
        self.assert_both(
            wrap('assert(json_valid("{\\"ok\\":true}")); println(str(len("Alsamos")))'),
            "7\n",
        )

    def test_reserved_names(self):
        for name in ("assert", "len", "str", "json_valid", "println"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(SamhusError, "reserved builtin"):
                    parse_program(f"fn {name}() {{}}\nfn main() {{}}")

    def test_multiple_errors_evaluated_in_order(self):
        self.assert_runtime_error(wrap("assert(false); println(1 / 0)"), "Assertion failed")

    def test_cli_vm_typecheck_full_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "sample.sahu"
            file.write_text(
                wrap('assert(json_valid("{\\"healthy\\":true}")); println(len("AI"))'),
                encoding="utf-8",
            )
            for backend in ("tree", "vm"):
                with self.subTest(backend=backend):
                    run = subprocess.run(
                        [sys.executable, "-m", "samhus", "run", str(file),
                         "--backend", backend, "--typecheck"],
                        text=True, capture_output=True,
                    )
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertEqual(run.stdout, "2\n")


if __name__ == "__main__":
    unittest.main()
