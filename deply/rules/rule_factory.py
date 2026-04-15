from typing import Dict, Any, List, Optional
from .base_rule import BaseRule
from .dependency_rule import DependencyRule
from .class_naming_rule import ClassNamingRule
from .function_naming_rule import FunctionNamingRule
from .class_decorator_rule import ClassDecoratorUsageRule
from .function_decorator_rule import FunctionDecoratorUsageRule
from .inheritance_rule import InheritanceRule
from .bool_rule import BoolRule


class RuleFactory:
    @staticmethod
    def create_sub_rules(rule_configs: List[Dict[str, Any]], layer_name: str) -> List[BaseRule]:
        rules: List[BaseRule] = []
        for rule_config in rule_configs:
            rule = RuleFactory._create_rule_from_config(layer_name, rule_config)
            if rule is not None:
                rules.append(rule)
        return rules

    @staticmethod
    def create_rules(ruleset: Dict[str, Any]) -> List[BaseRule]:
        rules: List[BaseRule] = []
        for layer_name, layer_rules in ruleset.items():
            disallowed = layer_rules.get("disallow_layer_dependencies")
            if disallowed:
                rules.append(DependencyRule(layer_name, disallowed))

            rules.extend(
                RuleFactory._collect_rules_for_key(layer_name, layer_rules, "enforce_class_naming")
            )
            rules.extend(
                RuleFactory._collect_rules_for_key(layer_name, layer_rules, "enforce_function_naming")
            )
            rules.extend(
                RuleFactory._collect_rules_for_key(layer_name, layer_rules, "enforce_class_decorator_usage")
            )
            rules.extend(
                RuleFactory._collect_rules_for_key(layer_name, layer_rules, "enforce_function_decorator_usage")
            )
            rules.extend(
                RuleFactory._collect_rules_for_key(layer_name, layer_rules, "enforce_inheritance")
            )

        return rules

    @staticmethod
    def _collect_rules_for_key(layer_name: str, layer_rules: Dict[str, Any], key: str) -> List[BaseRule]:
        if key not in layer_rules:
            return []
        configs = layer_rules[key]
        collected: List[BaseRule] = []
        for rule_config in configs:
            rule = RuleFactory._create_rule_from_config(layer_name, rule_config)
            if rule is not None:
                collected.append(rule)
        return collected

    @staticmethod
    def _create_rule_from_config(layer_name: str, rule_config: Dict[str, Any]) -> Optional[BaseRule]:
        rule_type = rule_config.get("type")
        if rule_type == "class_name_regex":
            regex = rule_config.get("class_name_regex", "")
            return ClassNamingRule(layer_name, regex)
        if rule_type == "function_name_regex":
            regex = rule_config.get("function_name_regex", "")
            return FunctionNamingRule(layer_name, regex)
        if rule_type == "function_decorator_name_regex":
            regex = rule_config.get("decorator_name_regex", "")
            return FunctionDecoratorUsageRule(layer_name, regex)
        if rule_type == "class_decorator_name_regex":
            regex = rule_config.get("decorator_name_regex", "")
            return ClassDecoratorUsageRule(layer_name, regex)
        if rule_type == "class_inherits":
            base_class = rule_config.get("base_class", "")
            return InheritanceRule(layer_name, base_class)
        if rule_type == "bool":
            return BoolRule(layer_name, rule_config)
        return None
