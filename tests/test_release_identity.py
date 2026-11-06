"""Release identity is consistent and historical prototype labels are not releases."""
import subprocess
import sys
import unittest
from importlib.metadata import version
from pathlib import Path
from samhus import __version__


class ReleaseIdentityTests(unittest.TestCase):
    def test_unreleased_identifier(self):
        self.assertEqual(__version__, "0.0.0.dev0")

    def test_package_metadata_version(self):
        # CI installs the package before CLI smoke; when tests run from source
        # compare pyproject.toml rather than assuming an installed distribution.
        import tomllib
        root = Path(__file__).resolve().parents[1]
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["project"]["version"], __version__)

    def test_cli_never_claims_release(self):
        command = subprocess.run([sys.executable, "-m", "samhus", "--version"],
                                 capture_output=True, text=True)
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertIn("0.0.0.dev0", command.stdout)
        self.assertIn("experimental", command.stdout)


if __name__ == "__main__":
    unittest.main()
