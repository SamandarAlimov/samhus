"""Standalone refcounted C11 String runtime tests, not compiler integration."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
CC = next((tool for tool in ("cc", "gcc", "clang") if shutil.which(tool)), None)
RUNTIME = PROJECT / "runtime" / "owned_string.c"


class OwnedStringC11Tests(unittest.TestCase):
    def run_c(self, body, expected="", failure=None):
        if CC is None:
            self.skipTest("C11 compiler unavailable")
        source = ('#include "owned_string.h"\n#include <stdio.h>\n'
                  '#include <stdlib.h>\nint main(void) {\n' + body
                  + "\nreturn 0;\n}\n")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            c = root / "test.c"
            exe = root / ("test.exe" if sys.platform == "win32" else "test")
            c.write_text(source, encoding="utf-8")
            built = subprocess.run(
                [CC, "-std=c11", "-Wall", "-Wextra", "-Werror",
                 "-I", str(PROJECT / "runtime"), str(RUNTIME),
                 str(c), "-o", str(exe)],
                text=True, encoding="utf-8", capture_output=True, timeout=25,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            executed = subprocess.run([str(exe)], capture_output=True, timeout=12)
            stdout = executed.stdout.decode("utf-8").replace("\r\n", "\n")
            stderr = executed.stderr.decode("utf-8", errors="replace")
            if failure:
                self.assertEqual(executed.returncode, 2, stderr)
                self.assertIn(failure, stderr)
            else:
                self.assertEqual(executed.returncode, 0, stderr)
                self.assertEqual(stdout, expected)
            return stdout, stderr

    def test_concat_aliases_free_after_last_reference(self):
        self.run_c(r'''
const unsigned char a[] = "Assalomu ";
const unsigned char b[] = "Samhus!";
sh_owned left = sh_owned_new_utf8(a, sizeof(a)-1);
sh_owned right = sh_owned_new_utf8(b, sizeof(b)-1);
sh_owned result = sh_owned_concat(left, right);
sh_owned alias = sh_owned_retain(result);
sh_owned_drop(&left); sh_owned_drop(&right); sh_owned_drop(&result);
sh_owned_print(alias);
printf("%zu %zu\n", sh_owned_live_bytes(), sh_owned_live_objects());
sh_owned_drop(&alias);
printf("%zu %zu\n", sh_owned_live_bytes(), sh_owned_live_objects());
''', "Assalomu Samhus!\n16 1\n0 0\n")

    def test_unicode_index_retains_parent_allocation(self):
        self.run_c(r'''
const unsigned char original[] = "O‘zbek 🌍🚀";
sh_owned text = sh_owned_new_utf8(original, sizeof(original)-1);
sh_owned glyph = sh_owned_index_cp(text, 8);
sh_owned_drop(&text);
sh_owned_print(glyph);
printf("%zu %zu\n", sh_owned_len_cp(glyph), sh_owned_live_objects());
sh_owned_drop(&glyph);
printf("%zu\n", sh_owned_live_bytes());
''', "🚀\n1 1\n0\n")

    def test_nested_slices_retained_and_empty(self):
        self.run_c(r'''
const unsigned char original[] = "abc🌍🚀z";
sh_owned x = sh_owned_new_utf8(original, sizeof(original)-1);
sh_owned middle = sh_owned_slice_cp(x, 2, 5);
sh_owned rocket = sh_owned_slice_cp(middle, 2, 3);
sh_owned empty = sh_owned_slice_cp(middle, 0, 0);
sh_owned_drop(&x); sh_owned_drop(&middle);
sh_owned_print(rocket);
sh_owned_print(empty);
sh_owned_drop(&empty); sh_owned_drop(&rocket);
printf("%zu %zu\n", sh_owned_live_bytes(), sh_owned_live_objects());
''', "🚀\n\n0 0\n")

    def test_repeated_allocation_after_drop_reuses_live_budget(self):
        self.run_c(r'''
unsigned char *data = malloc(700000);
if (!data) return 1;
for (size_t i=0; i<700000; ++i) data[i] = 'a';
for (int i=0; i<32; ++i) {
    sh_owned x = sh_owned_new_utf8(data, 700000);
    if (sh_owned_live_bytes() != 700000) return 3;
    sh_owned_drop(&x);
    if (sh_owned_live_bytes() != 0) return 4;
}
free(data);
printf("%zu %zu\n", sh_owned_live_bytes(), sh_owned_live_objects());
''', "0 0\n")

    def test_concurrent_live_payload_is_bounded(self):
        self.run_c(r'''
unsigned char *data = malloc(700000);
if (!data) return 1;
for (size_t i=0; i<700000; ++i) data[i] = 'a';
sh_owned first = sh_owned_new_utf8(data, 700000);
sh_owned second = sh_owned_new_utf8(data, 700000);
sh_owned_drop(&first); sh_owned_drop(&second);
free(data);
''', failure="Live String byte budget exceeded")

    def test_slice_holds_owner_until_released(self):
        self.run_c(r'''
unsigned char *data = malloc(700000);
if (!data) return 1;
for (size_t i=0; i<700000; ++i) data[i] = 'a';
sh_owned parent = sh_owned_new_utf8(data, 700000);
sh_owned slice = sh_owned_index_cp(parent, 1);
sh_owned_drop(&parent);
sh_owned second = sh_owned_new_utf8(data, 700000);
sh_owned_drop(&slice); sh_owned_drop(&second);
free(data);
''', failure="Live String byte budget exceeded")

    def test_invalid_utf8_rejected(self):
        self.run_c(r'''
const unsigned char broken[] = {0xc0, 0xaf};
sh_owned x = sh_owned_new_utf8(broken, sizeof(broken));
sh_owned_drop(&x);
''', failure="Invalid UTF-8")

    def test_surrogate_utf8_rejected(self):
        self.run_c(r'''
const unsigned char broken[] = {0xed, 0xa0, 0x80};
sh_owned x = sh_owned_new_utf8(broken, sizeof(broken));
sh_owned_drop(&x);
''', failure="Invalid UTF-8")

    def test_slice_bounds_checked(self):
        self.run_c(r'''
const unsigned char data[] = "abc";
sh_owned x = sh_owned_new_utf8(data, 3);
sh_owned bad = sh_owned_slice_cp(x, 1, 4);
sh_owned_drop(&bad); sh_owned_drop(&x);
''', failure="String slice bounds")

    def test_empty_concat_retains_nonempty_input(self):
        self.run_c(r'''
const unsigned char data[] = "Samhus";
sh_owned empty = sh_owned_new_utf8(NULL, 0);
sh_owned val = sh_owned_new_utf8(data, sizeof(data)-1);
sh_owned copy = sh_owned_concat(empty, val);
sh_owned_drop(&val);
sh_owned_print(copy);
sh_owned_drop(&copy); sh_owned_drop(&empty);
printf("%zu %zu\n", sh_owned_live_bytes(), sh_owned_live_objects());
''', "Samhus\n0 0\n")

    def test_embedded_nul_rejected(self):
        self.run_c(r'''
const unsigned char bytes[] = {'a', 0, 'b'};
sh_owned x = sh_owned_new_utf8(bytes, sizeof(bytes));
sh_owned_drop(&x);
''', failure="NUL byte is unsupported")

    def test_value_ir_compiler_not_silently_switched_to_owned(self):
        from samhus import parse_program
        from samhus.native_value_ir import emit_value_ir_c
        generated = emit_value_ir_c(parse_program(
            'fn main()->Unit{println("a"+"b")}'
        ))
        self.assertNotIn("sh_owned_", generated)
        self.assertIn("sh_string_arena", generated)


if __name__ == "__main__":
    unittest.main()
