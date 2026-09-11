import json
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from deply import __version__
from deply.models.violation import Violation


class SarifReport:
    def __init__(self, violations: List[Violation], metrics: Optional[Dict[str, int]] = None):
        self.violations = violations
        self.metrics = dict(metrics) if metrics is not None else None

    def generate(self) -> str:
        source_root = Path.cwd().resolve()
        violation_types = sorted(
            {violation.violation_type for violation in self.violations},
            key=lambda violation_type: violation_type.code,
        )
        run = {
            "tool": {"driver": {
                "name": "Deply",
                "version": __version__,
                "rules": [
                    {
                        "id": violation_type.code,
                        "shortDescription": {"text": violation_type.display_name},
                        "helpUri": "https://vashkatsi.github.io/deply/doc/rules.html",
                    }
                    for violation_type in violation_types
                ],
            }},
            "originalUriBaseIds": {"%SRCROOT%": {"uri": source_root.as_uri().rstrip("/") + "/"}},
            "results": [self._result(violation, source_root) for violation in self.violations],
        }
        if self.metrics is not None:
            run["properties"] = {"metrics": self.metrics}
        return json.dumps({
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [run],
        }, indent=2)

    @staticmethod
    def _result(violation: Violation, source_root: Path) -> dict:
        file_path = violation.file.resolve()
        try:
            relative_path = file_path.relative_to(source_root)
        except ValueError:
            artifact_location = {"uri": file_path.as_uri()}
        else:
            artifact_location = {"uri": quote(relative_path.as_posix()), "uriBaseId": "%SRCROOT%"}
        physical_location: dict = {"artifactLocation": artifact_location}
        if violation.line > 0:
            physical_location["region"] = {"startLine": violation.line}
        return {
            "ruleId": violation.violation_type.code,
            "level": "warning",
            "message": {"text": violation.message},
            "locations": [{"physicalLocation": physical_location}],
        }
