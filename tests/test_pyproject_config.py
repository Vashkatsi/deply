import os
import sys
import tempfile
import textwrap
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import yaml

from deply.config_parser import ConfigParser, TOML_UNSUPPORTED_MESSAGE, discover_config_path
from deply.main import main

TOML_SUPPORTED = sys.version_info >= (3, 11)

DEPLY_CONFIG = {
    "paths": ["."],
    "exclude_files": [".*/tests/.*"],
    "layers": [
        {"name": "domain", "collectors": [{"type": "directory", "directories": ["src/domain"]}]},
        {"name": "infrastructure", "collectors": [{"type": "directory", "directories": ["src/infrastructure"]}]},
    ],
    "ruleset": {"domain": {"disallow_layer_dependencies": ["infrastructure"]}},
}

PYPROJECT_TEXT = textwrap.dedent("""
    [project]
    name = "sample"

    [tool.deply]
    paths = ["."]
    exclude_files = ['.*/tests/.*']

    [[tool.deply.layers]]
    name = "domain"

    [[tool.deply.layers.collectors]]
    type = "directory"
    directories = ["src/domain"]

    [[tool.deply.layers]]
    name = "infrastructure"

    [[tool.deply.layers.collectors]]
    type = "directory"
    directories = ["src/infrastructure"]

    [tool.deply.ruleset.domain]
    disallow_layer_dependencies = ["infrastructure"]
""")

NAMING_PYPROJECT_TEXT = textwrap.dedent("""
    [tool.deply]

    [[tool.deply.layers]]
    name = "app"

    [[tool.deply.layers.collectors]]
    type = "file_regex"
    regex = ".*"

    [tool.deply.ruleset.app]
    enforce_class_naming = [{ type = "class_name_regex", class_name_regex = "^Expected$" }]
""")

PYPROJECT_WITHOUT_DEPLY_TEXT = '[tool.ruff]\nline-length = 120\n'


