from collections import defaultdict
from typing import Dict, List

from ...models.violation import Violation


class SummaryTable:
    COL1_WIDTH = 30
    COL2_WIDTH = 5

    def __init__(self, summary_data: Dict[str, str]):
        self.summary_data = summary_data

    def generate(self) -> str:
        lines = []
        lines.append(self._table_header())
        # "Report" in column 1, blank in column 2
        lines.append(self._table_row("Violations report", ""))
        lines.append(self._table_header())

        for key, value in self.summary_data.items():
            lines.append(self._table_row(key, str(value)))

        lines.append(self._table_header())
        return "\n".join(lines)

    def _table_header(self) -> str:
        return (
                " " + "-" * self.COL1_WIDTH + " " +
                "-" * self.COL2_WIDTH + " "
        )

    def _table_row(self, col1: str, col2: str) -> str:
        col1 = col1[:self.COL1_WIDTH]
        col2 = col2[:self.COL2_WIDTH]
        return (
                " "
                + col1.ljust(self.COL1_WIDTH)
                + " "
                + col2.ljust(self.COL2_WIDTH)
                + " "
        )


class TextReport:
    def __init__(self, violations: List[Violation]):
        self.violations = violations

    def generate(self) -> str:
        grouped_violations = self._group_violations_by_type()
        lines = []

        # 1) Print violations grouped by their display name
        for violation_type, type_violations in grouped_violations.items():
            lines.append(violation_type)
            sorted_violations = sorted(type_violations, key=lambda v: (v.file, v.line, v.column))
            for violation in sorted_violations:
                lines.append(f"{violation.file}:{violation.line}:{violation.column} - {violation.message}")
            lines.append("")

        # 2) Build a dict of summary data
        summary_data = {}
        for violation_type, type_violations in grouped_violations.items():
            summary_data[violation_type] = str(len(type_violations))

        # Add a total
        total_count = len(self.violations)
        summary_data[""] = ""
        summary_data["Total Violations"] = str(total_count)

        # 3) Generate the summary table
        summary_table = SummaryTable(summary_data)
        lines.append(summary_table.generate())

        return "\n".join(lines)

    def _group_violations_by_type(self) -> Dict[str, List[Violation]]:
        grouped = defaultdict(list)
        for violation in self.violations:
            grouped[violation.violation_type.display_name].append(violation)
        return dict(grouped)
