import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional
from ...models.violation_identity import ViolationSerializer
from ...models.violation import Violation


class JsonReport:
    def __init__(
            self,
            violations: List[Violation],
            metrics: Optional[Dict[str, int]] = None,
            *,
            root: Optional[Path] = None,
            status: str = "complete",
            errors: Optional[List[Dict[str, str]]] = None,
            baseline: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ):
        self.violations = violations
        self.metrics = dict(metrics) if metrics is not None else None
        self.root = (root or Path.cwd()).resolve()
        self.baseline = baseline
        self.status = status
        self.errors = list(errors or [])

    def generate(self) -> str:
        grouped_violations = self._group_violations_by_type()
        serializer = ViolationSerializer(self.root)
        data = {
            "schema_version": 1,
            "status": self.status,
            "errors": self.errors,
            "total_violations": len(self.violations),
            "by_type": {
                v_type: len(v_list) for v_type, v_list in grouped_violations.items()
            },
            "violations": [serializer.serialize(violation) for violation in self.violations],
        }
        if self.baseline is not None:
            data["baseline"] = self.baseline
        if self.metrics is not None:
            data["metrics"] = self.metrics
        return json.dumps(data, indent=2)

    def _group_violations_by_type(self) -> Dict[str, List[Violation]]:
        grouped = defaultdict(list)
        for violation in self.violations:
            grouped[violation.violation_type.code].append(violation)
        return dict(grouped)
