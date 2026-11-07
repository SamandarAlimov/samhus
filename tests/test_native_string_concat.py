"""Native String concat regression and VM differential suite."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from samhus import SamhusError, parse_program, run_to_string
from samhus.native_value_ir import emit_value_ir_c


CC = next((name for name in ("cc", "gcc", "clang") if shutil.which(name)), None)


def main(body):
    return "fn main() -> Unit {\n" + body + "\n}"


class NativeStringConcatTests(unittest.TestCase):
    def native(self, source, expected=None, error=None):
        if CC is None:
            self.skipTest("C11 compiler not available")
        generated = emit_value_ir_c(parse_program(source))
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            source_file = folder / "program.c"
            binary = folder / ("program.exe" if sys.platform == "win32" else "program")
            source_file.write_text(generated, encoding="utf-8")
            compiled = subprocess.run(
                [CC, "-std=c11", "-O2", str(source_file), "-o", str(binary)],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr + "\n" + generated[-5000:])
            result = subprocess.run([str(binary)], capture_output=True, timeout=15)
            stdout = result.stdout.decode("utf-8").replace("\r\n", "\n")
            stderr = result.stderr.decode("utf-8", errors="replace")
            if error:
                self.assertEqual(result.returncode, 2, stderr)
                self.assertIn(error, stderr)
            else:
                self.assertEqual(result.returncode, 0, stderr)
                self.assertEqual(stdout, expected)
                self.assertEqual(stdout, run_to_string(source))
        return generated

    def test_basic(self):
        self.native(main('println("Sam"+"hus")'), "Samhus\n")

    def test_unicode_index_length(self):
        self.native(main('let x="O‘z"+"bek 🌍🚀";println(x);println(len(x));'
                         'println(x[8])'), "O‘zbek 🌍🚀\n9\n🚀\n")

    def test_empty_operands(self):
        self.native(main('println(""+"abc");println("abc"+"");println(""+"")'),
                    "abc\nabc\n\n")

    def test_nested_concat(self):
        self.native(main('println(("S"+"am")+("hu"+"s"))'), "Samhus\n")

    def test_return_and_reused_views(self):
        code = ('fn join(a:String,b:String)->String{return a+b}\n'
                + main('let x=join("🌍","🚀");println(x);println(x[1]);'
                       'println(join(x,"!"))'))
        self.native(code, "🌍🚀\n🚀\n🌍🚀!\n")

    def test_loop_immutable_snapshots(self):
        self.native(main('var x:String="a";let old:String=x;'
                         'var i:Int=0;while i<4{x=x+"b";i=i+1};'
                         'println(old);println(x)'), "a\nabbbb\n")

    def test_index_then_concat(self):
        self.native(main('let x="🙂🚀"[1];println(x+"!");'
                         'println(len(x+"🌍"))'), "🚀!\n2\n")

    def test_untrusted_format_bytes(self):
        self.native(main('println("%s%n"+" %d")'), "%s%n %d\n")

    def test_repeated_large_result_reuses_existing_storage(self):
        # 600 * 20_000 would exhaust the 8 MiB arena without content reuse.
        left, right = "A" * 10000, "B" * 10000
        source = (
            'fn join()->String{return "' + left + '"+"' + right + '"}\n'
            + main('let saved:String=join();var i:Int=0;'
                   'while i<600{let other:String=join();'
                   'assert(other==saved);i=i+1};'
                   'println(len(saved));println(saved[10000])')
        )
        generated = self.native(source, "20000\nB\n")
        self.assertIn("sh_string_intern", generated)
        self.assertIn("sh_hash_concat", generated)

    def test_canonical_bytes_from_different_operand_splits(self):
        # Same resulting bytes, different splits, including Unicode.
        self.native(main('let a="🌍"+"🚀!";'
                         'let b="🌍🚀"+"!";'
                         'println(a==b);println(a[1]);println(b[2])'),
                    "true\n🚀\n!\n")

    def test_collision_does_not_change_contents_or_prior_views(self):
        # Search two different pairs that map to the same direct-mapped
        # bucket. The full byte comparison prevents hash-cache aliasing.
        def slot(text):
            value = 14695981039346656037
            for byte in text.encode("utf-8"):
                value = ((value ^ byte) * 1099511628211) & ((1 << 64) - 1)
            return value % 4096

        seen = {}
        first = second = None
        for i in range(10000):
            candidate = f"aa{i:04d}bb"
            key = slot(candidate)
            if key in seen and seen[key] != candidate:
                first, second = seen[key], candidate
                break
            seen[key] = candidate
        self.assertIsNotNone(first)
        source = main(
            f'let a="{first[:6]}"+"{first[6:]}";'
            f'let b="{second[:6]}"+"{second[6:]}";'
            f'let c="{first[:6]}"+"{first[6:]}";'
            'println(a);println(b);println(c);'
            'println(a==b);println(a==c)'
        )
        self.native(source, first + "\n" + second + "\n" + first + "\nfalse\ntrue\n")

    def test_no_intern_cache_without_concat(self):
        code = emit_value_ir_c(parse_program(main('println("Samhus")')))
        self.assertNotIn("sh_string_intern", code)

    def test_checked_cumulative_memory_exhaustion(self):
        self.native(main('var x:String="a";var i:Int=0;'
                         'while i<25{x=x+x;i=i+1};println(x)'),
                    error="String arena budget exceeded")

    def test_mixed_type_rejected(self):
        with self.assertRaises(SamhusError):
            emit_value_ir_c(parse_program(main('println("x"+5)')))


if __name__ == "__main__":
    unittest.main()
