"""Independent dominance and def-use checks for local String SSA."""
from dataclasses import replace
import unittest

from samhus import parse_program, run_to_string
from samhus.local_ssa_ir import analyze_local_ssa_ir, verify_local_ssa_ir
from samhus.local_ssa_dominance import (
    compute_dominators, verify_local_ssa_dominance,
)
from samhus.value_ir import compile_value_ir
from samhus.verify import BytecodeValidationError
from samhus.vm import run_vm_to_string


def main(body):
    return "fn main()->Unit{" + body + "}"


class LocalSSADominanceTests(unittest.TestCase):
    def graph(self, source):
        value = compile_value_ir(parse_program(source))
        report = analyze_local_ssa_ir(value)
        verify_local_ssa_ir(value, report)
        verify_local_ssa_dominance(value, report)
        self.assertFalse(report.safe_to_lower)
        self.assertEqual(run_to_string(source), run_vm_to_string(source))
        return value, report

    def diamond(self):
        return self.graph(main(
            'var s:String="a";if true{s="b"}else{s="c"};println(s)'
        ))

    def test_diamond_dominators(self):
        value, report = self.diamond()
        phi = report.phis[0]
        dom = compute_dominators(value.functions[0])
        self.assertEqual(
            dom[phi.block],
            frozenset((value.functions[0].blocks[0].label, phi.block)),
        )

    def test_loop_backedge_phi_valid(self):
        _, report = self.graph(main(
            'var s:String="a";var n:Int=0;while n<3{'
            's=s+"b";n=n+1};println(s)'
        ))
        self.assertTrue(report.phis)
        self.assertIn(report.phis[0].version,
                      {d.previous for d in report.definitions})

    def test_branch_without_write(self):
        _, report = self.graph(main(
            'let s:String="a";if true{println(1)}else{println(2)};println(s)'
        ))
        self.assertFalse(report.phis)

    def test_shadowing_valid(self):
        _, report = self.graph(main(
            'let s:String="a";if true{let s:String="b";println(s)};println(s)'
        ))
        self.assertEqual(len({d.slot for d in report.definitions}), 2)

    def test_parameter_read_valid(self):
        _, report = self.graph(
            'fn echo(s:String)->String{return s}\n' +
            main('println(echo("abc"))')
        )
        self.assertTrue(any(d.origin == "PARAMETER" for d in report.definitions))

    def test_straightline_rebind_valid(self):
        self.graph(main('var s:String="a";s="b";println(s)'))

    def test_nested_branch_in_loop_valid(self):
        self.graph(main(
            'var s:String="a";var i:Int=0;while i<2{'
            'if true{s=s+"x"}else{s=s+"y"};i=i+1};println(s)'
        ))

    def test_cross_branch_read_rejected(self):
        value, report = self.diamond()
        store = next(d for d in report.definitions if d.origin == "ASSIGN")
        altered = replace(report.reads[-1], version=store.version)
        with self.assertRaisesRegex(BytecodeValidationError, "dominate"):
            verify_local_ssa_dominance(
                value, replace(report, reads=report.reads[:-1] + (altered,))
            )

    def test_cross_branch_phi_edge_rejected(self):
        value, report = self.diamond()
        phi = report.phis[0]
        altered = replace(phi, incoming=(
            (phi.incoming[0][0], phi.incoming[1][1]),
            phi.incoming[1],
        ))
        with self.assertRaisesRegex(BytecodeValidationError, "dominate"):
            verify_local_ssa_dominance(
                value, replace(report, phis=(altered,))
            )

    def test_missing_phi_predecessor_rejected(self):
        value, report = self.diamond()
        altered = replace(report.phis[0], incoming=report.phis[0].incoming[:1])
        with self.assertRaisesRegex(BytecodeValidationError, "predecessor"):
            verify_local_ssa_dominance(
                value, replace(report, phis=(altered,))
            )

    def test_cross_slot_load_rejected(self):
        value, report = self.graph(main(
            'let a:String="a";let b:String="b";println(a)'
        ))
        other = next(d for d in report.definitions
                     if d.slot != report.reads[0].slot)
        altered = replace(report.reads[0], version=other.version)
        with self.assertRaisesRegex(BytecodeValidationError, "crosses lexical"):
            verify_local_ssa_dominance(
                value, replace(report, reads=(altered,) + report.reads[1:])
            )

    def test_unknown_version_rejected(self):
        value, report = self.graph(main('let s:String="a";println(s)'))
        altered = replace(report.reads[0], version="%unknown")
        with self.assertRaisesRegex(BytecodeValidationError, "undefined"):
            verify_local_ssa_dominance(value, replace(report, reads=(altered,)))

    def test_duplicate_definition_rejected(self):
        value, report = self.graph(main('let s:String="a";println(s)'))
        with self.assertRaisesRegex(BytecodeValidationError, "duplicate"):
            verify_local_ssa_dominance(
                value, replace(
                    report, definitions=report.definitions + (report.definitions[0],)
                )
            )

    def test_forged_store_offset_rejected(self):
        value, report = self.graph(main('let s:String="a";println(s)'))
        altered = replace(report.definitions[0], version="%store99999")
        with self.assertRaisesRegex(BytecodeValidationError, "forged"):
            verify_local_ssa_dominance(
                value, replace(report, definitions=(altered,))
            )

    def test_load_at_declare_offset_rejected(self):
        value, report = self.graph(main('let s:String="a";println(s)'))
        offset = int(report.definitions[0].version.removeprefix("%store"))
        altered = replace(report.reads[0], offset=offset)
        with self.assertRaisesRegex(BytecodeValidationError, "non-LOAD"):
            verify_local_ssa_dominance(
                value, replace(report, reads=(altered,))
            )

    def test_assignment_cannot_use_itself_as_previous(self):
        value, report = self.graph(main('var s:String="a";s="b";println(s)'))
        assignment = next(d for d in report.definitions if d.origin == "ASSIGN")
        altered = replace(assignment, previous=assignment.version)
        defs = tuple(altered if d == assignment else d for d in report.definitions)
        with self.assertRaisesRegex(BytecodeValidationError, "before local definition"):
            verify_local_ssa_dominance(value, replace(report, definitions=defs))

    def test_unknown_function_rejected(self):
        value, report = self.graph(
            'fn echo(s:String)->String{return s}\n' +
            main('println(echo("a"))')
        )
        original = next(d for d in report.definitions if d.function == "echo")
        altered = replace(original, function="ghost")
        defs = tuple(altered if d == original else d for d in report.definitions)
        with self.assertRaisesRegex(BytecodeValidationError, "missing function"):
            verify_local_ssa_dominance(value, replace(report, definitions=defs))

    def test_no_string_program(self):
        value, report = self.graph(main(
            'var n:Int=0;while n<2{n=n+1};println(n)'
        ))
        self.assertFalse(report.definitions or report.phis or report.reads)
        self.assertTrue(compute_dominators(value.functions[0]))


if __name__ == "__main__":
    unittest.main()
