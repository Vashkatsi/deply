import json
from pathlib import Path
from typing import Any, Dict, List, Set

from deply.models.code_element import CodeElement
from deply.models.dependency import Dependency
from deply.models.violation import Violation
from deply.models.violation_identity import ViolationSerializer
from deply.reports.report_generator import ReportGenerator
from deply.rules.base_rule import BaseRule


class ContextReport:
    def __init__(
            self, file: Path, file_status: str, memberships: Dict[CodeElement, Set[str]],
            dependencies: Set[Dependency], rules: List[BaseRule], violations: List[Violation],
            *, root: Path, metrics: Dict[str, int], errors: List[str],
    ):
        self.file = file.resolve()
        self.file_status = file_status
        self.memberships = memberships
        self.dependencies = dependencies
        self.rules = rules
        self.violations = violations
        self.serializer = ViolationSerializer(root)
        self.metrics = metrics
        self.errors = errors

    def _element(self, element: CodeElement) -> Dict[str, Any]:
        return dict(self.serializer.element_identity(element), line=element.line, column=element.column,
                    layers=sorted(self.memberships.get(element, set())))

    def generate(self) -> str:
        elements = [self._element(element) for element in self.memberships if element.file.resolve() == self.file]
        layers = {layer for element in elements for layer in element["layers"]}
        rules = {
            rule.rule_id: rule.definition for rule in self.rules
            if rule.definition is not None and (
                rule.definition["source_layer"] in layers
                or (rule.definition["kind"] == "disallow_layer_dependencies"
                    and layers.intersection(rule.definition["configuration"]))
            )
        }
        incoming = []
        outgoing = []
        for dependency in self.dependencies:
            edge = {
                "source": self._element(dependency.code_element),
                "target": self._element(dependency.depends_on_code_element),
                "dependency_type": dependency.dependency_type,
                "line": dependency.line,
                "column": dependency.column,
            }
            if dependency.code_element.file.resolve() == self.file:
                outgoing.append(edge)
            if dependency.depends_on_code_element.file.resolve() == self.file:
                incoming.append(edge)
        related_violations = [
            violation for violation in self.violations
            if violation.file.resolve() == self.file or (
                violation.dependency is not None
                and violation.dependency.depends_on_code_element.file.resolve() == self.file
            )
        ]
        return json.dumps({
            "schema_version": 1,
            "status": "incomplete" if self.errors else "complete",
            "errors": [{"code": "incomplete_analysis", "message": error} for error in sorted(self.errors)],
            "file": self.serializer.relative_path(self.file),
            "file_status": self.file_status,
            "elements": sorted(elements, key=lambda element: (element["line"], element["column"], element["name"], element["type"])),
            "rules": sorted(rules.values(), key=lambda rule: rule["rule_id"]),
            "incoming": sorted(incoming, key=lambda edge: json.dumps(edge, sort_keys=True)),
            "outgoing": sorted(outgoing, key=lambda edge: json.dumps(edge, sort_keys=True)),
            "violations": [self.serializer.serialize(violation)
                           for violation in ReportGenerator(related_violations).violations],
            "metrics": self.metrics,
        }, indent=2)
