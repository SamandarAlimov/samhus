"""String stack-temporary origins and use sites; no runtime drop."""
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from samhus import parse_program, run_to_string
from samhus.ir import compile_ir
from samhus.optimizer import optimize_ir
from samhus.temporary_lifetime_ir import (
    analyze_temporary_lifetime_ir, verify_temporary_lifetime_ir,
)
from samhus.value_ir import analyze_value_ir, compile_value_ir
from samhus.verify import BytecodeValidationError
from samhus.vm import run_vm_to_string


def main(body):
    return "fn main()->Unit{" + body + "}"


class TemporaryLifetimeIRTests(unittest.TestCase):
    def analyze(self, source, optimized=False):
        parsed = parse_program(source)
        if optimized:
            optimized_cfg, _ = optimize_ir(compile_ir(parsed))
            graph = analyze_value_ir(optimized_cfg)
        else:
            graph = compile_value_ir(parsed)
        report = analyze_temporary_lifetime_ir(graph)
        verify_temporary_lifetime_ir(graph, report)
        self.assertFalse(report.safe_to_lower)
        self.assertEqual(run_to_string(source), run_vm_to_string(source))
        return graph, report

    def test_static_literal_is_borrowed(self):
        _, report = self.analyze(main('println("hi")'))
        self.assertIn("STATIC_LITERAL", {x.kind for x in report.origins})
        self.assertEqual(report.unwind_gaps, ())

    def test_concat_creates_distinct_result(self):
        _, r = self.analyze(main('println("A"+"B")'))
        concat = next(x for x in r.origins if x.kind == "CONCAT_RESULT")
        self.assertEqual(len(concat.inputs), 2)
        self.assertTrue(any(u.value == concat.value
                            and u.action == "CALL_ARGUMENT_ABI_REQUIRED"
                            for u in r.uses))

    def test_index_has_parent_dependency(self):
        _, r = self.analyze(main('println("🌍🚀"[1])'))
        result = next(x for x in r.origins if x.kind == "PARENT_DEPENDENT_VIEW")
        self.assertEqual(len(result.inputs), 1)
        self.assertTrue(any(u.action == "SLICE_PARENT_DEPENDENCY"
                            and u.value == result.inputs[0] for u in r.uses))

    def test_local_load_points_to_store_version(self):
        _, r = self.analyze(main('let s:String="a"+"b";println(s)'))
        loaded = next(x for x in r.origins if x.kind == "LOCAL_LOAD_ALIAS")
        self.assertTrue(loaded.local_store.startswith("%store"))

    def test_local_rebind_load_uses_latest_store(self):
        _, r = self.analyze(main('var s:String="a";s="b";println(s)'))
        loaded = next(x for x in r.origins if x.kind == "LOCAL_LOAD_ALIAS")
        assigned = next(u for u in r.uses if u.action == "REPLACE_LOCAL_OBLIGATION")
        self.assertIsNotNone(assigned.value)
        self.assertNotEqual(loaded.local_store, "%store0")

    def test_call_result_is_unknown_owned_abi(self):
        source = 'fn build()->String{return "x"+"y"}\n' + main('println(build())')
        _, r = self.analyze(source)
        self.assertIn("CALL_RESULT_UNKNOWN_ABI",
                      {x.kind for x in r.origins})

    def test_call_result_discard_is_obligation(self):
        source = 'fn build()->String{return "x"+"y"}\n' + main('build()')
        _, r = self.analyze(source)
        self.assertTrue(any(u.action == "DISCARD_RESULT_OBLIGATION"
                            for u in r.uses))
        self.assertTrue(any(u.last_operation_use_in_block
                            and u.action == "DISCARD_RESULT_OBLIGATION"
                            for u in r.uses))

    def test_store_transfer_is_not_a_free(self):
        _, r = self.analyze(main('let s:String="A"+"B";println(s)'))
        self.assertIn("STORE_IN_LOCAL_OBLIGATION", {u.action for u in r.uses})
        self.assertIn("safe_to_lower=false", r.disassemble())

    def test_assignment_rhs_alias_is_not_safely_droppable(self):
        _, r = self.analyze(main('var s:String="a";s=s;println(s)'))
        self.assertIn("REPLACE_LOCAL_OBLIGATION", {u.action for u in r.uses})
        self.assertTrue(any(x.kind == "LOCAL_LOAD_ALIAS" for x in r.origins))

    def test_return_value_escapes_function(self):
        source = ('fn echo(s:String)->String{return s}\n'
                  + main('println(echo("ok"))'))
        _, r = self.analyze(source)
        escaping = [u for u in r.uses if u.function == "echo"
                    and u.action == "ESCAPE_TO_CALLER"]
        self.assertEqual(len(escaping), 1)

    def test_nested_concat_reports_active_stack_temp(self):
        _, r = self.analyze(main('println(("a"+"b")+("c"+"d"))'))
        gaps = [x for x in r.unwind_gaps
                if x.operation == "BINARY"
                and x.live_string_temporaries]
        self.assertTrue(gaps)
        self.assertTrue(any(x.kind == "CONCAT_RESULT" for x in r.origins))

    def test_stack_unwind_detects_possible_failure_in_call(self):
        _, r = self.analyze(main('println("a"+"b")'))
        self.assertTrue(any(g.operation == "CALL" for g in r.unwind_gaps))

    def test_static_literal_does_not_need_temp_unwind(self):
        _, r = self.analyze(main('println("a")'))
        self.assertEqual(r.unwind_gaps, ())

    def test_branch_keeps_local_alias_facts(self):
        _, r = self.analyze(main(
            'var s:String="a";if true{s="b"}else{s="c"};println(s)'
        ))
        self.assertTrue(any(x.kind == "LOCAL_LOAD_ALIAS" for x in r.origins))

    def test_loop_backedge_preserves_temp_facts(self):
        _, r = self.analyze(main(
            'var s:String="a";var n:Int=0;while n<2{s=s+"b";n=n+1};println(s)'
        ))
        self.assertIn("CONCAT_RESULT", {x.kind for x in r.origins})
        self.assertTrue(r.unwind_gaps)

    def test_unicode_concat_and_slice(self):
        _, r = self.analyze(main('println(("🌍"+"🚀")[0])'))
        self.assertEqual(
            {x.kind for x in r.origins if x.kind in {
                "CONCAT_RESULT", "PARENT_DEPENDENT_VIEW"
            }}, {"CONCAT_RESULT", "PARENT_DEPENDENT_VIEW"}
        )

    def test_optimized_cfg_is_supported(self):
        _, r = self.analyze(main('println("a"+"b")'), optimized=True)
        self.assertTrue(r.origins)

    def test_deterministic_analysis(self):
        source = main('let s:String="x"+"y";println(s[0])')
        self.assertEqual(self.analyze(source)[1], self.analyze(source)[1])

    def test_no_string_has_no_temporary_facts(self):
        _, r = self.analyze(main('println(1+2)'))
        self.assertEqual((r.origins, r.uses, r.unwind_gaps), ((), (), ()))

    def test_missing_origin_is_rejected(self):
        graph, r = self.analyze(main('println("a"+"b")'))
        with self.assertRaisesRegex(BytecodeValidationError, "differs"):
            verify_temporary_lifetime_ir(graph, replace(r, origins=()))

    def test_wrong_use_action_is_rejected(self):
        graph, r = self.analyze(main('println("a"+"b")'))
        changed = replace(r.uses[0], action="INVALID")
        with self.assertRaisesRegex(BytecodeValidationError, "differs"):
            verify_temporary_lifetime_ir(
                graph, replace(r, uses=(changed,) + r.uses[1:])
            )

    def test_wrong_unwind_gap_is_rejected(self):
        graph, r = self.analyze(main('println("a"+"b")'))
        self.assertTrue(r.unwind_gaps)
        with self.assertRaisesRegex(BytecodeValidationError, "differs"):
            verify_temporary_lifetime_ir(graph, replace(r, unwind_gaps=()))

    def test_cli_temp_owners(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p.sahu"
            path.write_text(main('println("a"+"b")'), encoding="utf-8")
            result = subprocess.run([
                sys.executable, "-m", "samhus", "ir", str(path),
                "--temp-owners",
            ], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("CONCAT_RESULT", result.stdout)
            self.assertIn("safe_to_lower=false", result.stdout)

    def test_cli_temp_owners_optimize(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p.sahu"
            path.write_text(main('println("a"+"b")'), encoding="utf-8")
            result = subprocess.run([
                sys.executable, "-m", "samhus", "ir", str(path),
                "--temp-owners", "--optimize",
            ], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("String stack temporary obligations", result.stdout)

    def test_cli_refuses_other_viewers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p.sahu"
            path.write_text(main('println("a")'), encoding="utf-8")
            for other in ("--types", "--values", "--ownership",
                          "--local-ssa", "--edge-owners"):
                with self.subTest(other=other):
                    result = subprocess.run([
                        sys.executable, "-m", "samhus", "ir", str(path),
                        "--temp-owners", other,
                    ], capture_output=True, text=True, encoding="utf-8")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("--temp-owners", result.stderr)


if __name__ == "__main__":
    unittest.main()
