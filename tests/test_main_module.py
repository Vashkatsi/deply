import subprocess
import sys
import unittest
from pathlib import Path

from deply import __version__

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class TestMainModule(unittest.TestCase):
    def run_module(self, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "deply", *arguments],
            cwd=REPOSITORY_ROOT, capture_output=True, text=True, check=False,
        )

    def test_version_runs_through_module_entry_point(self):
        result = self.run_module("--version")

        self.assertEqual(result.returncode, 0)
        self.assertIn(__version__, result.stdout)

    def test_validate_exit_code_reflects_invalid_configuration(self):
        result = self.run_module("validate", "--config", str(REPOSITORY_ROOT / "deply.yaml.example"))

        self.assertEqual(result.returncode, 1)
        self.assertIn("Invalid deply configuration", result.stderr)


if __name__ == "__main__":
    unittest.main()
