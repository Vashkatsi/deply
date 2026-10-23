import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from deply.main import main


class TestContext(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source_root = self.root / "src"
        self.source_root.mkdir()
        self.config = self.root / "deply.yaml"
        self.selected = self.source_root / "service.py"
        self.selected.write_text("from store import Store\ndef serve():\n    return Store()\n")
        (self.source_root / "store.py").write_text("class Store: pass\n")
        (self.source_root / "caller.py").write_text("from service import serve\ndef call():\n    return serve()\n")
        (self.source_root / "other.py").write_text("class Other: pass\n")
        self.configuration = {"deply": {
            "paths": [str(self.source_root)],
            "layers": [
                {"name": name, "collectors": [{"type": "file_regex", "regex": filename}]}
                for name, filename in [("service", "service.py"), ("shared", "service.py"),
                                       ("store", "store.py"), ("caller", "caller.py"), ("other", "other.py")]
            ],
            "ruleset": {
                "service": {"disallow_layer_dependencies": ["store"], "disallow_external_imports": ["requests"]},
                "shared": {"enforce_function_naming": [{"type": "function_name_regex", "function_name_regex": "^serve$"}]},
                "caller": {"disallow_layer_dependencies": ["service"]},
                "other": {"enforce_class_naming": [{"type": "class_name_regex", "class_name_regex": "^Good$"}]},
            },
        }}

    def run_cli(self, selected=None, command="context", extra=()):
        self.config.write_text(yaml.safe_dump(self.configuration))
        arguments = ["deply", command, "--config", str(self.config), "--report-format", "json"]
        if command == "context":
            arguments += ["--file", str(selected or self.selected)]
        with patch.object(sys, "argv", arguments + list(extra)), patch("sys.stdout", new=io.StringIO()) as stdout:
            with patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit) as result:
                main()
        return result.exception.code, json.loads(stdout.getvalue())

    def test_direct_edges_memberships_rules_and_shared_violation_identities(self):
        result, report = self.run_cli()
        self.assertEqual(result, 0)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["file"], "src/service.py")
        self.assertEqual(report["file_status"], "mapped")
        self.assertEqual(report["elements"], [{
            "file": "src/service.py", "name": "serve", "type": "function", "line": 2,
            "column": 0, "layers": ["service", "shared"],
        }])
        incoming = report["incoming"]
        outgoing = report["outgoing"]
        self.assertTrue(any(edge["dependency_type"] == "function_call" and edge["line"] == 3 for edge in incoming))
        self.assertEqual({edge["source"]["file"] for edge in incoming}, {"src/caller.py"})
        self.assertEqual({edge["target"]["file"] for edge in outgoing}, {"src/store.py"})
        self.assertEqual(incoming[0]["target"]["layers"], ["service", "shared"])
        self.assertEqual({rule["source_layer"] for rule in report["rules"]}, {"caller", "service", "shared"})
        self.assertEqual(len(report["rules"]), 4)
        _, analysis = self.run_cli(command="analyze")
        related = [item for item in analysis["violations"] if item["source"]["file"] != "src/other.py"]
        self.assertEqual(report["violations"], related)
        self.assertTrue({item["rule_id"] for item in related} <= {rule["rule_id"] for rule in report["rules"]})
        self.assertEqual(report["metrics"], analysis["metrics"])

    def test_unavailable_files(self):
        unmapped = self.source_root / "unmapped.py"
        unmapped.write_text("class Unmapped: pass\n")
        outside = self.root / "outside.py"
        outside.write_text("class Outside: pass\n")
        excluded = self.source_root / "excluded.py"
        excluded.write_text("class Excluded: pass\n")
        self.configuration["deply"]["exclude_files"] = ["excluded.py"]
        for selected, expected in [(unmapped, "unmapped"), (outside, "outside_scope"),
                                   (excluded, "excluded"), (self.root / "missing.py", "not_found"),
                                   (self.config, "not_python"), (self.source_root, "not_python")]:
            with self.subTest(expected=expected):
                result, report = self.run_cli(selected)
                self.assertEqual(result, 1)
                self.assertEqual(report["file_status"], expected)
                self.assertEqual(report["status"], "complete")
                for key in ("elements", "incoming", "outgoing", "rules", "violations"):
                    self.assertEqual(report[key], [])

    def test_incomplete_analysis_and_failed_selected_file(self):
        broken = self.source_root / "broken.py"
        broken.write_text("def broken(:\n")
        for selected, expected in [(self.selected, "mapped"), (broken, "parse_failed")]:
            with self.subTest(expected=expected):
                result, report = self.run_cli(selected)
                self.assertEqual(result, 1)
                self.assertEqual(report["status"], "incomplete")
                self.assertEqual(report["file_status"], expected)
                self.assertEqual(report["errors"][0]["code"], "incomplete_analysis")
                self.assertEqual(report["incoming"], [])

    def test_invalid_configuration_returns_json(self):
        self.configuration["deply"]["paths"] = [str(self.root / "missing")]
        result, report = self.run_cli()
        self.assertEqual(result, 1)
        self.assertEqual(report["status"], "invalid_configuration")
        self.assertTrue(report["errors"])

    def test_no_files_or_no_mapped_elements_fail_closed(self):
        for mode in ("excluded", "unmapped"):
            with self.subTest(mode=mode):
                if mode == "excluded":
                    self.configuration["deply"]["exclude_files"] = [".*"]
                else:
                    self.configuration["deply"]["exclude_files"] = []
                    self.configuration["deply"]["layers"] = [
                        {"name": "service", "collectors": [{"type": "file_regex", "regex": "never-matches"}]},
                    ]
                    self.configuration["deply"]["ruleset"] = {}
                result, report = self.run_cli()
                self.assertEqual(result, 1)
                self.assertEqual(report["status"], "incomplete")
                self.assertEqual(report["file_status"], mode)

    def test_same_file_edges_are_in_both_directions_and_no_transitive_edges(self):
        self.selected.write_text("from store import Store\ndef helper():\n    return Store()\ndef serve():\n    return helper()\n")
        (self.source_root / "store.py").write_text("from other import Other\nclass Store(Other): pass\n")
        result, report = self.run_cli()
        self.assertEqual(result, 0)
        internal = [edge for edge in report["outgoing"] if edge["target"]["file"] == "src/service.py"]
        self.assertTrue(internal)
        for edge in internal:
            self.assertIn(edge, report["incoming"])
        self.assertNotIn("src/other.py", {edge["target"]["file"] for edge in report["outgoing"]})
        self.assertEqual(len(report["outgoing"]), len({json.dumps(edge, sort_keys=True) for edge in report["outgoing"]}))

    def test_suppression_external_and_element_violations(self):
        self.selected.write_text("import requests\nclass Wrong: pass\ndef serve(): pass\n")
        self.configuration["deply"]["ruleset"]["service"]["enforce_class_naming"] = [
            {"type": "class_name_regex", "class_name_regex": "^Good$"},
        ]
        result, report = self.run_cli()
        self.assertEqual(result, 0)
        self.assertTrue(any(item["target"] == {"module": "requests", "type": "external_module"}
                            for item in report["violations"]))
        self.assertTrue(any(item["element_name"] == "Wrong" for item in report["violations"]))
        self.selected.write_text("# deply:ignore-file:*\n" + self.selected.read_text())
        _, suppressed = self.run_cli()
        self.assertFalse(any(item["source"]["file"] == "src/service.py" for item in suppressed["violations"]))
        self.assertTrue(suppressed["incoming"])
        self.assertEqual(suppressed["rules"], report["rules"])

    def test_rules_include_effective_parameters_and_deduplicate(self):
        rule = {"type": "bool", "must": [{"type": "function_name_regex", "function_name_regex": "^serve$"}],
                "ignored_metadata": "not a rule parameter"}
        self.configuration["deply"]["ruleset"]["shared"]["enforce_function_naming"] = [rule, rule]
        _, report = self.run_cli()
        shared_rules = [item for item in report["rules"] if item["source_layer"] == "shared"]
        self.assertEqual(len(shared_rules), 1)
        self.assertEqual(shared_rules[0]["configuration"], {
            "type": "bool", "must": rule["must"], "any_of": [], "must_not": [],
        })

    def test_relative_paths_and_symlink_select_same_file(self):
        _, original = self.run_cli()
        _, relative = self.run_cli(Path(os.path.relpath(self.selected)))
        self.assertEqual(original, relative)
        alias = self.root / "alias.py"
        alias.symlink_to(self.selected)
        _, linked = self.run_cli(alias)
        self.assertEqual(original, linked)

    def test_included_path_wins_over_exclusion_in_overlapping_roots(self):
        self.configuration["deply"]["paths"] = [str(self.root), str(self.source_root)]
        self.configuration["deply"]["exclude_files"] = ["^src/"]
        result, report = self.run_cli()
        self.assertEqual(result, 0)
        self.assertEqual(report["file_status"], "mapped")

    def test_resolver_failure_returns_partial_context(self):
        with patch("deply.deply_runner.CodeAnalyzer.analyze", return_value=["ambiguous internal module"]):
            result, report = self.run_cli()
        self.assertEqual(result, 1)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["errors"], [{"code": "incomplete_analysis", "message": "ambiguous internal module"}])
        self.assertTrue(report["elements"])
        self.assertTrue(report["rules"])

    def test_mapped_file_without_dependencies_still_has_rules_and_findings(self):
        result, report = self.run_cli(self.source_root / "other.py")
        self.assertEqual(result, 0)
        self.assertEqual(report["file_status"], "mapped")
        self.assertEqual(report["incoming"], [])
        self.assertEqual(report["outgoing"], [])
        self.assertEqual(len(report["elements"]), 1)
        self.assertEqual(len(report["rules"]), 1)
        self.assertEqual(len(report["violations"]), 1)

    def test_required_file_and_unsupported_options(self):
        for options in ([], ["--file", str(self.selected), "--report-format", "text"],
                        ["--file", str(self.selected), "--write-baseline", "baseline.json"]):
            with self.subTest(options=options), patch.object(sys, "argv", ["deply", "context", *options]):
                with patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit) as result:
                    main()
                self.assertEqual(result.exception.code, 2)

    def test_deterministic_across_hash_seeds_and_default_json(self):
        self.run_cli()
        outputs = []
        for seed in ("1", "27"):
            result = subprocess.run(
                [sys.executable, "-m", "deply.main", "context", "--config", str(self.config),
                 "--file", str(self.selected)],
                env=dict(os.environ, PYTHONHASHSEED=seed), capture_output=True, text=True, check=True,
            )
            outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(json.loads(outputs[0])["schema_version"], 1)
