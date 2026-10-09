import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional
from ...models.code_element import CodeElement
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
    ):
        self.violations = violations
        self.metrics = dict(metrics) if metrics is not None else None
        self.root = (root or Path.cwd()).resolve()
        self.status = status
        self.errors = list(errors or [])

    def generate(self) -> str:
        grouped_violations = self._group_violations_by_type()
        data = {
            "schema_version": 1,
            "status": self.status,
            "errors": self.errors,
            "total_violations": len(self.violations),
            "by_type": {
                v_type: len(v_list) for v_type, v_list in grouped_violations.items()
            },
            "violations": [self._violation_data(violation) for violation in self.violations],
        }
        if self.metrics is not None:
            data["metrics"] = self.metrics
        return json.dumps(data, indent=2)

    def _relative_path(self, file: Path) -> str:
        resolved_file = file.resolve()
        try:
            return Path(os.path.relpath(resolved_file, self.root)).as_posix()
        except ValueError:
            return resolved_file.as_uri()

    def _element_identity(self, element: CodeElement) -> Dict[str, str]:
        return {
            "file": self._relative_path(element.file),
            "name": element.name,
            "type": element.element_type,
        }

    def _violation_data(self, violation: Violation) -> Dict[str, Any]:
        dependency = violation.dependency
        source = self._element_identity(dependency.code_element) if dependency else {
            "file": self._relative_path(violation.file),
            "name": "<module>" if violation.external_import else violation.element_name,
            "type": "module" if violation.external_import else violation.element_type,
        }
        target = self._element_identity(dependency.depends_on_code_element) if dependency else None
        if violation.external_import:
            target = {"module": violation.external_import, "type": "external_module"}
        identity = {
            "rule_id": violation.rule_id or violation.violation_type.code,
            "source": source,
            "target": target,
            "source_layer": violation.source_layer,
            "target_layer": violation.target_layer,
            "dependency_type": dependency.dependency_type if dependency else None,
        }
        fingerprint = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return dict(violation.to_dict(), **identity, fingerprint=fingerprint)

    def _group_violations_by_type(self) -> Dict[str, List[Violation]]:
        grouped = defaultdict(list)
        for violation in self.violations:
            grouped[violation.violation_type.code].append(violation)
        return dict(grouped)
