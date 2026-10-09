from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from deply.models.dependency import Dependency
from deply.models.violation_types import ViolationType


@dataclass(frozen=True)
class Violation:
    file: Path
    element_name: str
    element_type: str  # 'class', 'function', or 'variable'
    line: int
    column: int
    message: str
    violation_type: ViolationType
    dependency: Optional[Dependency] = None
    rule_id: Optional[str] = None
    source_layer: Optional[str] = None
    target_layer: Optional[str] = None
    external_import: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "file": str(self.file),
            "element_name": self.element_name,
            "element_type": self.element_type,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "violation_type": self.violation_type.code,
        }
