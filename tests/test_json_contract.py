import datetime
import io
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import yaml

from deply.main import main
from deply.models.code_element import CodeElement
from deply.models.dependency import Dependency
from deply.reports.formats.json_report import JsonReport
from deply.reports.report_generator import ReportGenerator
from deply.rules.rule_factory import RuleFactory


class TestJsonContract(unittest.TestCase):
    def _dependency_violation(self, root):
        source = CodeElement(root / "domain/service.py", "Service.load", "function", 2, 0)
        target = CodeElement(root / "infra/store.py", "Store", "class", 4, 0)
        dependency = Dependency(source, target, "function_call", 3, 4)
        rule = RuleFactory.create_rules({"domain": {"disallow_layer_dependencies": ["infra"]}})[0]
        return replace(rule.check("domain", "infra", dependency), rule_id=rule.rule_id)

    def _record(self, violation, root):
        return json.loads(JsonReport([violation], root=root).generate())["violations"][0]

    def test_dependency_context_preserves_legacy_fields(self):
        root = Path.cwd()
        violation = self._dependency_violation(root)
        record = self._record(violation, root)
        for key, value in violation.to_dict().items():
            self.assertEqual(record[key], value)
        self.assertEqual(record["source"], {
            "file": "domain/service.py", "name": "Service.load", "type": "function",
        })
        self.assertEqual(record["target"], {"file": "infra/store.py", "name": "Store", "type": "class"})
        self.assertEqual(record["source_layer"], "domain")
        self.assertEqual(record["target_layer"], "infra")
        self.assertEqual(record["dependency_type"], "function_call")
        self.assertTrue(record["rule_id"].startswith("domain:disallow_layer_dependencies:"))
        self.assertRegex(record["fingerprint"], r"^[0-9a-f]{64}$")

    def test_fingerprint_ignores_locations_message_and_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            first_root = Path(directory) / "first"
            second_root = Path(directory) / "second"
            original = self._dependency_violation(first_root)
            moved = self._dependency_violation(second_root)
            moved = replace(moved, line=100, column=20, message="different wording", dependency=replace(
                moved.dependency, line=100, column=20,
                code_element=replace(moved.dependency.code_element, line=99, column=8),
                depends_on_code_element=replace(moved.dependency.depends_on_code_element, line=30),
            ))
            self.assertEqual(self._record(original, first_root)["fingerprint"],
                             self._record(moved, second_root)["fingerprint"])

    def test_fingerprint_distinguishes_target_layers_dependency_and_rule(self):
        root = Path.cwd()
        original = self._dependency_violation(root)
        original_fingerprint = self._record(original, root)["fingerprint"]
        for changed in [
            replace(original, source_layer="another_domain"),
            replace(original, target_layer="another_infra"),
            replace(original, rule_id="another_rule"),
            replace(original, dependency=replace(original.dependency, dependency_type="inheritance")),
            replace(original, dependency=replace(original.dependency,
                    depends_on_code_element=replace(original.dependency.depends_on_code_element, name="Other"))),
        ]:
            with self.subTest(changed=changed):
                self.assertNotEqual(original_fingerprint, self._record(changed, root)["fingerprint"])
        other_target = replace(original, dependency=replace(original.dependency,
                               depends_on_code_element=replace(original.dependency.depends_on_code_element, name="Other")))
        self.assertEqual(len({original, other_target}), 2)
        self.assertNotEqual(original, object())

    def test_configured_rule_ids_ignore_mapping_and_set_order_but_preserve_constraints(self):
        rules = RuleFactory.create_rules({"domain": {
            "disallow_layer_dependencies": ["infra", "app"],
            "enforce_class_naming": [
                {"type": "class_name_regex", "class_name_regex": "^Good$"},
                {"class_name_regex": "^Good$", "type": "class_name_regex"},
                {"type": "class_name_regex", "class_name_regex": "^Other$"},
            ],
        }})
        reordered = RuleFactory.create_rules({"domain": {"disallow_layer_dependencies": ["app", "infra", "app"]}})
        self.assertEqual(rules[0].rule_id, reordered[0].rule_id)
        self.assertEqual(rules[1].rule_id, rules[2].rule_id)
        self.assertNotEqual(rules[1].rule_id, rules[3].rule_id)

    def _run_cli(self, directory, configuration, source=None, output=False, mermaid=False, parallel=None):
        root = Path(directory)
        config_path = root / "deply.yaml"
        config_path.write_text(yaml.safe_dump(configuration))
        if source is not None:
            (root / "app.py").write_text(source)
        output_path = root / "report.json"
        output_path.write_text("stale report")
        arguments = ["deply", "analyze", "--config", str(config_path), "--report-format", "json"]
        if output:
            arguments.extend(["--output", str(output_path)])
        if mermaid:
            arguments.append("--mermaid")
        if parallel is not None:
            arguments.extend(["--parallel", str(parallel)])
        with patch.object(sys, "argv", arguments), patch("sys.stdout", new=io.StringIO()) as stdout, patch(
            "sys.stderr", new=io.StringIO()
        ) as stderr:
            with self.assertRaises(SystemExit) as exit_context:
                main()
        payload = json.loads(output_path.read_text() if output else stdout.getvalue())
        return exit_context.exception.code, payload, stderr.getvalue(), stdout.getvalue()

    def _config(self, directory, regex=".*", rules=None):
        return {"deply": {
            "paths": [directory],
            "layers": [{"name": "app", "collectors": [{"type": "file_regex", "regex": regex}]}],
            "ruleset": rules or {},
        }}

    def test_cli_reports_complete_empty_violations_and_incomplete_analysis(self):
        for source, regex, expected_status, expected_exit, count in [
            ("class Expected: pass\n", ".*", "complete", 0, 0),
            ("class Actual: pass\n", ".*", "complete", 1, 1),
            ("class Broken:\n", ".*", "incomplete", 1, 0),
            ("class Actual: pass\n", "never-matches", "incomplete", 1, 0),
            (None, ".*", "incomplete", 1, 0),
        ]:
            for output in (False, True):
                with self.subTest(source=source, output=output), tempfile.TemporaryDirectory() as directory:
                    rules = {"app": {"enforce_class_naming": [
                        {"type": "class_name_regex", "class_name_regex": "^Expected$"},
                    ]}}
                    result, payload, errors, _ = self._run_cli(
                        directory, self._config(directory, regex, rules), source, output,
                    )
                    self.assertEqual(result, expected_exit)
                    self.assertEqual(payload["schema_version"], 1)
                    self.assertEqual(payload["status"], expected_status)
                    self.assertEqual(payload["total_violations"], count)
                    self.assertIn("metrics", payload)
                    if expected_status == "incomplete":
                        self.assertTrue(payload["errors"])
                        self.assertEqual(payload["errors"][0]["code"], "incomplete_analysis")
                        self.assertIn("Incomplete analysis:", errors)
                    else:
                        self.assertEqual(payload["errors"], [])

    def test_cli_invalid_configuration_and_mermaid_keep_json_parseable(self):
        for output in (False, True):
            with self.subTest(output=output), tempfile.TemporaryDirectory() as directory:
                result, payload, errors, _ = self._run_cli(directory, {"deply": []}, output=output)
                self.assertEqual(result, 1)
                self.assertEqual(payload["status"], "invalid_configuration")
                self.assertEqual(payload["errors"][0]["code"], "invalid_configuration")
                self.assertNotIn("metrics", payload)
                self.assertIn("Invalid deply configuration:", errors)
        with tempfile.TemporaryDirectory() as directory:
            result, payload, errors, _ = self._run_cli(
                directory, self._config(directory), "class Actual: pass\n", mermaid=True,
            )
            self.assertEqual(result, 0)
            self.assertEqual(payload["status"], "complete")
            self.assertIn("Mermaid Diagram", errors)

    def test_cli_overlapping_layers_and_distinct_rules_preserve_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target.py").write_text("class Target: pass\n")
            configuration = {"deply": {
                "paths": [directory],
                "layers": [
                    {"name": layer, "collectors": [{"type": "file_regex", "regex": regex}]}
                    for layer, regex in [("app", "app.py"), ("context", "app.py"), ("infra", "target.py")]
                ],
                "ruleset": {
                    "app": {"disallow_layer_dependencies": ["infra"], "enforce_class_naming": [
                        {"type": "class_name_regex", "class_name_regex": "^Expected$"},
                        {"type": "class_name_regex", "class_name_regex": "^Other$"},
                    ]},
                    "context": {"disallow_layer_dependencies": ["infra"]},
                },
            }}
            sequential = self._run_cli(directory, configuration, "from target import Target\nclass Actual: pass\n")[1]
            parallel = self._run_cli(directory, configuration, parallel=2)[1]
            self.assertEqual(sequential, parallel)
            dependency_records = [item for item in sequential["violations"] if item["target"]]
            self.assertEqual({item["source_layer"] for item in dependency_records}, {"app", "context"})
            naming_records = [item for item in sequential["violations"] if item["violation_type"] == "class_naming"]
            self.assertEqual(len(naming_records), 2)
            self.assertEqual(len({item["fingerprint"] for item in naming_records}), 2)

    def test_external_import_identity_uses_module_not_arbitrary_collected_element(self):
        from deply.rules.external_import_rule import ExternalImportRule
        rule = ExternalImportRule("domain", ["requests"])
        element = CodeElement(Path("domain.py"), "First", "class", 1, 0)
        original = rule.check_external_import("domain", element, "requests.sessions", 5, 0)
        changed = rule.check_external_import("domain", replace(element, name="Another", line=10), "requests.sessions", 20, 0)
        original_data = self._record(original, Path.cwd())
        self.assertEqual(original_data["fingerprint"], self._record(changed, Path.cwd())["fingerprint"])
        self.assertEqual(original_data["source"]["type"], "module")
        self.assertEqual(original_data["target"], {"module": "requests.sessions", "type": "external_module"})

    def test_report_order_is_stable_for_distinct_sources_at_same_location(self):
        root = Path.cwd()
        original = self._dependency_violation(root)
        other_source = replace(original, element_name="Other.load", dependency=replace(
            original.dependency, code_element=replace(original.dependency.code_element, name="Other.load"),
        ))
        self.assertEqual(
            ReportGenerator([original, other_source], root=root).generate("json"),
            ReportGenerator([other_source, original], root=root).generate("json"),
        )

    def test_cli_bool_and_external_rules_have_configured_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            rules = {"app": {
                "disallow_external_imports": ["requests"],
                "enforce_class_naming": [{"type": "bool", "must_not": [
                    {"type": "class_name_regex", "class_name_regex": "^Actual$"},
                ]}],
            }}
            result, payload, _, _ = self._run_cli(
                directory, self._config(directory, rules=rules), "import requests.sessions\nclass Actual: pass\n",
            )
            self.assertEqual(result, 1)
            self.assertEqual(payload["total_violations"], 2)
            for record in payload["violations"]:
                self.assertEqual(record["source_layer"], "app")
                self.assertTrue(record["rule_id"].startswith("app:"))
                self.assertIsNone(record["dependency_type"])
            bool_record = next(record for record in payload["violations"] if record["violation_type"] == "bool_rule")
            self.assertIsNone(bool_record["target"])
            self.assertIn(":enforce_class_naming:", bool_record["rule_id"])

    def test_ignored_yaml_values_do_not_break_analysis_or_change_rule_identity(self):
        for nested in (False, True):
            with self.subTest(nested=nested), tempfile.TemporaryDirectory() as directory:
                constraint = {"type": "class_name_regex", "class_name_regex": "^Expected$"}
                rule_config = {"type": "bool", "must": [constraint]} if nested else constraint
                rules = {"app": {"enforce_class_naming": [rule_config]}}
                baseline = self._run_cli(
                    directory, self._config(directory, rules=rules), "class Actual: pass\n",
                )[1]
                constraint["note"] = datetime.date(2026, 1, 1)
                rule_config["metadata"] = {"another_note": datetime.date(2026, 1, 2)}
                result, payload, _, _ = self._run_cli(directory, self._config(directory, rules=rules))
                self.assertEqual(result, 1)
                self.assertEqual(payload["status"], "complete")
                self.assertEqual(payload["violations"][0]["rule_id"], baseline["violations"][0]["rule_id"])
                self.assertEqual(payload["violations"][0]["fingerprint"], baseline["violations"][0]["fingerprint"])

    def test_cross_drive_paths_use_absolute_file_uri(self):
        root = Path.cwd()
        violation = self._dependency_violation(root)
        with patch("deply.reports.formats.json_report.os.path.relpath", side_effect=ValueError("different drives")):
            record = self._record(violation, root)
        self.assertEqual(record["source"]["file"], violation.file.resolve().as_uri())
        self.assertEqual(record["target"]["file"], violation.dependency.depends_on_code_element.file.resolve().as_uri())
