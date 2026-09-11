import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from deply import __version__

from deply.models.violation import Violation
from deply.models.violation_types import ViolationType
from deply.reports.formats.github_actions_report import GitHubActionsReport
from deply.reports.formats.json_report import JsonReport
from deply.reports.report_generator import ReportGenerator


class TestReports(unittest.TestCase):
    def test_sarif_rules_results_and_metrics(self):
        violations = [
            self._build_violation("app.py", 2, 4, "z", ViolationType.FUNCTION_NAMING),
            self._build_violation("app.py", 2, 4, "b", ViolationType.CLASS_NAMING),
            self._build_violation("app.py", 2, 4, "a", ViolationType.CLASS_NAMING),
        ]
        payload = json.loads(ReportGenerator(violations, self.metrics).generate("sarif"))
        self.assertEqual(payload["version"], "2.1.0")
        self.assertEqual(payload["$schema"], "https://json.schemastore.org/sarif-2.1.0.json")
        run = payload["runs"][0]
        self.assertEqual(run["tool"]["driver"]["name"], "Deply")
        self.assertEqual(run["tool"]["driver"]["version"], __version__)
        rules = run["tool"]["driver"]["rules"]
        self.assertEqual([rule["id"] for rule in rules], ["class_naming", "function_naming"])
        self.assertEqual(rules[0]["shortDescription"], {"text": "Class Naming"})
        self.assertEqual(rules[0]["helpUri"], "https://vashkatsi.github.io/deply/doc/rules.html")
        self.assertEqual(run["properties"]["metrics"], self.metrics)
        self.assertEqual([result["message"]["text"] for result in run["results"]], ["a", "b", "z"])
        for result in run["results"]:
            self.assertIn(result["ruleId"], [rule["id"] for rule in rules])
            self.assertEqual(result["level"], "warning")
            self.assertEqual(result["locations"][0]["physicalLocation"]["region"], {"startLine": 2})
        self.assertEqual(
            ReportGenerator(violations).generate("sarif"),
            ReportGenerator(list(reversed(violations))).generate("sarif"),
        )

    def test_sarif_empty_results(self):
        run = json.loads(ReportGenerator([]).generate("sarif"))["runs"][0]
        self.assertEqual(run["results"], [])
        self.assertEqual(run["tool"]["driver"]["rules"], [])
        self.assertNotIn("properties", run)

    def test_sarif_file_uris_and_unknown_line(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            source_root = root / "project"
            source_root.mkdir()
            target = source_root / "модуль #%.py"
            target.touch()
            alias = source_root / "alias.py"
            alias.symlink_to(target)
            outside = root / "outside file.py"
            for file_path, expected_location in [
                (target, {"uri": "%D0%BC%D0%BE%D0%B4%D1%83%D0%BB%D1%8C%20%23%25.py", "uriBaseId": "%SRCROOT%"}),
                (alias, {"uri": "%D0%BC%D0%BE%D0%B4%D1%83%D0%BB%D1%8C%20%23%25.py", "uriBaseId": "%SRCROOT%"}),
                (outside, {"uri": outside.as_uri()}),
            ]:
                with self.subTest(file=file_path), patch("pathlib.Path.cwd", return_value=source_root):
                    violation = self._build_violation(str(file_path), 0, 5, "message", ViolationType.CLASS_NAMING)
                    run = json.loads(ReportGenerator([violation]).generate("sarif"))["runs"][0]
                    location = run["results"][0]["locations"][0]["physicalLocation"]
                    self.assertEqual(location, {"artifactLocation": expected_location})
                    self.assertEqual(run["originalUriBaseIds"]["%SRCROOT%"]["uri"], source_root.as_uri() + "/")

    metrics = {
        "files_discovered": 2,
        "files_excluded": 0,
        "files_included": 2,
        "files_parsed": 2,
        "files_parse_failed": 0,
        "files_mapped": 1,
        "files_unmapped": 1,
        "elements_mapped": 1,
        "elements_overlapping": 0,
        "dependencies_detected": 3,
    }

    @staticmethod
    def _build_violation(
        file_path: str,
        line: int,
        column: int,
        message: str,
        violation_type: ViolationType,
    ) -> Violation:
        return Violation(
            file=Path(file_path),
            element_name="SampleElement",
            element_type="class",
            line=line,
            column=column,
            message=message,
            violation_type=violation_type,
        )

    def test_github_actions_report_sorts_and_adds_summary(self):
        violations = [
            self._build_violation("b.py", 5, 2, "second", ViolationType.CLASS_NAMING),
            self._build_violation("a.py", 2, 1, "first", ViolationType.CLASS_NAMING),
            self._build_violation("c.py", 1, 0, "third", ViolationType.FUNCTION_NAMING),
        ]

        report_output = GitHubActionsReport(violations, self.metrics).generate().splitlines()

        warning_lines = [line for line in report_output if line.startswith("::warning")]
        self.assertEqual(len(warning_lines), 3)
        self.assertEqual(
            warning_lines[0],
            "::warning file=a.py,line=2,col=1::first",
        )
        self.assertEqual(
            warning_lines[1],
            "::warning file=b.py,line=5,col=2::second",
        )
        self.assertIn("# Class Naming: 2", report_output)
        self.assertIn("# Function Naming: 1", report_output)
        self.assertIn("# Total Violations: 3", report_output)
        self.assertEqual(report_output[-10], "# files_discovered: 2")
        self.assertEqual(report_output[-1], "# dependencies_detected: 3")

    def test_json_report_generates_expected_payload(self):
        violations = [
            self._build_violation("app.py", 10, 0, "dependency issue", ViolationType.DISALLOWED_DEPENDENCY),
            self._build_violation("app.py", 20, 2, "naming issue", ViolationType.FUNCTION_NAMING),
        ]

        payload = json.loads(JsonReport(violations, self.metrics).generate())

        self.assertEqual(payload["total_violations"], 2)
        self.assertEqual(payload["by_type"]["disallowed_dependency"], 1)
        self.assertEqual(payload["by_type"]["function_naming"], 1)
        self.assertEqual(payload["violations"][0]["file"], "app.py")
        self.assertEqual(payload["violations"][0]["violation_type"], "disallowed_dependency")
        self.assertEqual(payload["violations"][1]["violation_type"], "function_naming")
        self.assertEqual(payload["metrics"], self.metrics)

    def test_report_generator_supports_all_formats_and_text_fallback(self):
        violations = [
            self._build_violation("x.py", 1, 0, "message", ViolationType.CLASS_NAMING),
        ]

        text_report = ReportGenerator(violations).generate("text")
        self.assertIn("Violations report", text_report)
        self.assertNotIn("Analysis completeness", text_report)

        json_report = ReportGenerator(violations).generate("json")
        json_payload = json.loads(json_report)
        self.assertEqual(json_payload["total_violations"], 1)
        self.assertNotIn("metrics", json_payload)

        github_actions_report = ReportGenerator(violations).generate("github-actions")
        self.assertIn("::warning file=x.py,line=1,col=0::message", github_actions_report)
        self.assertNotIn("# files_discovered", github_actions_report)

        unknown_report = ReportGenerator(violations).generate("unknown-format")
        self.assertIn("Violations report", unknown_report)

    def test_report_generator_adds_metrics_to_text_report(self):
        report = ReportGenerator([], self.metrics).generate("text")

        self.assertIn("Analysis completeness", report)
        self.assertIn("files_discovered: 2", report)
        self.assertIn("dependencies_detected: 3", report)

    def test_report_generator_stabilizes_same_location_violation_order(self):
        violations = [
            self._build_violation(
                "app.py",
                10,
                0,
                "Layer 'domain' is not allowed to depend on layer 'payments'.",
                ViolationType.DISALLOWED_DEPENDENCY,
            ),
            self._build_violation(
                "app.py",
                10,
                0,
                "Layer 'application' is not allowed to depend on layer 'payments'.",
                ViolationType.DISALLOWED_DEPENDENCY,
            ),
        ]

        payload = json.loads(ReportGenerator(violations).generate("json"))

        self.assertEqual(
            [violation["message"] for violation in payload["violations"]],
            [
                "Layer 'application' is not allowed to depend on layer 'payments'.",
                "Layer 'domain' is not allowed to depend on layer 'payments'.",
            ],
        )


if __name__ == "__main__":
    unittest.main()
