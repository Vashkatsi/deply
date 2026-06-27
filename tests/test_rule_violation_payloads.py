import unittest
from pathlib import Path

from deply.models.code_element import CodeElement
from deply.models.dependency import Dependency
from deply.models.violation import Violation
from deply.models.violation_types import ViolationType
from deply.rules.bool_rule import BoolRule
from deply.rules.class_decorator_rule import ClassDecoratorUsageRule
from deply.rules.class_naming_rule import ClassNamingRule
from deply.rules.dependency_rule import DependencyRule
from deply.rules.external_import_rule import ExternalImportRule
from deply.rules.function_decorator_rule import FunctionDecoratorUsageRule
from deply.rules.function_naming_rule import FunctionNamingRule
from deply.rules.inheritance_rule import InheritanceRule


class TestRuleViolationPayloads(unittest.TestCase):
    def _build_element(self, name: str, element_type: str, line: int = 7, column: int = 2) -> CodeElement:
        return CodeElement(
            file=Path("domain/service.py"),
            name=name,
            element_type=element_type,
            line=line,
            column=column,
        )

    def assert_payload(
        self,
        violation: Violation,
        element: CodeElement,
        violation_type: ViolationType,
        line: int = 7,
        column: int = 2,
    ):
        self.assertEqual(violation.file, element.file)
        self.assertEqual(violation.element_name, element.name)
        self.assertEqual(violation.element_type, element.element_type)
        self.assertEqual(violation.line, line)
        self.assertEqual(violation.column, column)
        self.assertEqual(violation.violation_type, violation_type)

    def test_naming_and_inheritance_rules_preserve_violation_payload(self):
        class_element = self._build_element("domain.bad_class", "class")
        function_element = self._build_element("domain.BadFunction", "function")

        class_violation = ClassNamingRule("domain", r"^Good.*$").check_element("domain", class_element)
        function_violation = FunctionNamingRule("domain", r"^good_.*$").check_element("domain", function_element)
        inheritance_violation = InheritanceRule("domain", "BaseModel").check_element("domain", class_element)

        self.assertIsNotNone(class_violation)
        self.assert_payload(class_violation, class_element, ViolationType.CLASS_NAMING)
        self.assertIsNotNone(function_violation)
        self.assert_payload(function_violation, function_element, ViolationType.FUNCTION_NAMING)
        self.assertEqual(
            function_violation.message,
            "Function 'domain.BadFunction' does not match naming pattern '^good_.*$'.",
        )
        self.assertIsNotNone(inheritance_violation)
        self.assert_payload(inheritance_violation, class_element, ViolationType.INHERITANCE)

    def test_naming_and_inheritance_rules_handle_qualified_names(self):
        class_element = self._build_element("domain.GoodClass", "class")
        function_element = self._build_element("domain.good_function", "function")
        exact_inheritance_element = CodeElement(
            file=Path("domain/model.py"),
            name="User",
            element_type="class",
            line=1,
            column=0,
            inherits=("BaseModel",),
        )
        qualified_inheritance_element = CodeElement(
            file=Path("domain/model.py"),
            name="Admin",
            element_type="class",
            line=5,
            column=0,
            inherits=("framework.BaseModel",),
        )

        self.assertIsNone(ClassNamingRule("domain", r"^GoodClass$").check_element("domain", class_element))
        self.assertIsNone(FunctionNamingRule("domain", r"^good_function$").check_element("domain", function_element))
        self.assertIsNone(InheritanceRule("domain", "BaseModel").check_element("domain", exact_inheritance_element))
        self.assertIsNone(InheritanceRule("domain", "BaseModel").check_element("domain", qualified_inheritance_element))

    def test_rules_do_not_apply_to_wrong_layer_or_element_type(self):
        class_element = self._build_element("bad_class", "class")
        function_element = self._build_element("BadFunction", "function")

        self.assertIsNone(ClassNamingRule("domain", r"^Good.*$").check_element("other", class_element))
        self.assertIsNone(ClassNamingRule("domain", r"^Good.*$").check_element("domain", function_element))
        self.assertIsNone(FunctionNamingRule("domain", r"^good_.*$").check_element("other", function_element))
        self.assertIsNone(FunctionNamingRule("domain", r"^good_.*$").check_element("domain", class_element))
        self.assertIsNone(InheritanceRule("domain", "BaseModel").check_element("other", class_element))
        self.assertIsNone(InheritanceRule("domain", "BaseModel").check_element("domain", function_element))

    def test_dependency_and_external_import_rules_preserve_violation_payload(self):
        source_element = self._build_element("load_user", "function", line=12, column=4)
        target_element = CodeElement(
            file=Path("domain/model.py"),
            name="User",
            element_type="class",
            line=1,
            column=0,
        )
        dependency = Dependency(
            code_element=source_element,
            depends_on_code_element=target_element,
            dependency_type="function_call",
            line=14,
            column=8,
        )

        dependency_violation = DependencyRule("service", ["domain"]).check("service", "domain", dependency)
        external_violation = ExternalImportRule("service", ["requests"]).check_external_import(
            "service",
            source_element,
            "requests.sessions",
            3,
            0,
        )

        self.assertIsNotNone(dependency_violation)
        self.assert_payload(dependency_violation, source_element, ViolationType.DISALLOWED_DEPENDENCY, 14, 8)
        self.assertEqual(dependency_violation.dependency, dependency)
        self.assertIsNotNone(external_violation)
        self.assert_payload(external_violation, source_element, ViolationType.DISALLOWED_EXTERNAL_IMPORT, 3, 0)

    def test_decorator_and_bool_rules_preserve_violation_payload(self):
        function_element = CodeElement(
            file=Path("service.py"),
            name="load_user",
            element_type="function",
            line=5,
            column=4,
            decorators=("plain_decorator",),
        )
        class_element = CodeElement(
            file=Path("service.py"),
            name="Service",
            element_type="class",
            line=9,
            column=0,
            decorators=("plain_decorator",),
        )

        decorator_violation = FunctionDecoratorUsageRule("service", r"^tracked_.*$").check_element(
            "service",
            function_element,
        )
        class_decorator_violation = ClassDecoratorUsageRule("service", r"^entity_.*$").check_element(
            "service",
            class_element,
        )
        bool_violation = BoolRule(
            "service",
            {
                "must_not": [
                    {
                        "type": "function_name_regex",
                        "function_name_regex": "^load_.*$",
                    }
                ]
            },
        ).check_element("service", function_element)

        self.assertIsNotNone(decorator_violation)
        self.assert_payload(decorator_violation, function_element, ViolationType.FUNCTION_DECORATOR_USAGE, 5, 4)
        self.assertIsNotNone(class_decorator_violation)
        self.assert_payload(class_decorator_violation, class_element, ViolationType.CLASS_DECORATOR_USAGE, 9, 0)
        self.assertIsNotNone(bool_violation)
        self.assert_payload(bool_violation, function_element, ViolationType.BOOL_RULE, 5, 4)

    def test_decorator_rules_ignore_wrong_layer_or_element_type_even_without_matching_decorator(self):
        function_element = CodeElement(
            file=Path("service.py"),
            name="load_user",
            element_type="function",
            line=5,
            column=4,
            decorators=("plain_decorator",),
        )
        class_element = CodeElement(
            file=Path("service.py"),
            name="Service",
            element_type="class",
            line=9,
            column=0,
            decorators=("plain_decorator",),
        )

        self.assertIsNone(FunctionDecoratorUsageRule("service", r"^tracked_.*$").check_element("other", function_element))
        self.assertIsNone(FunctionDecoratorUsageRule("service", r"^tracked_.*$").check_element("service", class_element))
        self.assertIsNone(ClassDecoratorUsageRule("service", r"^entity_.*$").check_element("other", class_element))
        self.assertIsNone(ClassDecoratorUsageRule("service", r"^entity_.*$").check_element("service", function_element))


if __name__ == "__main__":
    unittest.main()
