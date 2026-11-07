"""Cross-platform IR -> C11 end-to-end tests on both standalone samples."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    samples = [
        ("examples/native_value_ir.sahu", "14\nfalse\ntrue\n"),
        ("examples/native_value_ir_locals.sahu", "45\ntrue\n"),
        ("examples/native_value_ir_functions.sahu", "720\n55\n"),
        ("examples/native_value_ir_strings.sahu", "Assalomu alaykum, Samhus!\nToshkent\n11\ntrue\n🌍🚀\n"),
    ]
    vm_env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    for sample, expected in samples:
        vm = subprocess.run(
            [sys.executable, "-m", "samhus", "run", sample, "--backend", "vm", "--typecheck"],
            text=True, capture_output=True, encoding="utf-8", env=vm_env,
        )
        if vm.returncode:
            raise RuntimeError(f"VM failed for {sample}: {vm.stderr}")
        if vm.stdout != expected:
            raise AssertionError(f"VM result {vm.stdout!r} != {expected!r}")
        with tempfile.TemporaryDirectory(prefix="samhus-native-ir-") as directory:
            exe = Path(directory) / ("demo.exe" if sys.platform == "win32" else "demo")
            compiled = subprocess.run(
                [sys.executable, "-m", "samhus", "native-ir", sample, "-o", str(exe)],
                text=True, capture_output=True, encoding="utf-8",
            )
            if compiled.returncode:
                raise RuntimeError(f"IR-native compilation failed: {compiled.stderr}")
            executed = subprocess.run(
                [str(exe)], text=True, capture_output=True, encoding="utf-8",
            )
            if (executed.returncode, executed.stdout) != (0, expected):
                raise AssertionError(
                    f"Native {sample}: {(executed.returncode, executed.stdout, executed.stderr)!r}"
                )
    print("Native Value IR smoke PASS: C11 binaries, loops, functions and UTF-8 Strings match VM")


if __name__ == "__main__":
    main()
