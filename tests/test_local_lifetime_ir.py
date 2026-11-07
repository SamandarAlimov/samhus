"""Regression for lexical lifetime facts without executable auto release."""
from dataclasses import replace
import unittest

from samhus import parse_program, run_to_string
from samhus.local_lifetime_ir import analyze_local_lifetime_ir
from samhus.ownership_ir import analyze_ownership_ir, verify_ownership_ir
from samhus.value_ir import compile_value_ir
from samhus.verify import BytecodeValidationError
from samhus.vm import run_vm_to_string


def main(body):
    return "fn main()->Unit{" + body + "}"


class ScopedLifetimeTests(unittest.TestCase):
    def report(self, src):
        graph = compile_value_ir(parse_program(src))
        result = analyze_local_lifetime_ir(graph)
        combined = analyze_ownership_ir(graph)
        verify_ownership_ir(graph, combined)
        self.assertFalse(combined.safe_to_lower)
        self.assertEqual(run_to_string(src), run_vm_to_string(src))
        return result, combined

    def test_shadowing_has_distinct_lexical_slots(self):
        src = main('let s:String="A";if true {let s:String="B";println(s)};println(s)')
        result, _ = self.report(src)
        declarations = [x for x in result.events if x.action == "BIND_STRING_LOCAL"]
        self.assertEqual(len(declarations), 2)
        self.assertNotEqual(declarations[0].slot, declarations[1].slot)
        reads = [x for x in result.events if x.action == "READ_STRING_LOCAL_STORE"]
        self.assertEqual({x.slot for x in reads}, {x.slot for x in declarations})
        self.assertEqual(len([x for x in result.events
                              if x.action == "RELEASE_STRING_AT_SCOPE_EXIT"]), 1)

    def test_overwrite_identifies_previous_owner(self):
        src = main('var s:String="a";s="b";println(s)')
        result, combined = self.report(src)
        change = next(x for x in result.events if x.action == "REPLACE_STRING_LOCAL_OWNER")
        self.assertIn("declare@", change.detail)
        self.assertIn("assign@", next(
            x.detail for x in result.events if x.action == "READ_STRING_LOCAL_STORE"
        ))
        self.assertIn("REPLACE_STRING_LOCAL_OWNER",
                      [x.action for x in combined.events])

    def test_nested_scope_cleanup_reverse_declaration_order(self):
        src = main('if true {let a:String="a";let b:String="b";println(a+b)}')
        result, _ = self.report(src)
        created = [x.slot for x in result.events if x.action == "BIND_STRING_LOCAL"]
        released = [x.slot for x in result.events
                    if x.action == "RELEASE_STRING_AT_SCOPE_EXIT"]
        self.assertEqual(released, list(reversed(created)))

    def test_early_return_marks_escaping_local(self):
        src = ('fn choose(flag:Bool)->String{let s:String="ok";'
               'if flag{return s};return s}\n' + main('println(choose(true))'))
        result, _ = self.report(src)
        releases = [x for x in result.events if x.action == "RELEASE_STRING_AT_RETURN"
                    and x.function == "choose"]
        self.assertEqual(len(releases), 2)
        self.assertEqual(len({x.slot for x in releases}), 1)

    def test_loop_reports_multiple_reaching_stores(self):
        src = main('var s:String="x";var i:Int=0;while i<3{s=s+"y";i=i+1};println(s)')
        result, _ = self.report(src)
        joins = [x for x in result.events if x.action == "JOIN_STRING_REACHING_STORES"]
        self.assertTrue(joins)
        self.assertTrue(any("declare@" in x.detail and "assign@" in x.detail
                            for x in joins))

    def test_branch_merge_collects_both_assignments(self):
        src = main('var s:String="init";if true{s="left"}else{s="right"};println(s)')
        result, _ = self.report(src)
        reads = [x for x in result.events if x.action == "READ_STRING_LOCAL_STORE"]
        self.assertTrue(any(x.detail.count("assign@") == 2 for x in reads))

    def test_unchanged_binding_join_not_reported_as_changed(self):
        src = main('let s:String="ok";if true{println(1)}else{println(2)};println(s)')
        result, _ = self.report(src)
        self.assertEqual([x for x in result.events
                          if x.action == "JOIN_STRING_REACHING_STORES"], [])

    def test_inferred_string_bindings(self):
        src = main('let s="🌍";println(s)')
        result, _ = self.report(src)
        self.assertIn("BIND_STRING_LOCAL", [x.action for x in result.events])

    def test_parameters_stay_separate_from_local_releases(self):
        src = ('fn echo(s:String)->String{return s}\n'
               + main('println(echo("hello"))'))
        result, _ = self.report(src)
        self.assertFalse(any(e.function == "echo" and e.action.startswith("RELEASE")
                             for e in result.events))

    def test_no_string_program_generates_no_local_events(self):
        result, _ = self.report(main('var i:Int=1;i=i+1;println(i)'))
        self.assertEqual(result.events, ())

    def test_nested_scopes_same_name_do_not_alias(self):
        src = main(
            'var s:String="outer";if true{var s:String="inner";s="new";println(s)};'
            'println(s)'
        )
        result, _ = self.report(src)
        changed = next(x for x in result.events if x.action == "REPLACE_STRING_LOCAL_OWNER")
        declaration_slots = [e.slot for e in result.events if e.action == "BIND_STRING_LOCAL"]
        self.assertEqual(changed.slot, declaration_slots[1])
        self.assertNotEqual(changed.slot, declaration_slots[0])

    def test_combined_report_integrity_checks_local_events(self):
        src = main('var s:String="x";s="y";println(s)')
        graph = compile_value_ir(parse_program(src))
        original = analyze_ownership_ir(graph)
        local = next(x for x in original.events if x.action == "REPLACE_STRING_LOCAL_OWNER")
        changed = replace(original, events=tuple(
            x for x in original.events if x is not local
        ))
        with self.assertRaises(BytecodeValidationError):
            verify_ownership_ir(graph, changed)


if __name__ == "__main__":
    unittest.main()
