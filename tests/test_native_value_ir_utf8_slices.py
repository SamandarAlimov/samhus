"""Length-checked UTF-8 borrowed String slice tests for native Value IR."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import random

from samhus import SamhusError, parse_program, run_to_string
from samhus.native_value_ir import emit_value_ir_c

CC = next((name for name in ("cc","gcc","clang") if shutil.which(name)), None)


def main(body):
    return "fn main() -> Unit {\n" + body + "\n}"


class NativeUTF8SlicesTests(unittest.TestCase):
    def native(self, source, expected=None, fail=False):
        if not CC:
            self.skipTest("No C11 compiler")
        c = emit_value_ir_c(parse_program(source))
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            cfile = folder/"samhus.c"
            executable = folder/("prog.exe" if sys.platform=="win32" else "prog")
            cfile.write_text(c, encoding="utf-8")
            compiled = subprocess.run(
                [CC, "-std=c11", "-O2", str(cfile), "-o", str(executable)],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(compiled.returncode, 0,
                             compiled.stderr + "\n" + c[-7000:])
            result = subprocess.run([str(executable)],capture_output=True,timeout=10)
            stdout = result.stdout.decode("utf-8").replace("\r\n","\n")
            stderr = result.stderr.decode("utf-8",errors="replace")
            if fail:
                self.assertEqual(result.returncode, 2,stderr)
                self.assertIn("Index out of bounds",stderr)
            elif expected is not None:
                self.assertEqual((result.returncode,stdout),(0,expected),stderr)
                self.assertEqual(stdout,run_to_string(source))
            return result.returncode, stdout, stderr

    def test_ascii_first(self):
        self.native(main('println("Samhus"[0])'),"S\n")

    def test_ascii_last(self):
        self.native(main('println("Samhus"[5])'),"s\n")

    def test_emoji_first(self):
        self.native(main('println("🌍🚀"[0])'),"🌍\n")

    def test_emoji_last(self):
        self.native(main('println("🌍🚀"[1])'),"🚀\n")

    def test_arabic(self):
        self.native(main('println("سلام"[2])'),"ا\n")

    def test_uzbek(self):
        self.native(main('println("O‘zbekiston"[1])'),"‘\n")

    def test_combining_mark(self):
        self.native(main('println("e\u0301"[0]);println("e\u0301"[1])'),"e\n\u0301\n")

    def test_index_inferred_variable(self):
        self.native(main('let x="abc";println(x[1])'),"b\n")

    def test_index_typed_variable(self):
        self.native(main('let text:String="🌍🚀";println(text[1])'),"🚀\n")

    def test_index_mutable_variable(self):
        self.native(main('var text:String="abc";text="def";println(text[0])'),"d\n")

    def test_index_in_if(self):
        self.native(main('if true {println("AB"[1])} else {println("CD"[1])}'),"B\n")

    def test_index_in_loop(self):
        self.native(main('var i:Int=0;while i<3{println("ABC"[i]);i=i+1}'),
                    "A\nB\nC\n")

    def test_index_returned_from_function(self):
        code='fn cp(s:String,i:Int)->String{return s[i]}\n'+main('println(cp("🌍🚀",1))')
        self.native(code,"🚀\n")

    def test_nested_index_result(self):
        self.native(main('println("🌍🚀"[1][0])'),"🚀\n")

    def test_borrowed_return_outlives_callee(self):
        code='fn last(s:String)->String{return s[len(s)-1]}\n'+main(
            'let x=last("ABC");println(x);println(last("🙂🙃"))')
        self.native(code,"C\n🙃\n")

    def test_index_equality(self):
        self.native(main('println("🌍🚀"[0]=="🌍");println("abc"[1]!="a")'),
                    "true\ntrue\n")

    def test_index_length_one(self):
        self.native(main('println(len("🌍🚀"[1]));println(len("abc"[2]))'),
                    "1\n1\n")

    def test_index_output_non_ascii_bytes(self):
        self.native(main('println("بسم"[0]);println("🙂🚀"[1])'),"ب\n🚀\n")

    def test_index_negative(self):
        self.native(main('println("abc"[-1])'),fail=True)

    def test_index_at_length(self):
        self.native(main('println("abc"[3])'),fail=True)

    def test_index_empty(self):
        self.native(main('println(""[0])'),fail=True)

    def test_index_huge(self):
        self.native(main('println("abc"[9223372036854775807])'),fail=True)

    def test_shortcircuit_avoids_invalid_index(self):
        self.native(main('println(false && ("abc"[3]=="a"))'),"false\n")

    def test_compiled_layout_length_tracking(self):
        code=emit_value_ir_c(parse_program(main('println("abc"[1])')))
        self.assertIn("sh_utf8_index",code)
        self.assertIn("size_t size;",code)
        self.assertIn("sh_string_equal",code)
        self.assertNotIn("malloc(",code)
        self.assertNotIn("free(",code)

    def test_phi_slice(self):
        code=main('let x:String="abc";println((x[0]=="a") && (x[2]=="c"))')
        self.native(code,"true\n")

    def test_50_random_ascii_indices_single_binary(self):
        rng=random.Random(73120)
        alphabet="abcdefghijklmnopqrstuvwxyz"
        rows=[]
        expected=[]
        for _ in range(50):
            value="".join(rng.choice(alphabet) for _ in range(5))
            index=rng.randrange(len(value))
            rows.append(f'println("{value}"[{index}])')
            expected.append(value[index])
        self.native(main(";".join(rows)), "\n".join(expected)+"\n")

    def test_30_unicode_indices_single_binary(self):
        alphabet=["O","‘","z","б","🙂","🌍","🚀","é"]
        rows=[]
        expected=[]
        for i in range(30):
            text="".join(alphabet[(i+j)%len(alphabet)] for j in range(5))
            index=i%5
            rows.append(f'println("{text}"[{index}])')
            expected.append(text[index])
        self.native(main(";".join(rows)),"\n".join(expected)+"\n")

    def test_invalid_index_type_rejected(self):
        with self.assertRaises(SamhusError):
            emit_value_ir_c(parse_program(main('println("abc"[true])')))

    def test_invalid_collection_type_rejected(self):
        with self.assertRaises(SamhusError):
            emit_value_ir_c(parse_program(main('println(123[0])')))


if __name__ == "__main__":
    unittest.main()