class TestPyprojectConfig(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.project_path = Path(temporary_directory.name)
        self.pyproject_path = self.project_path / "pyproject.toml"
        self.yaml_path = self.project_path / "deply.yaml"

    def _change_directory(self, directory: Path) -> None:
        previous_directory = os.getcwd()
        self.addCleanup(os.chdir, previous_directory)
        os.chdir(directory)

    def _run_cli(self, arguments):
        with patch.object(sys, "argv", ["deply"] + arguments), patch("sys.stdout", new=StringIO()) as output_stream, \
                patch("sys.stderr", new=StringIO()) as error_stream:
            with self.assertRaises(SystemExit) as exit_context:
                main()
        return exit_context.exception.code, output_stream.getvalue(), error_stream.getvalue()

    def test_discovery_prefers_yaml_over_pyproject(self):
        self.yaml_path.write_text("deply: {}\n")
        self.pyproject_path.write_text(PYPROJECT_TEXT)

        self.assertEqual(discover_config_path(self.project_path), self.yaml_path)

    @unittest.skipUnless(TOML_SUPPORTED, "tomllib requires Python 3.11+")
    def test_discovery_uses_pyproject_with_deply_table(self):
        self.pyproject_path.write_text(PYPROJECT_TEXT)

        self.assertEqual(discover_config_path(self.project_path), self.pyproject_path)

    def test_discovery_falls_back_to_yaml_without_deply_table(self):
        for pyproject_text in [PYPROJECT_WITHOUT_DEPLY_TEXT, "tool = 1\n", "[tool\n"]:
            with self.subTest(pyproject_text=pyproject_text):
                self.pyproject_path.write_text(pyproject_text)
                self.assertEqual(discover_config_path(self.project_path), self.yaml_path)

    def test_discovery_falls_back_to_yaml_when_pyproject_is_unreadable(self):
        self.pyproject_path.mkdir()

        self.assertEqual(discover_config_path(self.project_path), self.yaml_path)

    def test_discovery_falls_back_to_yaml_without_any_config(self):
        self.assertEqual(discover_config_path(self.project_path), self.yaml_path)

    def test_discovery_ignores_pyproject_without_tomllib(self):
        self.pyproject_path.write_text(PYPROJECT_TEXT)

        with patch.dict(sys.modules, {"tomllib": None}):
            self.assertEqual(discover_config_path(self.project_path), self.yaml_path)

    def test_parse_rejects_pyproject_without_tomllib(self):
        self.pyproject_path.write_text(PYPROJECT_TEXT)

        with patch.dict(sys.modules, {"tomllib": None}):
            with self.assertRaises(ValueError) as context:
                ConfigParser(self.pyproject_path).parse()

        self.assertEqual(str(context.exception), TOML_UNSUPPORTED_MESSAGE)

    @unittest.skipUnless(TOML_SUPPORTED, "tomllib requires Python 3.11+")
    def test_parse_toml_matches_yaml(self):
        self.yaml_path.write_text(yaml.safe_dump({"deply": DEPLY_CONFIG}))
        self.pyproject_path.write_text(PYPROJECT_TEXT)

        self.assertEqual(ConfigParser(self.pyproject_path).parse(), ConfigParser(self.yaml_path).parse())
        self.assertEqual(ConfigParser(self.pyproject_path).parse(), DEPLY_CONFIG)

    @unittest.skipUnless(TOML_SUPPORTED, "tomllib requires Python 3.11+")
    def test_parse_defaults_paths_to_pyproject_directory(self):
        self.pyproject_path.write_text("[tool.deply]\n")

        self.assertEqual(ConfigParser(self.pyproject_path).parse()["paths"], [str(self.project_path)])

    @unittest.skipUnless(TOML_SUPPORTED, "tomllib requires Python 3.11+")
    def test_parse_rejects_pyproject_without_deply_table(self):
        for pyproject_text in [PYPROJECT_WITHOUT_DEPLY_TEXT, "tool = 1\n"]:
            with self.subTest(pyproject_text=pyproject_text):
                self.pyproject_path.write_text(pyproject_text)
                with self.assertRaises(ValueError) as context:
                    ConfigParser(self.pyproject_path).parse()
                self.assertIn("has no [tool.deply] table", str(context.exception))

    @unittest.skipUnless(TOML_SUPPORTED, "tomllib requires Python 3.11+")
    def test_parse_rejects_non_table_deply_value(self):
        self.pyproject_path.write_text("[tool]\ndeply = 1\n")

        with self.assertRaises(ValueError) as context:
            ConfigParser(self.pyproject_path).parse()

        self.assertEqual(str(context.exception), "Invalid deply configuration format")

    @unittest.skipUnless(TOML_SUPPORTED, "tomllib requires Python 3.11+")
    def test_analyze_without_flags_uses_pyproject(self):
        self.pyproject_path.write_text(NAMING_PYPROJECT_TEXT)
        (self.project_path / "app.py").write_text("class Actual: pass\n")
        self._change_directory(self.project_path)

        exit_code, output, _ = self._run_cli(["analyze"])

        self.assertEqual(exit_code, 1)
        self.assertIn("Actual", output)

    @unittest.skipUnless(TOML_SUPPORTED, "tomllib requires Python 3.11+")
    def test_analyze_with_explicit_pyproject_path(self):
        self.pyproject_path.write_text(NAMING_PYPROJECT_TEXT)
        (self.project_path / "app.py").write_text("class Expected: pass\n")

        exit_code, _, error_output = self._run_cli(["analyze", "--config", str(self.pyproject_path)])

        self.assertEqual(exit_code, 0, error_output)

    @unittest.skipUnless(TOML_SUPPORTED, "tomllib requires Python 3.11+")
    def test_validate_reports_missing_deply_table(self):
        self.pyproject_path.write_text(PYPROJECT_WITHOUT_DEPLY_TEXT)

        exit_code, _, error_output = self._run_cli(["validate", "--config", str(self.pyproject_path)])

        self.assertEqual(exit_code, 1)
        self.assertIn("has no [tool.deply] table", error_output)

    def test_analyze_without_any_config_reports_missing_yaml(self):
        self.pyproject_path.write_text(PYPROJECT_WITHOUT_DEPLY_TEXT)
        self._change_directory(self.project_path)

        exit_code, _, error_output = self._run_cli(["analyze"])

        self.assertEqual(exit_code, 1)
        self.assertIn("deply.yaml", error_output)


if __name__ == "__main__":
    unittest.main()
