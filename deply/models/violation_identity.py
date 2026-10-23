import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict

from .code_element import CodeElement
from .violation import Violation


class ViolationSerializer:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def relative_path(self, file: Path) -> str:
        resolved_file = file.resolve()
        try:
            return Path(os.path.relpath(resolved_file, self.root)).as_posix()
        except ValueError:
            return resolved_file.as_uri()

    def element_identity(self, element: CodeElement) -> Dict[str, str]:
        return {
            "file": self.relative_path(element.file),
            "name": element.name,
            "type": element.element_type,
        }

    def serialize(self, violation: Violation) -> Dict[str, Any]:
        dependency = violation.dependency
        source = self.element_identity(dependency.code_element) if dependency else {
            "file": self.relative_path(violation.file),
            "name": "<module>" if violation.external_import else violation.element_name,
            "type": "module" if violation.external_import else violation.element_type,
        }
        target = self.element_identity(dependency.depends_on_code_element) if dependency else None
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
        fingerprint = relationship_fingerprint(identity)
        return dict(violation.to_dict(), **identity, fingerprint=fingerprint)


def relationship_fingerprint(identity: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
