import unittest
from pathlib import Path
from typing import Tuple

from deply.models.code_element import CodeElement
from deply.models.violation import Violation
from deply.models.violation_types import ViolationType
from deply.rules.function_decorator_rule import FunctionDecoratorUsageRule


class TestFunctionDecoratorUsageRule(unittest.TestCase):
    def setUp(self):
        self.layer_name = "service_layer"
        self.decorator_pattern = r"^tracked_.*$"
        self.rule = FunctionDecoratorUsageRule(self.layer_name, self.decorator_pattern)

    def _build_element(self, name: str, element_type: str, decorators: Tuple[str, ...]) -> CodeElement:
        return CodeElement(
            file=Path("module.py"),
            name=name,
            element_type=element_type,
            line=8,
            column=2,
            decorators=decorators,
        )

    def test_wrong_layer_returns_none(self):
        function_element = self._build_element("track_order", "function", ("tracked_operation",))
        self.assertIsNone(self.rule.check_element("another_layer", function_element))

    def test_wrong_element_type_returns_none(self):
        class_element = self._build_element("OrderService", "class", ("tracked_operation",))
        self.assertIsNone(self.rule.check_element(self.layer_name, class_element))

    def test_matching_decorator_returns_none(self):
        function_element = self._build_element("track_order", "function", ("tracked_operation", "other_decorator"))
        self.assertIsNone(self.rule.check_element(self.layer_name, function_element))

    def test_missing_or_non_matching_decorator_returns_violation(self):
        function_without_match = self._build_element("track_order", "function", ("plain_decorator",))

        violation = self.rule.check_element(self.layer_name, function_without_match)

        self.assertIsInstance(violation, Violation)
        self.assertEqual(violation.violation_type, ViolationType.FUNCTION_DECORATOR_USAGE)
        self.assertEqual(
            violation.message,
            "Function 'track_order' must have a decorator matching '^tracked_.*$'.",
        )

        function_without_decorators = self._build_element("track_order", "function", tuple())
        violation_without_decorators = self.rule.check_element(self.layer_name, function_without_decorators)
        self.assertIsNotNone(violation_without_decorators)


if __name__ == "__main__":
    unittest.main()
