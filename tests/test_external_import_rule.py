import argparse
import codecs
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from deply.deply_runner import DeplyRunner, extract_absolute_imports
from deply.models.code_element import CodeElement
from deply.models.violation_types import ViolationType
from deply.rules.external_import_rule import ExternalImportRule


class TestExternalImportRule(unittest.TestCase):
    def setUp(self):
        self.element = CodeElement(
            file=Path("domain/service.py"),
            name="load_user",
            element_type="function",
            line=4,
            column=0,
        )

    def test_import_root_violation(self):
        rule = ExternalImportRule("domain", ["requests"])

        violation = rule.check_external_import("domain", self.element, "requests.sessions", 1, 0)

        self.assertIsNotNone(violation)
        self.assertEqual(violation.violation_type, ViolationType.DISALLOWED_EXTERNAL_IMPORT)
        self.assertEqual(violation.file, self.element.file)
        self.assertEqual(violation.element_name, "load_user")
        self.assertEqual(violation.element_type, "function")
        self.assertEqual(violation.line, 1)
        self.assertEqual(violation.column, 0)
        self.assertIn("external package 'requests'", violation.message)

    def test_unconfigured_import_passes(self):
        rule = ExternalImportRule("domain", ["django"])

        violation = rule.check_external_import("domain", self.element, "requests", 1, 0)

        self.assertIsNone(violation)

    def test_wrong_layer_passes(self):
        rule = ExternalImportRule("domain", ["requests"])

        violation = rule.check_external_import("infrastructure", self.element, "requests", 1, 0)

        self.assertIsNone(violation)

    def test_configured_nested_import_is_treated_as_root(self):
        rule = ExternalImportRule("domain", ["django.db"])

        violation = rule.check_external_import("domain", self.element, "django.forms", 1, 0)

        self.assertIsNotNone(violation)
        self.assertIn("external package 'django'", violation.message)

    def test_root_name_must_match_exactly(self):
        rule = ExternalImportRule("domain", ["request"])

        violation = rule.check_external_import("domain", self.element, "requests", 1, 0)

        self.assertIsNone(violation)


