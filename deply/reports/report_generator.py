from typing import List, Union

from .formats.github_actions_report import GitHubActionsReport
from .formats.json_report import JsonReport
from ..models.violation import Violation
from .formats.text_report import TextReport


class ReportGenerator:
    def __init__(self, violations: List[Violation]):
        self.violations = violations

    def generate(self, format: str) -> str:
        reporter: Union[TextReport, JsonReport, GitHubActionsReport]
        if format == "text":
            reporter = TextReport(self.violations)
        elif format == "json":
            reporter = JsonReport(self.violations)
        elif format == 'github-actions':
            reporter = GitHubActionsReport(self.violations)
        else:
            reporter = TextReport(self.violations)

        return reporter.generate()
