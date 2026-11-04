"""Additional command-line regression tests."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class SamhusCliTests(unittest.TestCase):
    def cli(self, source: str, *args: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.sahu"
            path.write_text(source, encoding="utf-8")
            return subprocess.run(
                [sys.executable, "-m", "samhus", *args, str(path)],
                capture_output=True, text=True,
            )

    def test_flag_rejects_infinite_while(self):
        source = "fn main() { while true {} }"
        result = self.cli(source, "run", "--max-steps", "20")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Execution step limit exceeded", result.stderr)

    def test_positive_budget_only(self):
        result = self.cli("fn main() {}", "run", "--max-steps", "0")
        self.assertEqual(result.returncode, 2)
        self.assertIn("positive integer", result.stderr)

    def test_check_still_parses_functions(self):
        source = "fn add(a,b) { return a + b }\nfn main() { println(add(1,2)) }"
        result = self.cli(source, "check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Syntax OK:", result.stdout)

    def test_run_function_example(self):
        source = "fn double(x) { return x * 2 }\nfn main() { println(double(21)) }"
        result = self.cli(source, "run", "--max-steps", "100")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "42\n")


if __name__ == "__main__":
    unittest.main()
