"""Conservative, read-only ownership obligations; no runtime integration."""
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from samhus import parse_program, run_to_string
from samhus.ownership_ir import (
    OwnershipReport, analyze_ownership_ir, verify_ownership_ir,
)
from samhus.value_ir import compile_value_ir
from samhus.verify import BytecodeValidationError
from samhus.vm import run_vm_to_string


def main(body):
    return "fn main() -> Unit {\n" + body + "\n}"


class OwnershipIRTests(unittest.TestCase):
    def report(self, source):
        graph = compile_value_ir(parse_program(source))
        report = analyze_ownership_ir(graph)
        verify_ownership_ir(graph, report)
        self.assertFalse(report.safe_to_lower)
        self.assertEqual(run_to_string(source), run_vm_to_string(source))
        return graph, report

    def actions(self, source):
        return [event.action for event in self.report(source)[1].events]

    def test_literal_is_static_and_print_borrows(self):
        actions = self.actions(main('println("Samhus")'))
        self.assertIn("BORROW_STATIC_LITERAL", actions)
        self.assertIn("BORROW_CALL_ARGUMENT", actions)

    def test_concat_allocates_and_borrows_inputs(self):
        actions = self.actions(main('println("Sam"+"hus")'))
        self.assertIn("ALLOCATE_CONCAT_RESULT", actions)
        self.assertEqual(actions.count("BORROW_FOR_BINARY"), 2)

    def test_index_retains_backing_parent(self):
        actions = self.actions(main('println("🌍🚀"[1])'))
        self.assertIn("RETAIN_PARENT_FOR_SLICE", actions)
        self.assertIn("BORROW_FOR_INDEX", actions)

    def test_string_local_requires_explicit_cleanup(self):
        _, report = self.report(main(
            'var value:String="a";value="b";println(value)'
        ))
        actions = [e.action for e in report.events]
        self.assertIn("TRANSFER_OR_RETAIN_FOR_LOCAL", actions)
        self.assertIn("RETAIN_LOCAL_ON_LOAD", actions)
        self.assertTrue(any("overwrite" in b for b in report.blockers))

    def test_function_call_return_and_parameters_are_blocked(self):
        source = ('fn join(a:String,b:String)->String{return a+b}\n'
                  + main('println(join("a","b"))'))
        _, report = self.report(source)
        actions = [e.action for e in report.events]
        self.assertIn("TRANSFER_RETURN_TO_CALLER", actions)
        self.assertIn("RECEIVE_CALL_RESULT", actions)
        self.assertTrue(any("owned/borrowed ABI" in b for b in report.blockers))

    def test_unused_string_temporary_has_drop_obligation(self):
        # Only calls are permitted as expression statements in Samhus.
        source = 'fn make()->String{return "a"+"b"}\n' + main('make()')
        actions = self.actions(source)
        self.assertIn("DROP_UNUSED_TEMP", actions)

    def test_boolean_phi_is_not_string_ownership_phi(self):
        _, report = self.report(main('println(true && false)'))
        self.assertNotIn("PHI_EDGE_OWNER", [e.action for e in report.events])

    def test_no_string_program_is_empty(self):
        _, report = self.report(main('println(42)'))
        self.assertEqual(report.events, ())
        self.assertFalse(report.safe_to_lower)

    def test_nested_string_calls_keep_reference_behavior(self):
        src = ('fn greet(x:String)->String{return "Hi "+x}\n'
               + main('let x:String=greet("🌍");println(x[3])'))
        _, report = self.report(src)
        self.assertIn("RETAIN_PARENT_FOR_SLICE", [e.action for e in report.events])

    def test_while_loop_creates_local_lifetime_obligations(self):
        src = main(
            'var s:String="a";var i:Int=0;'
            'while i<3 {s=s+"b";i=i+1};println(s)'
        )
        _, report = self.report(src)
        self.assertIn("ALLOCATE_CONCAT_RESULT", [e.action for e in report.events])
        self.assertTrue(report.blockers)

    def test_analysis_is_stable(self):
        src = main('println("a"+"b")')
        graph = compile_value_ir(parse_program(src))
        self.assertEqual(analyze_ownership_ir(graph), analyze_ownership_ir(graph))

    def test_tampered_events_are_rejected(self):
        graph, report = self.report(main('println("A"+"B")'))
        self.assertTrue(report.events)
        modified = replace(report, events=report.events[1:])
        with self.assertRaisesRegex(BytecodeValidationError, "differs"):
            verify_ownership_ir(graph, modified)

    def test_tampered_blockers_are_rejected(self):
        graph, report = self.report(main('let s:String="a";println(s)'))
        modified = replace(report, blockers=())
        with self.assertRaises(BytecodeValidationError):
            verify_ownership_ir(graph, modified)

    def test_cli_shows_read_only_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.sahu"
            path.write_text(main('println("Sam"+"hus")'), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "samhus", "ir", str(path), "--ownership"],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ALLOCATE_CONCAT_RESULT", result.stdout)
            self.assertIn("safe_to_lower=false", result.stdout)

    def test_cli_ownership_and_values_are_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.sahu"
            path.write_text(main("println(1)"), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "samhus", "ir", str(path),
                 "--ownership", "--values"],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--ownership", result.stderr)

    def test_cli_ownership_works_on_optimized_cfg(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.sahu"
            path.write_text(main('println("a"+"b")'), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "samhus", "ir", str(path),
                 "--ownership", "--optimize"],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("String ownership obligations", result.stdout)


if __name__ == "__main__":
    unittest.main()
