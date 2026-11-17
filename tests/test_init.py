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
from deply.presets import PRESETS_DIRECTORY, available_presets, render_preset

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

    def test_render_preset_replaces_only_paths(self):
        rendered = render_preset("fastapi", ["src"])
        original = yaml.safe_load((PRESETS_DIRECTORY / "fastapi.yaml").read_text())["deply"]
        self.assertEqual(rendered["deply"]["paths"], ["src"])
        self.assertEqual(rendered["deply"]["layers"], original["layers"])
        self.assertEqual(rendered["deply"]["ruleset"], original["ruleset"])
        self.assertEqual(list(rendered["deply"]), list(original))


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
        self.assertIn(r".*/\.venv/.*", written["deply"]["exclude_files"])
        self.assertEqual([layer["name"] for layer in written["deply"]["layers"]],
                         ["domain", "application", "infrastructure", "interface"])
        self.assertEqual(run_cli("validate")[0], 0)

    def test_every_preset_round_trips_through_init(self):
        for name in available_presets():
            with self.subTest(preset=name):
                output_path = self.root / f"{name}.yaml"
                self.assertEqual(run_cli("init", "--preset", name, "--output", str(output_path))[0], 0)
                self.assertEqual(yaml.safe_load(output_path.read_text()), render_preset(name, ["."]))

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

    def test_init_honours_output_and_paths(self):
        (self.root / "src").mkdir()
        output_path = self.root / "config" / "architecture.yaml"
        output_path.parent.mkdir()
        exit_code, _, _ = run_cli("init", "--preset", "django", "--output", str(output_path), "--paths", "src")
        self.assertEqual(exit_code, 0)
        written = yaml.safe_load(output_path.read_text())
        self.assertEqual(written["deply"]["paths"], ["src"])
        self.assertEqual(run_cli("validate", "--config", str(output_path))[0], 0)

    def test_init_rejects_missing_paths_without_writing(self):
        exit_code, _, error = run_cli("init", "--preset", "flask", "--paths", "missing")
        self.assertEqual(exit_code, 1)
        self.assertIn("paths[0]: path does not exist: missing", error)
        self.assertFalse((self.root / "deply.yaml").exists())

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
        self.assertEqual(run_cli("init", "--preset", "unknown")[0], 2)
        self.assertEqual(run_cli("init")[0], 2)
        self.assertFalse((self.root / "deply.yaml").exists())
