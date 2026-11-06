"""Cross-platform IR->C11 smoke using the installed Samhus experimental CLI."""
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    sample = "examples/native_value_ir.sahu"
    expected = "14\nfalse\ntrue\n"
    vm = subprocess.run(
        [sys.executable, "-m", "samhus", "run", sample, "--backend", "vm", "--typecheck"],
        text=True, capture_output=True, encoding="utf-8",
    )
    if vm.returncode:
        raise RuntimeError(f"VM smoke failed: {vm.stderr}")
    if vm.stdout != expected:
        raise AssertionError(f"VM output {vm.stdout!r} != {expected!r}")
    with tempfile.TemporaryDirectory(prefix="samhus-native-ir-") as directory:
        exe = Path(directory) / ("demo.exe" if sys.platform == "win32" else "demo")
        compiled = subprocess.run(
            [sys.executable, "-m", "samhus", "native-ir", sample, "-o", str(exe)],
            text=True, capture_output=True, encoding="utf-8",
        )
        if compiled.returncode:
            raise RuntimeError(f"IR-native compilation failed: {compiled.stderr}")
        launched = subprocess.run(
            [str(exe)], text=True, capture_output=True, encoding="utf-8",
        )
        if (launched.returncode, launched.stdout) != (0, expected):
            raise AssertionError(
                f"Native result {(launched.returncode, launched.stdout, launched.stderr)!r}"
            )
        print("Native Value IR smoke PASS: standalone C11 binary, output matches VM")


if __name__ == "__main__":
    main()
