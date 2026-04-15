import json
import unittest
from pathlib import Path

from deply.models.violation import Violation
from deply.models.violation_types import ViolationType
from deply.reports.formats.github_actions_report import GitHubActionsReport
from deply.reports.formats.json_report import JsonReport
from deply.reports.report_generator import ReportGenerator


class TestReports(unittest.TestCase):
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

        report_output = GitHubActionsReport(violations).generate().splitlines()

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

    def test_json_report_generates_expected_payload(self):
        violations = [
            self._build_violation("app.py", 10, 0, "dependency issue", ViolationType.DISALLOWED_DEPENDENCY),
            self._build_violation("app.py", 20, 2, "naming issue", ViolationType.FUNCTION_NAMING),
        ]

        payload = json.loads(JsonReport(violations).generate())

        self.assertEqual(payload["total_violations"], 2)
        self.assertEqual(payload["by_type"]["disallowed_dependency"], 1)
        self.assertEqual(payload["by_type"]["function_naming"], 1)
        self.assertEqual(payload["violations"][0]["file"], "app.py")
        self.assertEqual(payload["violations"][0]["violation_type"], "disallowed_dependency")
        self.assertEqual(payload["violations"][1]["violation_type"], "function_naming")

    def test_report_generator_supports_all_formats_and_text_fallback(self):
        violations = [
            self._build_violation("x.py", 1, 0, "message", ViolationType.CLASS_NAMING),
        ]

        text_report = ReportGenerator(violations).generate("text")
        self.assertIn("Violations report", text_report)

        json_report = ReportGenerator(violations).generate("json")
        self.assertEqual(json.loads(json_report)["total_violations"], 1)

        github_actions_report = ReportGenerator(violations).generate("github-actions")
        self.assertIn("::warning file=x.py,line=1,col=0::message", github_actions_report)

        unknown_report = ReportGenerator(violations).generate("unknown-format")
        self.assertIn("Violations report", unknown_report)


if __name__ == "__main__":
    unittest.main()
