"""Research-only SSA-style local String store versions and PHI edges."""
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from samhus import parse_program, run_to_string
from samhus.local_ssa_ir import analyze_local_ssa_ir, verify_local_ssa_ir
from samhus.value_ir import compile_value_ir
from samhus.verify import BytecodeValidationError
from samhus.vm import run_vm_to_string


def main(body):
    return "fn main()->Unit{" + body + "}"


class LocalStringSSATests(unittest.TestCase):
    def analysis(self, source):
        graph = compile_value_ir(parse_program(source))
        report = analyze_local_ssa_ir(graph)
        verify_local_ssa_ir(graph, report)
        self.assertFalse(report.safe_to_lower)
        self.assertEqual(run_to_string(source), run_vm_to_string(source))
        return report

    def test_parameter_and_return(self):
        report = self.analysis(
            'fn echo(s:String)->String{return s}\n' + main('println(echo("abc"))')
        )
        parameter = next(x for x in report.definitions if x.function == "echo")
        self.assertEqual(parameter.origin, "PARAMETER")
        self.assertEqual(parameter.version, "%arg0")
        self.assertTrue(any(x.version == "%arg0" for x in report.reads))

    def test_straight_line_rebinding_has_unique_versions(self):
        r = self.analysis(main('var s:String="a";s="b";println(s)'))
        writes = [d for d in r.definitions if d.origin != "PARAMETER"]
        self.assertEqual(len(writes), 2)
        self.assertNotEqual(writes[0].version, writes[1].version)
        self.assertEqual(writes[1].previous, writes[0].version)
        self.assertEqual(r.reads[-1].version, writes[1].version)
        self.assertEqual(r.phis, ())

    def test_branch_join_has_explicit_two_edge_phi(self):
        r = self.analysis(main(
            'var s:String="init";if true{s="yes"}else{s="no"};println(s)'
        ))
        self.assertEqual(len(r.phis), 1, r.disassemble())
        phi = r.phis[0]
        self.assertEqual(len(phi.incoming), 2)
        versions = {v for _, v in phi.incoming}
        self.assertEqual(versions, {d.version for d in r.definitions
                                    if d.origin == "ASSIGN"})
        self.assertEqual(r.reads[-1].version, phi.version)

    def test_only_one_branch_mutates_local(self):
        r = self.analysis(main('var s:String="x";if true{s="y"};println(s)'))
        self.assertEqual(len(r.phis), 1, r.disassemble())
        self.assertEqual(
            {v for _, v in r.phis[0].incoming},
            {d.version for d in r.definitions}
        )

    def test_unmodified_branch_has_no_phi(self):
        r = self.analysis(main(
            'let s:String="stable";if true{println(1)}else{println(2)};println(s)'
        ))
        self.assertEqual(r.phis, ())

    def test_while_loop_has_backedge_phi(self):
        r = self.analysis(main(
            'var s:String="a";var i:Int=0;'
            'while i<3{s=s+"b";i=i+1};println(s)'
        ))
        self.assertTrue(r.phis, r.disassemble())
        phi = r.phis[0]
        self.assertEqual(len(phi.incoming), 2)
        self.assertIn(phi.version, {d.previous for d in r.definitions})
        self.assertEqual(r.reads[-1].version, phi.version)

    def test_loop_without_string_write_has_no_phi(self):
        r = self.analysis(main(
            'let s:String="hello";var i:Int=0;while i<3{i=i+1};println(s)'
        ))
        self.assertEqual(r.phis, ())

    def test_nested_shadowing_produces_distinct_slots(self):
        r = self.analysis(main(
            'let s:String="outer";if true{let s:String="inner";println(s)};println(s)'
        ))
        writes = [d for d in r.definitions if d.origin == "DECLARE"]
        self.assertEqual(len(writes), 2)
        self.assertNotEqual(writes[0].slot, writes[1].slot)
        self.assertEqual(r.reads[-1].version, writes[0].version)

    def test_nested_scope_discard_does_not_escape(self):
        r = self.analysis(main(
            'if true {let s:String="inside";println(s)};println(1)'
        ))
        self.assertEqual(r.phis, ())
        self.assertEqual(len(r.reads), 1)

    def test_early_return_read_has_correct_version(self):
        r = self.analysis(
            'fn choose(flag:Bool)->String{let s:String="hi";'
            'if flag{return s};return s}\n'
            + main('println(choose(true))')
        )
        reads = [x.version for x in r.reads if x.function == "choose"]
        self.assertEqual(len(reads), 2)
        self.assertEqual(reads[0], reads[1])

    def test_many_acyclic_chained_joins(self):
        r = self.analysis(main(
            'var s:String="a";if true{s="b"}else{s="c"};'
            'if false{s="d"}else{s="e"};println(s)'
        ))
        self.assertEqual(len(r.phis), 2, r.disassemble())
        self.assertEqual(r.reads[-1].version, r.phis[-1].version)

    def test_deterministic_report(self):
        src = main('var s:String="a";while false{s="x"};println(s)')
        r1 = self.analysis(src)
        r2 = self.analysis(src)
        self.assertEqual(r1, r2)
        self.assertEqual(r1.disassemble(), r2.disassemble())

    def test_no_string_locals_no_versions(self):
        r = self.analysis(main('var n:Int=2;println(n+3)'))
        self.assertEqual(r.definitions, ())
        self.assertEqual(r.reads, ())
        self.assertEqual(r.phis, ())

    def test_modified_phi_incoming_rejected(self):
        src = main('var s:String="a";if true{s="b"}else{s="c"};println(s)')
        graph = compile_value_ir(parse_program(src))
        r = analyze_local_ssa_ir(graph)
        self.assertTrue(r.phis)
        bad_phi = replace(r.phis[0], incoming=(("fake", "%fake"),))
        with self.assertRaisesRegex(BytecodeValidationError, "differs"):
            verify_local_ssa_ir(graph, replace(r, phis=(bad_phi,) + r.phis[1:]))

    def test_modified_read_source_rejected(self):
        graph = compile_value_ir(parse_program(main(
            'let s:String="ok";println(s)'
        )))
        r = analyze_local_ssa_ir(graph)
        bad = replace(r.reads[0], version="%wrong")
        with self.assertRaises(BytecodeValidationError):
            verify_local_ssa_ir(graph, replace(r, reads=(bad,) + r.reads[1:]))

    def test_cli_local_ssa(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.sahu"
            p.write_text(main(
                'var s:String="x";if true{s="a"}else{s="b"};println(s)'
            ), encoding="utf-8")
            output = subprocess.run(
                [sys.executable, "-m", "samhus", "ir", str(p), "--local-ssa"],
                text=True, capture_output=True, encoding="utf-8"
            )
            self.assertEqual(output.returncode, 0, output.stderr)
            self.assertIn("phi(", output.stdout)
            self.assertIn("safe_to_lower=false", output.stdout)

    def test_cli_optimized_local_ssa(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.sahu"
            p.write_text(main('var s:String="a";println(s)'), encoding="utf-8")
            output = subprocess.run(
                [sys.executable, "-m", "samhus", "ir", str(p),
                 "--local-ssa", "--optimize"],
                text=True, capture_output=True, encoding="utf-8"
            )
            self.assertEqual(output.returncode, 0, output.stderr)
            self.assertIn("Local String store versions", output.stdout)

    def test_cli_rejects_conflicting_modes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.sahu"
            p.write_text(main('println(1)'), encoding="utf-8")
            for mode in ("--values", "--ownership", "--types"):
                output = subprocess.run(
                    [sys.executable, "-m", "samhus", "ir", str(p),
                     "--local-ssa", mode],
                    text=True, capture_output=True, encoding="utf-8"
                )
                self.assertNotEqual(output.returncode, 0)
                self.assertIn("--local-ssa", output.stderr)


if __name__ == "__main__":
    unittest.main()
