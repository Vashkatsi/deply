from typing import List, Optional

from deply.models.code_element import CodeElement
from deply.models.violation import Violation
from deply.models.violation_types import ViolationType
from deply.rules.base_rule import BaseRule


class ExternalImportRule(BaseRule):
    VIOLATION_TYPE = ViolationType.DISALLOWED_EXTERNAL_IMPORT
    checks_external_imports = True

    def __init__(self, layer_name: str, disallowed_imports: List[str]):
        self.layer_name = layer_name
        self.disallowed_import_roots = {
            import_name.split(".")[0]
            for import_name in disallowed_imports
            if import_name
        }

    def check_external_import(
            self,
            layer_name: str,
            element: CodeElement,
            module_name: str,
            line: int,
            column: int
    ) -> Optional[Violation]:
        if layer_name != self.layer_name:
            return None

        import_root = module_name.split(".")[0]
        if import_root not in self.disallowed_import_roots:
            return None

        return Violation(
            file=element.file,
            element_name=element.name,
            element_type=element.element_type,
            line=line,
            column=column,
            message=(
                f"Layer '{layer_name}' is not allowed to import external package "
                f"'{import_root}'. Import: {module_name}."
            ),
            violation_type=self.VIOLATION_TYPE,
        )