class TestExternalImportExtraction(unittest.TestCase):
    def test_extract_absolute_imports_handles_aliases_and_multiple_names(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            file_path = Path(temporary_directory) / "service.py"
            file_path.write_text(
                "import requests as http, django.db\n"
                "from sqlalchemy.orm import Session\n"
                "from ccxt.pro import binance\n"
                "from .entities import User\n"
                "from ..shared import Money\n"
            )

            imports = extract_absolute_imports(file_path)

        self.assertEqual(
            imports,
            [
                ("requests", 1, 0),
                ("django.db", 1, 0),
                ("sqlalchemy.orm", 2, 0),
                ("ccxt.pro", 3, 0),
            ],
        )

    def test_extract_absolute_imports_returns_empty_on_parse_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            file_path = Path(temporary_directory) / "invalid.py"
            file_path.write_text("def invalid(:\n")

            imports = extract_absolute_imports(file_path)

        self.assertEqual(imports, [])

    def test_extract_absolute_imports_reports_parse_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            file_path = Path(temporary_directory) / "invalid.py"
            file_path.write_text("def invalid(:\n")
            analysis_errors = []

            extract_absolute_imports(file_path, analysis_errors)

        self.assertEqual(len(analysis_errors), 1)
        self.assertIn(f"failed to analyze {file_path}:", analysis_errors[0])

    def test_extract_absolute_imports_accepts_python_source_encodings(self):
        source_files = {
            "pep263": "# coding: latin-1\nimport requests\nname = 'café'\n".encode("latin-1"),
            "utf8_bom": codecs.BOM_UTF8 + b"import requests\n",
        }
        for source_name, source_bytes in source_files.items():
            with self.subTest(source=source_name), tempfile.TemporaryDirectory() as temporary_directory:
                file_path = Path(temporary_directory) / "service.py"
                file_path.write_bytes(source_bytes)
                analysis_errors = []

                imports = extract_absolute_imports(file_path, analysis_errors)

            self.assertEqual(imports, [("requests", 2 if source_name == "pep263" else 1, 0)])
            self.assertEqual(analysis_errors, [])


class TestExternalImportRunner(unittest.TestCase):
    def test_runner_records_external_import_read_failure(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_file = Path(temporary_directory) / "missing.py"
            element = CodeElement(
                file=missing_file,
                name="load_user",
                element_type="function",
                line=1,
                column=0,
            )
            runner = DeplyRunner(
                argparse.Namespace(
                    config="deply.yaml",
                    parallel=None,
                    report_format="text",
                    output=None,
                    mermaid=False,
                    max_violations=0,
                )
            )
            runner.code_element_to_layers = {element: {"domain"}}
            runner.rules = [ExternalImportRule("domain", ["requests"])]

            runner.run_external_import_checks()

        self.assertEqual(len(runner.analysis_errors), 1)
        self.assertIn(f"failed to analyze {missing_file}:", runner.analysis_errors[0])

    def test_runner_checks_external_imports_for_every_layer_membership(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            file_path = Path(temporary_directory) / "service.py"
            file_path.write_text("import requests\n")
            element = CodeElement(
                file=file_path,
                name="load_user",
                element_type="function",
                line=2,
                column=0,
            )
            runner = DeplyRunner(
                argparse.Namespace(
                    config="deply.yaml",
                    parallel=None,
                    report_format="text",
                    output=None,
                    mermaid=False,
                    max_violations=0,
                )
            )
            runner.code_element_to_layers = {
                element: {"application", "domain"},
            }
            runner.rules = [
                ExternalImportRule("application", ["requests"]),
                ExternalImportRule("domain", ["requests"]),
            ]

            with patch(
                "deply.deply_runner.extract_absolute_imports",
                wraps=extract_absolute_imports,
            ) as extract_imports:
                runner.run_external_import_checks()

        self.assertEqual(extract_imports.call_count, 1)
        self.assertEqual(
            {violation.message.split("'")[1] for violation in runner.violations},
            {"application", "domain"},
        )

    def test_runner_reports_external_imports_and_skips_relative_imports(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory) / "test_project"
            domain_path = project_path / "domain"
            domain_path.mkdir(parents=True)
            (domain_path / "entities.py").write_text("class User:\n    pass\n")
            (domain_path / "service.py").write_text(
                "import requests\n"
                "from django.db import models\n"
                "from .entities import User\n"
                "\n"
                "def load_user():\n"
                "    return User()\n"
            )
            config_path = Path(temporary_directory) / "deply.yaml"
            config_path.write_text(
                yaml.dump(
                    {
                        "deply": {
                            "paths": [str(project_path)],
                            "layers": [
                                {
                                    "name": "domain",
                                    "collectors": [
                                        {
                                            "type": "file_regex",
                                            "regex": ".*/domain/service.py",
                                        }
                                    ],
                                }
                            ],
                            "ruleset": {
                                "domain": {
                                    "disallow_external_imports": [
                                        "requests",
                                        "django",
                                        "entities",
                                    ]
                                }
                            },
                        }
                    }
                )
            )
            runner = DeplyRunner(
                argparse.Namespace(
                    config=str(config_path),
                    parallel=None,
                    report_format="json",
                    output=None,
                    mermaid=False,
                    max_violations=0,
                )
            )

            with patch("sys.stdout", new=io.StringIO()) as output_stream:
                result = runner.run()

        payload = json.loads(output_stream.getvalue())

        self.assertFalse(result)
        self.assertEqual(payload["total_violations"], 2)
        self.assertEqual(payload["by_type"]["disallowed_external_import"], 2)
        self.assertEqual(
            sorted(violation["line"] for violation in payload["violations"]),
            [1, 2],
        )
        violations_by_line = {
            violation["line"]: violation
            for violation in payload["violations"]
        }
        self.assertEqual(violations_by_line[1]["element_name"], "load_user")
        self.assertEqual(violations_by_line[1]["element_type"], "function")
        self.assertEqual(violations_by_line[1]["column"], 0)
        self.assertEqual(violations_by_line[2]["element_name"], "load_user")
        self.assertEqual(violations_by_line[2]["element_type"], "function")
        self.assertEqual(violations_by_line[2]["column"], 0)

    def test_runner_applies_line_suppression(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory) / "test_project"
            domain_path = project_path / "domain"
            domain_path.mkdir(parents=True)
            (domain_path / "service.py").write_text(
                "import requests  # deply:ignore:DISALLOWED_EXTERNAL_IMPORT\n"
                "\n"
                "def load_user():\n"
                "    return None\n"
            )
            config_path = Path(temporary_directory) / "deply.yaml"
            config_path.write_text(
                yaml.dump(
                    {
                        "deply": {
                            "paths": [str(project_path)],
                            "layers": [
                                {
                                    "name": "domain",
                                    "collectors": [
                                        {
                                            "type": "file_regex",
                                            "regex": ".*/domain/service.py",
                                        }
                                    ],
                                }
                            ],
                            "ruleset": {
                                "domain": {
                                    "disallow_external_imports": ["requests"]
                                }
                            },
                        }
                    }
                )
            )
            runner = DeplyRunner(
                argparse.Namespace(
                    config=str(config_path),
                    parallel=None,
                    report_format="json",
                    output=None,
                    mermaid=False,
                    max_violations=0,
                )
            )

            with patch("sys.stdout", new=io.StringIO()) as output_stream:
                result = runner.run()

        payload = json.loads(output_stream.getvalue())

        self.assertTrue(result)
        self.assertEqual(payload["total_violations"], 0)

    def test_runner_applies_file_level_suppression(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory) / "test_project"
            domain_path = project_path / "domain"
            domain_path.mkdir(parents=True)
            (domain_path / "service.py").write_text(
                "# deply:ignore-file:DISALLOWED_EXTERNAL_IMPORT\n"
                "import requests\n"
                "\n"
                "def load_user():\n"
                "    return None\n"
            )
            config_path = Path(temporary_directory) / "deply.yaml"
            config_path.write_text(
                yaml.dump(
                    {
                        "deply": {
                            "paths": [str(project_path)],
                            "layers": [
                                {
                                    "name": "domain",
                                    "collectors": [
                                        {
                                            "type": "file_regex",
                                            "regex": ".*/domain/service.py",
                                        }
                                    ],
                                }
                            ],
                            "ruleset": {
                                "domain": {
                                    "disallow_external_imports": ["requests"]
                                }
                            },
                        }
                    }
                )
            )
            runner = DeplyRunner(
                argparse.Namespace(
                    config=str(config_path),
                    parallel=None,
                    report_format="json",
                    output=None,
                    mermaid=False,
                    max_violations=0,
                )
            )

            with patch("sys.stdout", new=io.StringIO()) as output_stream:
                result = runner.run()

        payload = json.loads(output_stream.getvalue())

        self.assertTrue(result)
        self.assertEqual(payload["total_violations"], 0)

    def test_runner_fails_when_external_import_file_has_no_collected_elements(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory) / "test_project"
            domain_path = project_path / "domain"
            domain_path.mkdir(parents=True)
            (domain_path / "empty.py").write_text("import requests\n")
            config_path = Path(temporary_directory) / "deply.yaml"
            config_path.write_text(
                yaml.dump(
                    {
                        "deply": {
                            "paths": [str(project_path)],
                            "layers": [
                                {
                                    "name": "domain",
                                    "collectors": [
                                        {
                                            "type": "file_regex",
                                            "regex": ".*/domain/empty.py",
                                        }
                                    ],
                                }
                            ],
                            "ruleset": {
                                "domain": {
                                    "disallow_external_imports": ["requests"]
                                }
                            },
                        }
                    }
                )
            )
            runner = DeplyRunner(
                argparse.Namespace(
                    config=str(config_path),
                    parallel=None,
                    report_format="json",
                    output=None,
                    mermaid=False,
                    max_violations=0,
                )
            )

            with patch("sys.stderr", new=io.StringIO()) as error_stream:
                result = runner.run()

        self.assertFalse(result)
        self.assertIn("no code elements mapped to configured layers", error_stream.getvalue())


if __name__ == "__main__":
    unittest.main()
