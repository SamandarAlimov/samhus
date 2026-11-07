"""Cross-platform native String literal subset tests (no heap ownership)."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from samhus import SamhusError, parse_program, run_to_string
from samhus.native_value_ir import MAX_NATIVE_LITERAL_BYTES, emit_value_ir_c, _static_utf8_literal
from samhus.lexer import Token
from samhus.bytecode import Instruction

CC = next((name for name in ("cc", "gcc", "clang") if shutil.which(name)), None)


def main(code):
    return "fn main() -> Unit {\n" + code + "\n}"


class NativeStringsTests(unittest.TestCase):
    def emit(self, code):
        return emit_value_ir_c(parse_program(code))

    def native(self, source, expected=None):
        if CC is None:
            self.skipTest("No C11 compiler available")
        c = self.emit(source)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            file = folder / "program.c"
            executable = folder / ("program.exe" if sys.platform == "win32" else "program")
            file.write_text(c, encoding="utf-8")
            compile_result = subprocess.run(
                [CC, "-std=c11", "-O2", str(file), "-o", str(executable)],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(compile_result.returncode, 0,
                             compile_result.stderr + "\n" + c[-7000:])
            result = subprocess.run(
                [str(executable)], capture_output=True, timeout=10,
            )
            output = result.stdout.decode("utf-8").replace("\r\n", "\n")
            errors = result.stderr.decode("utf-8", errors="replace")
            if expected is not None:
                self.assertEqual((result.returncode, output), (0, expected), errors)
                self.assertEqual(output, run_to_string(source))
            return result.returncode, output, errors

    def test_simple_literal(self):
        self.native(main('println("Samhus")'), "Samhus\n")

    def test_empty_literal(self):
        self.native(main('println("")'), "\n")

    def test_quote_and_backslash(self):
        self.native(main(r'println("quote: \" and backslash: \\")'),
                    'quote: " and backslash: \\\n')

    def test_percent_format_safety(self):
        self.native(main('println("%s %d %n")'), "%s %d %n\n")

    def test_newline_escape(self):
        self.native(main(r'println("one\ntwo")'), "one\ntwo\n")

    def test_tab_escape(self):
        self.native(main(r'println("a\tb")'), "a\tb\n")

    def test_uzbek_utf8(self):
        self.native(main('println("O‘zbekiston — Samhus")'),
                    "O‘zbekiston — Samhus\n")

    def test_arabic_utf8(self):
        self.native(main('println("بسم الله الرحمن الرحيم")'),
                    "بسم الله الرحمن الرحيم\n")

    def test_emoji_utf8(self):
        self.native(main('println("🌍🚀")'), "🌍🚀\n")

    def test_unicode_equal(self):
        self.native(main('println("o‘zbek" == "o‘zbek")'), "true\n")

    def test_unicode_not_equal(self):
        self.native(main('println("olma" != "anor")'), "true\n")

    def test_same_length_distinct_string(self):
        self.native(main('println("abc" == "abd")'), "false\n")

    def test_empty_equality(self):
        self.native(main('println("" == "")'), "true\n")

    def test_string_variable_inferred(self):
        self.native(main('let name = "Samhus"; println(name)'), "Samhus\n")

    def test_string_variable_annotated(self):
        self.native(main('let name: String = "Samhus"; println(name)'), "Samhus\n")

    def test_string_mutable_assignment(self):
        self.native(main('var word: String = "old"; word = "new"; println(word)'),
                    "new\n")

    def test_string_shadowing(self):
        self.native(main('let x:String="outer";if true {let x:String="inner";'
                         'println(x)};println(x)'), "inner\nouter\n")

    def test_string_parameter(self):
        self.native('fn greet(name:String)->Unit{println(name)}\n'
                    'fn main()->Unit{greet("Samhus")}','Samhus\n')

    def test_string_return(self):
        self.native('fn greeting()->String{return "Assalomu alaykum"}\n'
                    'fn main()->Unit{println(greeting())}', 'Assalomu alaykum\n')

    def test_string_forward_call(self):
        self.native('fn main()->Unit{println(greeting())}\n'
                    'fn greeting()->String{return "Salom"}', 'Salom\n')

    def test_string_conditional_return(self):
        self.native('fn choice(ok:Bool)->String{if ok {return "ha"};return "yo‘q"}\n'
                    'fn main()->Unit{println(choice(true));println(choice(false))}',
                    'ha\nyo‘q\n')

    def test_string_recursive_return(self):
        self.native('fn countdown(n:Int)->String{if n==0{return "tugadi"};'
                    'return countdown(n-1)}\n'
                    'fn main()->Unit{println(countdown(4))}', 'tugadi\n')

    def test_string_two_argument_call(self):
        self.native('fn equals(a:String,b:String)->Bool{return a==b}\n'
                    'fn main()->Unit{println(equals("abc","abc"));'
                    'println(equals("abc","ab"))}', 'true\nfalse\n')

    def test_string_len_ascii(self):
        self.native(main('println(len("Samhus"))'), '6\n')

    def test_string_len_utf8(self):
        self.native(main('println(len("O‘zbekiston"))'), '11\n')

    def test_string_len_arabic(self):
        self.native(main('println(len("سلام"))'), '4\n')

    def test_string_len_emoji(self):
        self.native(main('println(len("🌍🚀"))'), '2\n')

    def test_string_len_empty(self):
        self.native(main('println(len(""))'), '0\n')

    def test_string_len_parameter(self):
        self.native('fn length(text:String)->Int{return len(text)}\n'
                    'fn main()->Unit{println(length("🌍a"))}', '2\n')

    def test_string_len_variable(self):
        self.native(main('var x:String="ab";x="a🌍";println(len(x))'), '2\n')

    def test_generated_mixed_literals_single_binary(self):
        words = ["Samhus", "", "🙂", "أهلا", "Oʻzbek", '"', "\\", "%n", "a\nb"]
        # Render as parser-compatible escaped JSON string literals.
        import json
        body = ";".join("println(" + json.dumps(word, ensure_ascii=False) + ")"
                        for word in words)
        self.native(main(body), "".join(word + "\n" for word in words))

    def test_no_nul_string(self):
        token = Token("STRING", "", 1, 1)
        with self.assertRaisesRegex(SamhusError, "NUL byte"):
            _static_utf8_literal("hi" + chr(0) + "bye", Instruction("PUSH", "", token))

    def test_native_literal_byte_limit(self):
        oversized = "A" * (MAX_NATIVE_LITERAL_BYTES + 1)
        with self.assertRaisesRegex(SamhusError, "exceeds"):
            self.emit(main("println(" + '"' + oversized + '"' + ")"))

    def test_no_heap_concat(self):
        self.native(main('println("Sam" + "hus")'), "Samhus\n")
        code = self.emit(main('println("Sam" + "hus")'))
        self.assertIn("sh_string_arena", code)
        self.assertIn("sh_concat(", code)
        self.assertNotIn("malloc(", code)
        self.assertNotIn("free(", code)

    def test_concat_arena_is_opt_in(self):
        code = self.emit(main('println("hello")'))
        self.assertNotIn("sh_string_arena", code)
        self.assertNotIn("sh_concat(", code)

    def test_codepoint_string_index(self):
        self.native(main('println("abc"[0]);println("abc"[2])'),"a\nc\n")

    def test_no_dynamic_string_conversion(self):
        with self.assertRaisesRegex(SamhusError, "unsupported call"):
            self.emit(main('println(str(42))'))

    def test_reject_numeric_string_mixed_assignment(self):
        with self.assertRaises(SamhusError):
            self.emit(main('var name: String = "text"; name = 4'))

    def test_result_c_uses_utf8_octals(self):
        code = self.emit(main('println("🌍")'))
        self.assertIn(r"\360\237\214\215", code)
        self.assertIn("const unsigned char *", code)

    def test_string_narrowed_to_static_storage(self):
        code = self.emit('fn echo(x:String)->String{return x}\n'
                         'fn main()->Unit{println(echo("text"))}')
        self.assertIn("sh_string sh_arg_0", code)
        self.assertNotIn("malloc(", code)
        self.assertNotIn("free(", code)


if __name__ == "__main__":
    unittest.main()
