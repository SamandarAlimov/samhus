"""Strict Ubuntu Clang ASan/UBSan for the isolated C11 owned String runtime.

Sanitizers are not a full proof of memory safety or a compiler integration.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CLANG = shutil.which("clang")


def main():
    if CLANG is None:
        raise SystemExit("clang is required for owned String ASan/UBSan validation")
    body = (ROOT / "tests" / "fixtures" /
            "owned_string_stress_body.inc").read_text(encoding="utf-8")
    code = ('#include "owned_string.h"\n'
            '#include <stdio.h>\n#include <stdlib.h>\n'
            'int main(void) {\n' + body + '\nreturn 0;\n}\n')
    with tempfile.TemporaryDirectory(prefix="samhus-owned-sanitizer-") as d:
        folder = Path(d)
        source = folder / "owned_stress.c"
        executable = folder / "owned_stress"
        source.write_text(code, encoding="utf-8")
        command = [
            CLANG, "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-Wpedantic", "-O1", "-g", "-fno-omit-frame-pointer",
            "-fsanitize=address,undefined", "-I", str(ROOT / "runtime"),
            str(ROOT / "runtime" / "owned_string.c"),
            str(source), "-o", str(executable),
        ]
        compiled = subprocess.run(command, capture_output=True, text=True,
                                  check=False, timeout=60)
        if compiled.returncode:
            raise SystemExit("ASan/UBSan compilation failed:\n" + compiled.stderr)
        env = os.environ.copy()
        env["ASAN_OPTIONS"] = "detect_leaks=1:halt_on_error=1"
        env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
        result = subprocess.run([str(executable)], env=env, capture_output=True,
                                text=True, check=False, timeout=60)
        if result.returncode or result.stdout != "0 0\n" or result.stderr:
            raise SystemExit(
                f"ASan/UBSan stress failed ({result.returncode})\n"
                f"stdout={result.stdout!r}\nstderr={result.stderr}"
            )
        print("Owned String C11: 50,000 operations, 0 live bytes/objects; "
              "Clang ASan/UBSan passed")


if __name__ == "__main__":
    main()
