from collections import defaultdict
from typing import Dict, List, Optional

from ...models.violation import Violation


class GitHubActionsReport:
    def __init__(
            self,
            violations: List[Violation],
            metrics: Optional[Dict[str, int]] = None,
    ):
        self.violations = violations
        self.metrics = dict(metrics) if metrics is not None else None

    def generate(self) -> str:
        grouped_violations = self._group_violations_by_type()
        lines = []
        for violation_type, type_violations in grouped_violations.items():
            sorted_violations = sorted(type_violations, key=lambda v: (v.file, v.line, v.column))
            for violation in sorted_violations:
                # Using warning format. Could be "::error" or "::warning"
                # Format: ::warning file=<file>,line=<line>,col=<column>::<message>
                lines.append(
                    f"::warning file={violation.file},line={violation.line},col={violation.column}::{violation.message}"
                )

        # Add summary at the end as a comment
        total_count = len(self.violations)
        for violation_type, type_violations in grouped_violations.items():
            lines.append(f"# {violation_type}: {len(type_violations)}")
        lines.append(f"# Total Violations: {total_count}")
        if self.metrics is not None:
            lines.extend(f"# {name}: {value}" for name, value in self.metrics.items())

        return "\n".join(lines)

    def _group_violations_by_type(self) -> Dict[str, List[Violation]]:
        grouped = defaultdict(list)
        for violation in self.violations:
            grouped[violation.violation_type.display_name].append(violation)
        return dict(grouped)
