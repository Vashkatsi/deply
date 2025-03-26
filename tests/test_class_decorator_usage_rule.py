import unittest
from pathlib import Path

from deply.models.violation import Violation
from deply.models.violation_types import ViolationType
from deply.rules.class_decorator_rule import ClassDecoratorUsageRule


class DummyCodeElement:
    def __init__(self, file: Path, name: str, element_type: str, line: int, column: int, decorators=None):
        self.file = file
        self.name = name
        self.element_type = element_type
        self.line = line
        self.column = column
        self.decorators = decorators if decorators is not None else []

    def __hash__(self):
        return hash((self.file, self.name, self.line, self.column))

    def __eq__(self, other):
        if not isinstance(other, DummyCodeElement):
            return False
        return (
                self.file == other.file and
                self.name == other.name and
                self.element_type == other.element_type and
                self.line == other.line and
                self.column == other.column
        )


class TestClassDecoratorUsageRule(unittest.TestCase):
    def setUp(self):
        self.layer_name = "test_layer"
        self.decorator_regex = r'^@my_decorator$'
        self.rule = ClassDecoratorUsageRule(self.layer_name, self.decorator_regex)
        self.file_path = Path("dummy_file.py")
        self.line = 10
        self.column = 0

    def test_rule_does_not_apply_wrong_layer(self):
        element = DummyCodeElement(
            file=self.file_path,
            name="TestClass",
            element_type="class",
            line=self.line,
            column=self.column,
            decorators=["@not_my_decorator"]
        )
        result = self.rule.check_element("other_layer", element)
        self.assertIsNone(result)

    def test_rule_does_not_apply_wrong_element_type(self):
        element = DummyCodeElement(
            file=self.file_path,
            name="TestFunction",
            element_type="function",
            line=self.line,
            column=self.column,
            decorators=["@my_decorator"]
        )
        result = self.rule.check_element(self.layer_name, element)
        self.assertIsNone(result)

    def test_rule_passes_when_decorator_matches(self):
        element = DummyCodeElement(
            file=self.file_path,
            name="TestClass",
            element_type="class",
            line=self.line,
            column=self.column,
            decorators=["@my_decorator", "@other_decorator"]
        )
        result = self.rule.check_element(self.layer_name, element)
        self.assertIsNone(result)

    def test_rule_returns_violation_when_no_decorator_matches(self):
        element = DummyCodeElement(
            file=self.file_path,
            name="TestClass",
            element_type="class",
            line=self.line,
            column=self.column,
            decorators=["@other_decorator"]
        )
        result = self.rule.check_element(self.layer_name, element)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, Violation)
        expected_message = (
            f"Class '{element.name}' must have a decorator matching '{self.decorator_regex}'."
        )
        self.assertEqual(result.message, expected_message)
        self.assertEqual(result.violation_type, ViolationType.CLASS_DECORATOR_USAGE)
        self.assertEqual(result.file, self.file_path)
        self.assertEqual(result.line, self.line)
        self.assertEqual(result.column, self.column)

    def test_rule_returns_violation_when_no_decorators(self):
        element = DummyCodeElement(
            file=self.file_path,
            name="TestClass",
            element_type="class",
            line=self.line,
            column=self.column,
            decorators=[]
        )
        result = self.rule.check_element(self.layer_name, element)
        self.assertIsNotNone(result)
        expected_message = (
            f"Class '{element.name}' must have a decorator matching '{self.decorator_regex}'."
        )
        self.assertEqual(result.message, expected_message)


if __name__ == '__main__':
    unittest.main()
