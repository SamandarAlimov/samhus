"""Multi-file Samhus module integration, import security and backend parity."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from samhus import SamhusError, parse_program, run_to_string
from samhus.bytecode import compile_ast
from samhus.formatter import format_program
from samhus.modules import load_program
from samhus.native_c import emit_program_c
from samhus.runtime import Interpreter
from samhus.typecheck import TypeChecker
from samhus.vm import VirtualMachine
from io import StringIO


LIB = """fn sum(a: Int, b: Int) -> Int { return a+b }"""
ENTRY = """import "math.sahu"
fn main() -> Unit { println(sum(19,23)) }
"""


class ModulesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.entry = self.write("main.sahu", ENTRY)
        self.lib = self.write("math.sahu", LIB)

    def write(self, name: str, source: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return path

    def cli(self, command: str, *args: str, file: Path | None = None):
        return subprocess.run(
            [sys.executable, "-m", "samhus", command, str(file or self.entry), *args],
            text=True, capture_output=True, encoding="utf-8",
        )

    def test_multifile_ast(self):
        p = load_program(self.entry)
        self.assertEqual([f.name for f in p.functions], ["sum", "main"])
        self.assertEqual(p.imports, ())

    def test_reference_and_vm_parity(self):
        program = load_program(self.entry)
        TypeChecker(program).check()
        out = StringIO()
        Interpreter(out).run(program)
        self.assertEqual(out.getvalue(), "42\n")
        out = StringIO()
        VirtualMachine(out).run(compile_ast(program))
        self.assertEqual(out.getvalue(), "42\n")

    def test_cli_tree(self):
        r = self.cli("run", "--backend", "tree", "--typecheck")
        self.assertEqual((r.returncode, r.stdout), (0, "42\n"), r.stderr)

    def test_cli_vm(self):
        r = self.cli("run", "--backend", "vm", "--typecheck")
        self.assertEqual((r.returncode, r.stdout), (0, "42\n"), r.stderr)

    def test_cli_check(self):
        r = self.cli("check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Syntax OK", r.stdout)

    def test_cli_typecheck(self):
        r = self.cli("typecheck")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Type check OK", r.stdout)

    def test_cli_ast(self):
        r = self.cli("ast")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"name": "sum"', r.stdout)

    def test_cli_disasm(self):
        r = self.cli("disasm")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("fn sum", r.stdout)

    def test_cli_emit_c_multifile(self):
        r = self.cli("emit-c")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("sh_fn_sum", r.stdout)

    def test_direct_source_api_rejects_unresolved_import(self):
        with self.assertRaisesRegex(SamhusError, "Imports require file-based"):
            parse_program(ENTRY)
        with self.assertRaisesRegex(SamhusError, "Imports require file-based"):
            run_to_string(ENTRY)

    def test_library_does_not_require_main(self):
        self.assertEqual([f.name for f in load_program(self.entry).functions], ["sum", "main"])

    def test_nested_import(self):
        self.write("modules/extra.sahu", 'fn multiplier(x:Int)->Int{return x*2}')
        self.write("math.sahu", 'import "modules/extra.sahu"\nfn sum(a:Int,b:Int)->Int{return multiplier(a+b)}')
        r = self.cli("run", "--backend", "vm", "--typecheck")
        self.assertEqual((r.returncode, r.stdout), (0, "84\n"), r.stderr)

    def test_diamond_import_deduplicated(self):
        self.write("shared.sahu", "fn shared()->Int{return 7}")
        self.write("left.sahu", 'import "shared.sahu"\nfn left()->Int{return shared()}')
        self.write("right.sahu", 'import "shared.sahu"\nfn right()->Int{return shared()}')
        self.write("main.sahu", 'import "left.sahu"\nimport "right.sahu"\nfn main()->Unit{println(left()+right())}')
        p = load_program(self.entry)
        self.assertEqual([f.name for f in p.functions], ["shared", "left", "right", "main"])
        self.assertEqual(self.cli("run", "--backend", "vm").stdout, "14\n")

    def test_repeated_same_import_deduplicated(self):
        self.write("main.sahu", 'import "math.sahu"\nimport "math.sahu"\nfn main(){println(sum(1,2))}')
        self.assertEqual(self.cli("run").stdout, "3\n")

    def test_cycle_detected(self):
        self.write("math.sahu", 'import "main.sahu"\nfn sum(a:Int,b:Int)->Int{return a+b}')
        with self.assertRaisesRegex(SamhusError, "Cyclic module import"):
            load_program(self.entry)

    def test_self_cycle_detected(self):
        self.write("math.sahu", 'import "math.sahu"\nfn sum(a:Int,b:Int)->Int{return a+b}')
        with self.assertRaisesRegex(SamhusError, "Cyclic module import"):
            load_program(self.entry)

    def test_duplicate_export_detected(self):
        self.write("other.sahu", "fn sum(a: Int,b:Int)->Int{return 0}")
        self.write("main.sahu", 'import "math.sahu"\nimport "other.sahu"\nfn main(){}')
        with self.assertRaisesRegex(SamhusError, "Duplicate function 'sum'"):
            load_program(self.entry)

    def test_imported_main_rejected(self):
        self.write("math.sahu", "fn main() {}")
        with self.assertRaisesRegex(SamhusError, "must not define main"):
            load_program(self.entry)

    def test_missing_library_error(self):
        self.lib.unlink()
        with self.assertRaisesRegex(SamhusError, "Cannot read module"):
            load_program(self.entry)

    def test_missing_entry_main(self):
        self.write("main.sahu", 'import "math.sahu"\nfn other(){}')
        with self.assertRaisesRegex(SamhusError, "Missing entry point"):
            load_program(self.entry)

    def test_invalid_import_path_absolute(self):
        self.write("main.sahu", f'import "{self.lib.as_posix()}"\nfn main(){{}}')
        with self.assertRaisesRegex(SamhusError, "Invalid local module path"):
            load_program(self.entry)

    def test_invalid_import_path_remote(self):
        self.write("main.sahu", 'import "https://example.com/pkg.sahu"\nfn main(){}')
        with self.assertRaisesRegex(SamhusError, "Invalid local module path"):
            load_program(self.entry)

    def test_invalid_import_path_other_extension(self):
        self.write("main.sahu", 'import "lib.py"\nfn main(){}')
        with self.assertRaisesRegex(SamhusError, "Invalid local module path"):
            load_program(self.entry)

    def test_escape_to_parent_rejected(self):
        sub = self.root / "sub"
        sub.mkdir()
        entry = sub / "main.sahu"
        entry.write_text('import "../math.sahu"\nfn main(){}', encoding="utf-8")
        with self.assertRaisesRegex(SamhusError, "Import escapes project root"):
            load_program(entry)

    def test_symlink_escape_rejected(self):
        external = self.root.parent / (self.root.name + "-outside.sahu")
        external.write_text("fn external(){}", encoding="utf-8")
        self.addCleanup(lambda: external.unlink(missing_ok=True))
        link = self.root / "external.sahu"
        try:
            link.symlink_to(external)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable on this platform")
        self.write("main.sahu", 'import "external.sahu"\nfn main(){}')
        with self.assertRaisesRegex(SamhusError, "Import escapes project root"):
            load_program(self.entry)

    def test_library_parse_error_mentions_file(self):
        self.write("math.sahu", "fn broken( {}")
        with self.assertRaisesRegex(SamhusError, "In module 'math.sahu'"):
            load_program(self.entry)

    def test_import_depth_limit(self):
        self.write("math.sahu", 'import "next.sahu"\nfn sum(a:Int,b:Int)->Int{return a+b}')
        self.write("next.sahu", "fn last() {}")
        with patch("samhus.modules.MAX_IMPORT_DEPTH", 1):
            with self.assertRaisesRegex(SamhusError, "Import depth limit"):
                load_program(self.entry)

    def test_module_count_limit(self):
        with patch("samhus.modules.MAX_MODULES", 1):
            with self.assertRaisesRegex(SamhusError, "Module count limit"):
                load_program(self.entry)

    def test_total_source_limit(self):
        with patch("samhus.modules.MAX_COMBINED_SOURCE_CHARS", len(ENTRY) + 10):
            with self.assertRaisesRegex(SamhusError, "Total imported source"):
                load_program(self.entry)

    def test_imported_signature_typechecked(self):
        self.write("math.sahu", "fn sum(a: Int,b:Int)->Int{return a+b}")
        self.write("main.sahu", 'import "math.sahu"\nfn main(){println(sum("x",2))}')
        r = self.cli("typecheck")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Type mismatch", r.stderr)

    def test_formatter_preserves_import_syntax(self):
        formatted = format_program(ENTRY)
        self.assertIn('import "math.sahu"', formatted)
        self.assertEqual(format_program(formatted), formatted)

    def test_formatter_allows_library_without_main(self):
        self.assertIn("fn sum(", format_program(LIB))

    def test_cli_native_real_executable(self):
        compiler = next((c for c in ("cc", "gcc", "clang") if shutil.which(c)), None)
        if not compiler:
            self.skipTest("No C compiler in PATH")
        out = self.root / ("result.exe" if os.name == "nt" else "result")
        build = self.cli("native", "-o", str(out))
        self.assertEqual(build.returncode, 0, build.stderr)
        self.assertTrue(out.is_file())
        done = subprocess.run([str(out)], capture_output=True, encoding="utf-8")
        self.assertEqual((done.returncode, done.stdout), (0, "42\n"), done.stderr)


if __name__ == "__main__":
    unittest.main()
