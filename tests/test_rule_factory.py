import unittest

from deply.rules.bool_rule import BoolRule
from deply.rules.class_decorator_rule import ClassDecoratorUsageRule
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
