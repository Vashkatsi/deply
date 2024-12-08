import re
from typing import Optional
from .base_rule import BaseRule
from ..models.violation import Violation
from ..models.code_element import CodeElement


class FunctionDecoratorUsageRule(BaseRule):
    VIOLATION_TYPE = "function_decorator_usage"

    def __init__(self, layer_name: str, decorator_regex: str):
        self.layer_name = layer_name
        self.decorator_pattern = re.compile(decorator_regex)

    def check_element(self, layer_name: str, element: CodeElement) -> Optional[Violation]:
        if layer_name != self.layer_name or element.element_type != 'function':
            return None
        decorators = getattr(element, 'decorators', [])
        if any(self.decorator_pattern.match(decorator) for decorator in decorators):
            return None
        return Violation(
            file=element.file,
            element_name=element.name,
            element_type=element.element_type,
            line=element.line,
            column=element.column,
            message=(
                f"Function '{element.name}' must have a decorator matching '{self.decorator_pattern.pattern}'."
            ),
            violation_type=self.VIOLATION_TYPE
        )
