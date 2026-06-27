import unittest

from deply.rules.bool_rule import BoolRule
from deply.rules.class_decorator_rule import ClassDecoratorUsageRule
from deply.rules.external_import_rule import ExternalImportRule
from deply.rules.function_decorator_rule import FunctionDecoratorUsageRule
from deply.rules.rule_factory import RuleFactory


class TestRuleFactory(unittest.TestCase):
    def test_create_rule_from_config_for_decorator_rules(self):
        function_decorator_rule = RuleFactory._create_rule_from_config(
            "service_layer",
            {
                "type": "function_decorator_name_regex",
                "decorator_name_regex": r"^track_.*$",
            },
        )
        class_decorator_rule = RuleFactory._create_rule_from_config(
            "service_layer",
            {
                "type": "class_decorator_name_regex",
                "decorator_name_regex": r"^entity_.*$",
            },
        )

        self.assertIsInstance(function_decorator_rule, FunctionDecoratorUsageRule)
        self.assertIsInstance(class_decorator_rule, ClassDecoratorUsageRule)

    def test_create_rules_for_external_imports(self):
        rules = RuleFactory.create_rules(
            {
                "domain": {
                    "disallow_external_imports": ["django", "requests"],
                }
            }
        )

        self.assertEqual(len(rules), 1)
        self.assertIsInstance(rules[0], ExternalImportRule)

    def test_create_rules_for_decorator_rules_preserves_layer_and_pattern(self):
        rules = RuleFactory.create_rules(
            {
                "service_layer": {
                    "enforce_class_decorator_usage": [
                        {
                            "type": "class_decorator_name_regex",
                            "decorator_name_regex": r"^entity_.*$",
                        }
                    ],
                    "enforce_function_decorator_usage": [
                        {
                            "type": "function_decorator_name_regex",
                            "decorator_name_regex": r"^tracked_.*$",
                        }
                    ],
                }
            }
        )

        self.assertEqual(len(rules), 2)
        class_decorator_rule, function_decorator_rule = rules
        self.assertIsInstance(class_decorator_rule, ClassDecoratorUsageRule)
        self.assertEqual(class_decorator_rule.layer_name, "service_layer")
        self.assertEqual(class_decorator_rule.decorator_pattern.pattern, r"^entity_.*$")
        self.assertIsInstance(function_decorator_rule, FunctionDecoratorUsageRule)
        self.assertEqual(function_decorator_rule.layer_name, "service_layer")
        self.assertEqual(function_decorator_rule.decorator_pattern.pattern, r"^tracked_.*$")

    def test_create_rule_from_config_for_bool_and_unknown_type(self):
        bool_rule = RuleFactory._create_rule_from_config(
            "service_layer",
            {
                "type": "bool",
                "must": [],
                "any_of": [],
                "must_not": [],
            },
        )
        unknown_rule = RuleFactory._create_rule_from_config(
            "service_layer",
            {
                "type": "not_supported",
            },
        )

        self.assertIsInstance(bool_rule, BoolRule)
        self.assertIsNone(unknown_rule)


if __name__ == "__main__":
    unittest.main()
