import json
from collections import defaultdict
from typing import Dict, List
from ...models.violation import Violation


class JsonReport:
    def __init__(self, violations: List[Violation]):
        self.violations = violations

    def generate(self) -> str:
        grouped_violations = self._group_violations_by_type()

        data = {
            "total_violations": len(self.violations),
            "by_type": {
                v_type: len(v_list) for v_type, v_list in grouped_violations.items()
            },
            "violations": [
                {
                    "file": str(violation.file),
                    "element_name": violation.element_name,
                    "element_type": violation.element_type,
                    "line": violation.line,
                    "column": violation.column,
                    "message": violation.message,
                    "violation_type": violation.violation_type.code,
                }
                for violation in self.violations
            ],
        }

        return json.dumps(data, indent=2)

    def _group_violations_by_type(self) -> Dict[str, List[Violation]]:
        grouped = defaultdict(list)
        for violation in self.violations:
            grouped[violation.violation_type.code].append(violation)
        return dict(grouped)
