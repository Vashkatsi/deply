from typing import Optional
from ..models.dependency import Dependency
from ..models.violation import Violation
from ..models.code_element import CodeElement


class BaseRule:
    checks_external_imports = False

    def check(
            self,
            source_layer: str,
            target_layer: str,
            dependency: Dependency
    ) -> Optional[Violation]:
        return None

    # New method for element-based checks
    def check_element(
            self,
            layer_name: str,
            element: CodeElement
    ) -> Optional[Violation]:
        return None

    def check_external_import(
            self,
            layer_name: str,
            element: CodeElement,
            module_name: str,
            line: int,
            column: int
    ) -> Optional[Violation]:
        return None
