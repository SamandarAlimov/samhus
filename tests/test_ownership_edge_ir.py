"""CFG-edge String owner obligations are analysis only, never native frees."""
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from samhus import parse_program, run_to_string
from samhus.ir import compile_ir
from samhus.optimizer import optimize_ir
from samhus.ownership_edge_ir import (
    analyze_edge_ownership_ir, verify_edge_ownership_ir,
)
from samhus.value_ir import analyze_value_ir, compile_value_ir
from samhus.verify import BytecodeValidationError
from samhus.vm import run_vm_to_string


def main(body):
    return "fn main()->Unit{" + body + "}"


class EdgeOwnershipIRTests(unittest.TestCase):
    def report(self, source, optimized=False):
        program = parse_program(source)
        if optimized:
            cfg, _ = optimize_ir(compile_ir(program))
            graph = analyze_value_ir(cfg)
        else:
            graph = compile_value_ir(program)
        result = analyze_edge_ownership_ir(graph)
        verify_edge_ownership_ir(graph, result)
        self.assertFalse(result.safe_to_lower)
        self.assertEqual(run_to_string(source), run_vm_to_string(source))
        return graph, result

    def test_branch_forwards_live_string_slot(self):
        _, report = self.report(main(
            'let s:String="x";if true{println(1)}else{println(2)};println(s)'
        ))
        self.assertTrue(report.edges)
        self.assertTrue(all(e.action == "FORWARD_STRING_LOCAL"
                            for e in report.edges))
        self.assertTrue(all(e.source_version == e.target_version
                            for e in report.edges))

    def test_diamond_has_distinct_phi_sources(self):
        _, r = self.report(main(
            'var s:String="initial";if true{s="a"}else{s="b"};println(s)'
        ))
        phi = [x for x in r.edges if x.action == "PHI_EDGE_OWNER_OBLIGATION"]
        self.assertEqual(len(phi), 2, r.disassemble())
        self.assertEqual(len({x.source_version for x in phi}), 2)
        self.assertEqual(len({x.target_version for x in phi}), 1)

    def test_loop_phi_tracks_backedge(self):
        _, r = self.report(main(
            'var s:String="a";var i:Int=0;while i<3{s=s+"b";i=i+1};println(s)'
        ))
        phi = [x for x in r.edges if x.action == "PHI_EDGE_OWNER_OBLIGATION"]
        self.assertEqual(len(phi), 2, r.disassemble())
        self.assertEqual(len({x.source_version for x in phi}), 2)

    def test_rebind_captures_previous_version(self):
        _, r = self.report(main(
            'var s:String="a";s="b";println(s)'
        ))
        changed = [c for c in r.cleanups
                   if c.action == "REPLACE_OWNER_OBLIGATION"]
        self.assertEqual(len(changed), 1)
        self.assertNotEqual(changed[0].old_version, changed[0].new_version)

    def test_rebind_same_source_still_requires_alias_safety(self):
        _, r = self.report(main(
            'var s:String="a";s=s;println(s)'
        ))
        changed = [c for c in r.cleanups
                   if c.action == "REPLACE_OWNER_OBLIGATION"]
        self.assertEqual(len(changed), 1)
        self.assertIn("UNMODELED_EXCEPTION_CLEANUP", r.disassemble())

    def test_nested_scope_exit_releases_in_reverse_order(self):
        _, r = self.report(main(
            'if true{let a:String="a";let b:String="b";println(a+b)}'
        ))
        release = [c for c in r.cleanups
                   if c.action == "SCOPE_EXIT_RELEASE_OBLIGATION"]
        self.assertEqual(len(release), 2)
        self.assertNotEqual(release[0].slot, release[1].slot)
        self.assertTrue(release[0].slot.startswith("local:"))

    def test_shadowed_scope_exit_does_not_drop_outer(self):
        _, r = self.report(main(
            'let s:String="outer";if true{let s:String="inner";println(s)};'
            'println(s)'
        ))
        release = [c for c in r.cleanups
                   if c.action == "SCOPE_EXIT_RELEASE_OBLIGATION"]
        self.assertEqual(len(release), 1)
        exits = [c for c in r.cleanups
                 if c.action == "RETURN_RELEASE_OBLIGATION"]
        self.assertEqual(len(exits), 1)
        self.assertNotEqual(release[0].slot, exits[0].slot)

    def test_early_return_protects_returned_stack_alias(self):
        source = ('fn choose(flag:Bool)->String{let s:String="ok";'
                  'if flag{return s};return s}\n' +
                  main('println(choose(true))'))
        _, r = self.report(source)
        releases = [c for c in r.cleanups if c.function == "choose"
                    and c.action == "RETURN_RELEASE_OBLIGATION"]
        self.assertEqual(len(releases), 2)
        self.assertTrue(all(c.return_source is not None for c in releases))
        self.assertEqual(len({c.old_version for c in releases}), 1)

    def test_implicit_return_has_cleanup_obligation(self):
        _, r = self.report(main('let s:String="a";println(s)'))
        exit_cleanups = [c for c in r.cleanups
                         if c.action == "RETURN_RELEASE_OBLIGATION"]
        self.assertEqual(len(exit_cleanups), 1)
        self.assertIsNone(exit_cleanups[0].return_source)

    def test_no_cleanup_of_caller_owned_parameters(self):
        source = ('fn echo(s:String)->String{return s}\n' +
                  main('println(echo("a"))'))
        _, r = self.report(source)
        self.assertFalse(any(c.function == "echo" for c in r.cleanups))

    def test_loop_local_scope_release_each_iteration_path(self):
        _, r = self.report(main(
            'var i:Int=0;while i<2{let s:String="x";println(s);i=i+1}'
        ))
        release = [c for c in r.cleanups
                   if c.action == "SCOPE_EXIT_RELEASE_OBLIGATION"]
        self.assertEqual(len(release), 1)
        self.assertNotIn(release[0].slot, {edge.slot for edge in r.edges})

    def test_call_may_fail_with_active_owner(self):
        _, r = self.report(main('let s:String="x";println(s)'))
        gaps = [g for g in r.exception_gaps if g.operation == "CALL"]
        self.assertTrue(gaps)
        self.assertTrue(any(g.local_versions for g in gaps))

    def test_replacement_may_fail_before_owner_swap(self):
        _, r = self.report(main('var s:String="a";s=s+"b";println(s)'))
        assign = next(c for c in r.cleanups
                      if c.action == "REPLACE_OWNER_OBLIGATION")
        gaps = [g for g in r.exception_gaps
                if g.offset == assign.offset and g.operation == "ASSIGN"]
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].local_versions[0][1], assign.old_version)

    def test_empty_string_local_graph(self):
        _, r = self.report(main('var i:Int=0;i=i+1;println(i)'))
        self.assertEqual(r.edges, ())
        self.assertEqual(r.cleanups, ())
        self.assertEqual(r.exception_gaps, ())

    def test_optimized_cfg_produces_valid_obligations(self):
        _, r = self.report(main(
            'var s:String="a";if true{s="b"}else{s="c"};println(s)'
        ), optimized=True)
        self.assertTrue(r.cleanups)

    def test_determinism(self):
        source = main(
            'var s:String="a";var i:Int=0;while i<2{s=s+"x";i=i+1};println(s)'
        )
        a = self.report(source)[1]
        b = self.report(source)[1]
        self.assertEqual(a, b)
        self.assertEqual(a.disassemble(), b.disassemble())

    def test_tampered_edge_is_rejected(self):
        graph, r = self.report(main(
            'var s:String="a";if true{s="b"};println(s)'
        ))
        self.assertTrue(r.edges)
        bogus = replace(r.edges[0], source_version="%forged")
        with self.assertRaisesRegex(BytecodeValidationError, "differ"):
            verify_edge_ownership_ir(
                graph, replace(r, edges=(bogus,) + r.edges[1:])
            )

    def test_tampered_return_cleanup_rejected(self):
        graph, r = self.report(main('let s:String="a";println(s)'))
        self.assertTrue(r.cleanups)
        with self.assertRaisesRegex(BytecodeValidationError, "differ"):
            verify_edge_ownership_ir(graph, replace(r, cleanups=()))

    def test_tampered_exception_gap_rejected(self):
        graph, r = self.report(main('let s:String="a";println(s)'))
        self.assertTrue(r.exception_gaps)
        with self.assertRaisesRegex(BytecodeValidationError, "differ"):
            verify_edge_ownership_ir(graph, replace(r, exception_gaps=()))

    def test_cli_edge_owners(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "s.sahu"
            path.write_text(main(
                'var s:String="x";if true{s="a"}else{s="b"};println(s)'
            ), encoding="utf-8")
            run = subprocess.run([
                sys.executable, "-m", "samhus", "ir", str(path),
                "--edge-owners",
            ], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("PHI_EDGE_OWNER_OBLIGATION", run.stdout)
            self.assertIn("safe_to_lower=false", run.stdout)

    def test_cli_edge_owners_optimized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "s.sahu"
            path.write_text(main('var s:String="a";println(s)'),
                            encoding="utf-8")
            run = subprocess.run([
                sys.executable, "-m", "samhus", "ir", str(path),
                "--edge-owners", "--optimize",
            ], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("String CFG ownership obligations", run.stdout)

    def test_cli_rejects_other_ir_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "s.sahu"
            path.write_text(main('println(1)'), encoding="utf-8")
            for option in ("--types", "--values", "--ownership", "--local-ssa"):
                with self.subTest(option=option):
                    run = subprocess.run([
                        sys.executable, "-m", "samhus", "ir", str(path),
                        "--edge-owners", option,
                    ], capture_output=True, text=True, encoding="utf-8")
                    self.assertNotEqual(run.returncode, 0)
                    self.assertIn("--edge-owners", run.stderr)


if __name__ == "__main__":
    unittest.main()
