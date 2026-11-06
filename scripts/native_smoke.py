"""End-to-end C backend smoke: Samhus -> C11 -> standalone executable."""
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="samhus-native-smoke-") as directory:
        path = Path(directory) / ("demo.exe" if sys.platform == "win32" else "demo")
        compile_result = subprocess.run(
            [sys.executable, "-m", "samhus", "native", "examples/native.sahu", "-o", str(path)],
            capture_output=True,
        )
        if compile_result.returncode:
            raise RuntimeError(compile_result.stderr.decode("utf-8", errors="replace"))
        result = subprocess.run([str(path)], capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
        expected = ["Samhus", "55", "0", "1", "2"]
        actual = result.stdout.decode("utf-8").splitlines()
        if actual != expected:
            raise AssertionError(f"Native smoke mismatch {actual!r} != {expected!r}")
        print("Native smoke PASS: produced and executed Python-independent binary")


if __name__ == "__main__":
    main()
