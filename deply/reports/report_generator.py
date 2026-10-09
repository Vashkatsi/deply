from pathlib import Path
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
            *,
            root: Optional[Path] = None,
            status: str = "complete",
            errors: Optional[List[Dict[str, str]]] = None,
    ):
        self.violations = sorted(
            violations,
            key=lambda violation: (
                violation.violation_type.code,
                str(violation.file),
                violation.line,
                violation.column,
                violation.message,
                violation.element_name,
                violation.element_type,
                violation.rule_id or "",
                violation.source_layer or "",
                violation.target_layer or "",
                str(violation.dependency.depends_on_code_element.file) if violation.dependency else "",
                violation.dependency.depends_on_code_element.name if violation.dependency else "",
                violation.dependency.depends_on_code_element.element_type if violation.dependency else "",
                violation.dependency.dependency_type if violation.dependency else "",
                violation.external_import or "",
            ),
        )
        self.metrics = dict(metrics) if metrics is not None else None
        self.root = root
        self.status = status
        self.errors = errors

    def generate(self, format: str) -> str:
        reporter: Union[TextReport, JsonReport, GitHubActionsReport, SarifReport]
        if format == "text":
            reporter = TextReport(self.violations, self.metrics)
        elif format == "json":
            reporter = JsonReport(self.violations, self.metrics, root=self.root, status=self.status, errors=self.errors)
        elif format == 'github-actions':
            reporter = GitHubActionsReport(self.violations, self.metrics)
        elif format == "sarif":
            reporter = SarifReport(self.violations, self.metrics)
        else:
            reporter = TextReport(self.violations, self.metrics)

        return reporter.generate()
