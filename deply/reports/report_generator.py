from typing import Dict, List, Optional, Union

from .formats.github_actions_report import GitHubActionsReport
from .formats.json_report import JsonReport
from .formats.sarif_report import SarifReport
from ..models.violation import Violation
from .formats.text_report import TextReport


class ReportGenerator:
    def __init__(
            self,
            violations: List[Violation],
            metrics: Optional[Dict[str, int]] = None,
    ):
        self.violations = sorted(
            violations,
            key=lambda violation: (
                violation.violation_type.code,
                str(violation.file),
                violation.line,
                violation.column,
                violation.message,
            ),
        )
        self.metrics = dict(metrics) if metrics is not None else None

    def generate(self, format: str) -> str:
        reporter: Union[TextReport, JsonReport, GitHubActionsReport, SarifReport]
        if format == "text":
            reporter = TextReport(self.violations, self.metrics)
        elif format == "json":
            reporter = JsonReport(self.violations, self.metrics)
        elif format == 'github-actions':
            reporter = GitHubActionsReport(self.violations, self.metrics)
        elif format == "sarif":
            reporter = SarifReport(self.violations, self.metrics)
        else:
            reporter = TextReport(self.violations, self.metrics)

        return reporter.generate()
