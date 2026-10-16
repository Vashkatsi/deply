import copy
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from deply.baseline import load_baseline, write_baseline
from deply.main import main


class TestBaseline(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config = self.root / "deply.yaml"
        self.baseline = self.root / "baseline.json"
        self.source = self.root / "app.py"
        self.source.write_text("class Old: pass\n")
        self.configuration = {"deply": {
            "paths": [str(self.root)],
            "layers": [{"name": "app", "collectors": [{"type": "file_regex", "regex": "app.py"}]}],
            "ruleset": {"app": {"enforce_class_naming": [
                {"type": "class_name_regex", "class_name_regex": "^Good$"},
            ]}},
        }}
        self.config.write_text(yaml.safe_dump(self.configuration))

    def run_cli(self, *options, report_format="json"):
        arguments = ["deply", "analyze", "--config", str(self.config), "--report-format", report_format, *options]
        with patch.object(sys, "argv", arguments), patch("sys.stdout", new=io.StringIO()) as stdout, patch(
            "sys.stderr", new=io.StringIO()
        ) as stderr:
            with self.assertRaises(SystemExit) as context:
                main()
        output = stdout.getvalue()
        return context.exception.code, json.loads(output) if report_format == "json" and output.strip() else output, stderr.getvalue()

    def create_baseline(self):
        result, report, _ = self.run_cli("--write-baseline", str(self.baseline))
        self.assertEqual(result, 0)
        self.assertEqual(report["status"], "complete")
        return self.baseline.read_bytes()

    def test_new_existing_resolved_and_unchanged_baseline(self):
        original = self.create_baseline()
        self.source.write_text("\n\nclass Old: pass\n")
        result, report, _ = self.run_cli("--baseline", str(self.baseline))
        self.assertEqual(result, 0)
        self.assertEqual(report["total_violations"], 1)
        self.assertEqual(report["baseline"]["new"], [])
        self.assertEqual(report["baseline"]["resolved"], [])
        self.assertEqual(report["baseline"]["existing"][0]["line"], 3)
        self.source.write_text("class New: pass\n")
        result, report, _ = self.run_cli("--baseline", str(self.baseline))
        self.assertEqual(result, 1)
        self.assertEqual(report["total_violations"], 1)
        self.assertEqual(report["baseline"]["new"][0]["element_name"], "New")
        self.assertEqual(report["baseline"]["resolved"][0]["element_name"], "Old")
        self.assertEqual(report["baseline"]["existing"], [])
        self.source.write_text("class Good: pass\n")
        result, report, _ = self.run_cli("--baseline", str(self.baseline))
        self.assertEqual(result, 0)
        self.assertEqual(len(report["baseline"]["resolved"]), 1)
        self.assertEqual(report["baseline"]["new"], [])
        self.assertEqual(self.baseline.read_bytes(), original)

    def test_empty_baseline_and_changed_rule(self):
        self.source.write_text("class Good: pass\n")
        self.create_baseline()
        self.assertEqual(load_baseline(self.baseline), [])
        self.source.write_text("class Old: pass\n")
        self.assertEqual(self.run_cli("--baseline", str(self.baseline))[0], 1)
        self.baseline.unlink()
        self.create_baseline()
        self.configuration["deply"]["ruleset"]["app"]["enforce_class_naming"][0]["class_name_regex"] = "^Better$"
        self.config.write_text(yaml.safe_dump(self.configuration))
        result, report, _ = self.run_cli("--baseline", str(self.baseline))
        self.assertEqual(result, 1)
        self.assertEqual(len(report["baseline"]["new"]), 1)
        self.assertEqual(len(report["baseline"]["resolved"]), 1)

    def test_missing_invalid_baseline_and_output_file(self):
        for contents in (None, "{", "[]", '{"schema_version":1,"schema_version":1,"violations":[]}'):
            with self.subTest(contents=contents):
                if contents is not None:
                    self.baseline.write_text(contents)
                result, report, errors = self.run_cli("--baseline", str(self.baseline))
                self.assertEqual(result, 1)
                self.assertEqual(report["status"], "incomplete")
                self.assertEqual(report["errors"][0]["code"], "baseline_error")
                self.assertNotIn("baseline", report)
                self.assertIn("Baseline error:", errors)
        output = self.root / "report.json"
        result, stdout, _ = self.run_cli("--baseline", str(self.baseline), "--output", str(output))
        self.assertEqual(result, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(json.loads(output.read_text())["status"], "incomplete")

    def test_malformed_baseline_records_fail_closed(self):
        self.create_baseline()
        valid = json.loads(self.baseline.read_text())
        malformed = [None, [], {}, {"schema_version": True, "violations": []},
                     {"schema_version": 2, "violations": []}, {"schema_version": 1, "violations": {}},
                     dict(valid, status="incomplete")]
        for field, value in [("fingerprint", "0" * 64), ("source", []), ("source", {}),
                             ("target", 123), ("target", {}), ("rule_id", ""), ("rule_id", []),
                             ("source_layer", 123), ("line", True), ("column", -1), ("message", None)]:
            changed = copy.deepcopy(valid)
            changed["violations"][0][field] = value
            malformed.append(changed)
        malformed.extend([dict(valid, violations=[None]), dict(valid, violations=[{}])])
        for payload in malformed:
            with self.subTest(payload=payload):
                self.baseline.write_text(json.dumps(payload))
                self.assertEqual(self.run_cli("--baseline", str(self.baseline))[0], 1)
        self.baseline.write_bytes(b"\xff")
        self.assertEqual(self.run_cli("--baseline", str(self.baseline))[0], 1)

    def test_incomplete_and_invalid_config_never_create_or_compare(self):
        for source in ("class Broken:\n", "", None):
            for option in ("--write-baseline", "--baseline"):
                with self.subTest(source=source, option=option):
                    if source is None:
                        self.source.unlink(missing_ok=True)
                    else:
                        self.source.write_text(source)
                    result, report, _ = self.run_cli(option, str(self.baseline))
                    self.assertEqual(result, 1)
                    self.assertEqual(report["status"], "incomplete")
                    self.assertNotIn("baseline", report)
                    self.assertFalse(self.baseline.exists())
        self.config.write_text("deply: []\n")
        result, report, _ = self.run_cli("--write-baseline", str(self.baseline))
        self.assertEqual(result, 1)
        self.assertEqual(report["status"], "invalid_configuration")
        self.assertFalse(self.baseline.exists())

    def test_existing_baseline_is_not_overwritten_even_with_symlink(self):
        original = self.create_baseline()
        for destination in (self.baseline, self.root / "link.json"):
            if destination != self.baseline:
                destination.symlink_to(self.baseline)
            result, report, _ = self.run_cli("--write-baseline", str(destination))
            self.assertEqual(result, 1)
            self.assertEqual(report["errors"][0]["code"], "baseline_error")
            self.assertEqual(self.baseline.read_bytes(), original)
        with patch("deply.baseline.os.link", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                write_baseline(self.root / "failed.json", [])
        self.assertFalse((self.root / "failed.json").exists())
        self.assertEqual(list(self.root.glob(".deply-baseline-*")), [])

    def test_reject_conflicting_options_and_output_aliases(self):
        original = self.create_baseline()
        alias = self.root / "alias.json"
        alias.symlink_to(self.baseline)
        hardlink = self.root / "hardlink.json"
        os.link(self.baseline, hardlink)
        options = [
            ("--baseline", str(self.baseline), "--write-baseline", str(self.root / "new.json")),
            ("--baseline", str(self.baseline), "--max-violations", "1"),
            ("--write-baseline", str(self.root / "new.json"), "--max-violations", "-1"),
        ] + [("--baseline", str(self.baseline), "--output", str(path))
             for path in (self.baseline, self.config, alias, hardlink)]
        for arguments in options:
            with self.subTest(arguments=arguments):
                self.assertEqual(self.run_cli(*arguments)[0], 2)
        self.assertEqual(self.baseline.read_bytes(), original)

    def test_other_formats_filter_existing_findings(self):
        self.create_baseline()
        self.source.write_text("class Old: pass\nclass New: pass\n")
        for report_format in ("text", "github-actions", "sarif"):
            with self.subTest(report_format=report_format):
                result, output, _ = self.run_cli("--baseline", str(self.baseline), report_format=report_format)
                self.assertEqual(result, 1)
                self.assertIn("New", output)
                self.assertNotIn("Old", output)
        self.baseline.write_text("broken")
        result, _, errors = self.run_cli("--baseline", str(self.baseline), report_format="text")
        self.assertEqual(result, 1)
        self.assertIn("Baseline error", errors)

    def test_report_output_parallel_and_mermaid_preserve_json_contract(self):
        self.create_baseline()
        result, report, errors = self.run_cli("--baseline", str(self.baseline), "--parallel", "2", "--mermaid")
        self.assertEqual(result, 0)
        self.assertEqual(len(report["baseline"]["existing"]), 1)
        self.assertIn("Mermaid Diagram", errors)
        output = self.root / "report.json"
        result, stdout, _ = self.run_cli("--baseline", str(self.baseline), "--output", str(output))
        self.assertEqual(result, 0)
        self.assertEqual(stdout, "")
        self.assertEqual(json.loads(output.read_text())["baseline"], report["baseline"])

    def test_dependency_relationships_repeated_locations_and_checkout_move(self):
        self.configuration["deply"]["layers"].append({
            "name": "infra", "collectors": [{"type": "file_regex", "regex": "target.py"}],
        })
        self.configuration["deply"]["ruleset"] = {"app": {"disallow_layer_dependencies": ["infra"]}}
        self.config.write_text(yaml.safe_dump(self.configuration))
        (self.root / "target.py").write_text("class Target: pass\nclass Other: pass\n")
        self.source.write_text("from target import Target\ndef call():\n    Target()\n")
        original = self.create_baseline()
        self.source.write_text("from target import Target\ndef call():\n    Target()\n    Target()\n")
        result, report, _ = self.run_cli("--baseline", str(self.baseline))
        self.assertEqual(result, 0)
        self.assertGreater(len(report["baseline"]["existing"]), len(load_baseline(self.baseline)))
        self.source.write_text("from target import Other\ndef call():\n    Other()\n")
        result, report, _ = self.run_cli("--baseline", str(self.baseline))
        self.assertEqual(result, 1)
        self.assertTrue(report["baseline"]["new"])
        self.assertTrue(report["baseline"]["resolved"])
        with tempfile.TemporaryDirectory() as relocated:
            relocated_root = Path(relocated)
            self.configuration["deply"]["paths"] = [relocated]
            self.config = relocated_root / "deply.yaml"
            self.config.write_text(yaml.safe_dump(self.configuration))
            (relocated_root / "app.py").write_text("from target import Target\ndef call():\n    Target()\n")
            (relocated_root / "target.py").write_text("class Target: pass\nclass Other: pass\n")
            self.baseline = relocated_root / "baseline.json"
            self.baseline.write_bytes(original)
            self.assertEqual(self.run_cli("--baseline", str(self.baseline))[0], 0)

    def test_external_import_baseline_and_ignored_findings(self):
        self.configuration["deply"]["ruleset"] = {"app": {"disallow_external_imports": ["requests"]}}
        self.config.write_text(yaml.safe_dump(self.configuration))
        self.source.write_text("import requests\nclass Old: pass\n")
        self.create_baseline()
        self.assertEqual(self.run_cli("--baseline", str(self.baseline))[0], 0)
        self.source.write_text("import requests  # deply:ignore:DISALLOWED_EXTERNAL_IMPORT\nclass Old: pass\n")
        result, report, _ = self.run_cli("--baseline", str(self.baseline))
        self.assertEqual(result, 0)
        self.assertEqual(len(report["baseline"]["resolved"]), 1)

    def test_empty_paths_and_missing_creation_directory_fail(self):
        for option in ("--baseline", "--write-baseline"):
            result, report, _ = self.run_cli(option, "")
            self.assertEqual(result, 1)
            self.assertEqual(report["errors"][0]["code"], "baseline_error")
        result, report, _ = self.run_cli("--write-baseline", str(self.root / "missing" / "baseline.json"))
        self.assertEqual(result, 1)
        self.assertEqual(report["errors"][0]["code"], "baseline_error")

    def test_creation_rejects_output_before_publishing_baseline(self):
        original_config = self.config.read_bytes()
        for output in (self.root / "BASELINE.json", self.root / "report.json"):
            result, _, errors = self.run_cli("--write-baseline", str(self.baseline), "--output", str(output))
            self.assertEqual(result, 2)
            self.assertIn("--output cannot be combined with --write-baseline", errors)
            self.assertFalse(self.baseline.exists())
            self.assertFalse(output.exists())
            self.assertEqual(self.config.read_bytes(), original_config)
