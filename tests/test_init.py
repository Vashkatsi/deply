import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import yaml

from deply.config_validator import ConfigValidator
from deply.main import main
from deply.presets import PRESETS_DIRECTORY, available_presets, preset_text

EXPECTED_PRESETS = ["django", "fastapi", "flask", "layered"]


def run_cli(*arguments):
    with patch.object(sys, "argv", ["deply", *arguments]), patch("sys.stdout", new=StringIO()) as output_stream, \
            patch("sys.stderr", new=StringIO()) as error_stream:
        with unittest.TestCase().assertRaises(SystemExit) as exit_context:
            main()
    return exit_context.exception.code, output_stream.getvalue(), error_stream.getvalue()


class TestPresets(unittest.TestCase):
    def test_packaged_presets_are_valid_configurations(self):
        self.assertEqual(available_presets(), EXPECTED_PRESETS)
        for name in available_presets():
            with self.subTest(preset=name):
                preset_path = PRESETS_DIRECTORY / f"{name}.yaml"
                config = yaml.safe_load(preset_path.read_text())
                self.assertEqual(list(config), ["deply"])
                self.assertEqual(config["deply"]["paths"], ["."])
                self.assertEqual(ConfigValidator(preset_path).validate(config["deply"]), [])


class TestInitCommand(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        previous_directory = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, previous_directory)

    def test_init_writes_config_that_validate_accepts(self):
        exit_code, output, _ = run_cli("init", "--preset", "fastapi")
        self.assertEqual(exit_code, 0)
        self.assertIn("deply.yaml", output)
        written = yaml.safe_load((self.root / "deply.yaml").read_text())
        self.assertEqual(written["deply"]["paths"], ["."])
        self.assertIn(r"(^|/)\.venv/", written["deply"]["exclude_files"])
        self.assertEqual([layer["name"] for layer in written["deply"]["layers"]],
                         ["domain", "application", "infrastructure", "interface"])
        self.assertEqual(run_cli("validate")[0], 0)

    def test_every_preset_is_written_verbatim(self):
        for name in available_presets():
            with self.subTest(preset=name):
                output_path = self.root / f"{name}.yaml"
                self.assertEqual(run_cli("init", "--preset", name, "--output", str(output_path))[0], 0)
                self.assertEqual(output_path.read_text(), preset_text(name))

    def test_init_preset_excludes_root_level_virtualenv_tests_and_migrations(self):
        (self.root / "src" / "app" / "domain").mkdir(parents=True)
        (self.root / "src" / "app" / "domain" / "entity.py").write_text("class Entity: pass\n")
        for excluded_directory in (".venv", "tests", "migrations"):
            (self.root / excluded_directory).mkdir()
            (self.root / excluded_directory / "broken.py").write_text("class Broken:\n")
        self.assertEqual(run_cli("init", "--preset", "fastapi")[0], 0)
        exit_code, output, _ = run_cli("analyze", "--report-format", "json")
        self.assertEqual(exit_code, 0)
        metrics = json.loads(output)["metrics"]
        self.assertEqual(metrics["files_excluded"], 3)
        self.assertEqual(metrics["files_mapped"], 1)

    def test_init_rejects_invalid_preset_content_without_writing(self):
        invalid_preset = "deply:\n  paths: ['.']\n  layers: []\n  ruleset: {}\n"
        with patch("deply.main.preset_text", return_value=invalid_preset):
            exit_code, _, error = run_cli("init", "--preset", "fastapi")
        self.assertEqual(exit_code, 1)
        self.assertIn("Invalid deply configuration:", error)
        self.assertIn("layers: must contain at least one layer", error)
        self.assertFalse((self.root / "deply.yaml").exists())

    def test_init_refuses_to_overwrite_without_force(self):
        existing = self.root / "deply.yaml"
        existing.write_text("deply: {}\n")
        exit_code, _, error = run_cli("init", "--preset", "layered")
        self.assertEqual(exit_code, 1)
        self.assertIn("already exists", error)
        self.assertIn("--force", error)
        self.assertEqual(existing.read_text(), "deply: {}\n")

    def test_init_force_overwrites_existing_file(self):
        (self.root / "deply.yaml").write_text("deply: {}\n")
        exit_code, _, _ = run_cli("init", "--preset", "layered", "--force")
        self.assertEqual(exit_code, 0)
        written = yaml.safe_load((self.root / "deply.yaml").read_text())
        self.assertEqual(written["deply"]["layers"][0]["name"], "presentation")

    def test_init_honours_output(self):
        output_path = self.root / "config" / "architecture.yaml"
        output_path.parent.mkdir()
        exit_code, _, _ = run_cli("init", "--preset", "django", "--output", str(output_path))
        self.assertEqual(exit_code, 0)
        self.assertEqual(run_cli("validate", "--config", str(output_path))[0], 0)

    def test_init_fails_when_output_directory_is_missing(self):
        exit_code, _, error = run_cli("init", "--preset", "flask", "--output", "missing/deply.yaml")
        self.assertEqual(exit_code, 1)
        self.assertIn(str(Path("missing") / "deply.yaml"), error)

    def test_list_presets_prints_names_without_writing(self):
        exit_code, output, _ = run_cli("init", "--list-presets")
        self.assertEqual(exit_code, 0)
        self.assertEqual(output.split(), EXPECTED_PRESETS)
        self.assertFalse((self.root / "deply.yaml").exists())

    def test_init_rejects_unknown_preset_and_missing_selection(self):
        exit_code, _, error = run_cli("init", "--preset", "unknown")
        self.assertEqual(exit_code, 2)
        self.assertIn("invalid choice: 'unknown'", error)
        exit_code, _, error = run_cli("init")
        self.assertEqual(exit_code, 2)
        self.assertIn("one of the arguments --preset --list-presets is required", error)
        self.assertFalse((self.root / "deply.yaml").exists())
