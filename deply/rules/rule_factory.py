import hashlib
import json

from typing import Dict, Any, List, Optional
from .base_rule import BaseRule
from .dependency_rule import DependencyRule
from .class_naming_rule import ClassNamingRule
from .function_naming_rule import FunctionNamingRule
from .class_decorator_rule import ClassDecoratorUsageRule
from .function_decorator_rule import FunctionDecoratorUsageRule
from .inheritance_rule import InheritanceRule
from .bool_rule import BoolRule
from .external_import_rule import ExternalImportRule


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
                rules.append(RuleFactory._identify_rule(
                    DependencyRule(layer_name, disallowed), layer_name,
                    "disallow_layer_dependencies", sorted(set(disallowed)),
                ))

            disallowed_external_imports = layer_rules.get("disallow_external_imports")
            if disallowed_external_imports:
                rules.append(RuleFactory._identify_rule(
                    ExternalImportRule(layer_name, disallowed_external_imports), layer_name,
                    "disallow_external_imports",
                    sorted({name.split(".")[0] for name in disallowed_external_imports}),
                ))

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
                collected.append(RuleFactory._identify_rule(rule, layer_name, key, RuleFactory._effective_rule_config(rule_config)))
        return collected

    @staticmethod
    def _effective_rule_config(config: Dict[str, Any]) -> Dict[str, Any]:
        rule_type = config.get("type", "")
        if rule_type == "bool":
            return dict(type=rule_type, **{
                key: [RuleFactory._effective_rule_config(rule) for rule in config.get(key, [])]
                for key in ("must", "any_of", "must_not")
            })
        parameter = {
            "class_name_regex": "class_name_regex",
            "function_name_regex": "function_name_regex",
            "class_decorator_name_regex": "decorator_name_regex",
            "function_decorator_name_regex": "decorator_name_regex",
            "class_inherits": "base_class",
        }.get(rule_type)
        if parameter is None:
            return {"type": rule_type}
        return {"type": rule_type, parameter: config.get(parameter, "")}

    @staticmethod
    def _identify_rule(rule: BaseRule, layer_name: str, key: str, config: Any) -> BaseRule:
        configuration = json.dumps(config, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(configuration.encode("utf-8")).hexdigest()
        rule.rule_id = f"{layer_name}:{key}:{digest}"
        return rule

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
