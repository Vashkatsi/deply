import re
from pathlib import Path
from typing import Any, Dict, List, Set

from deply.collectors.base_collector import BaseCollector


class ConfigValidator:
    TOP_LEVEL_KEYS = {"paths", "exclude_files", "layers", "ruleset"}
    COLLECTOR_TYPES = {
        "file_regex",
        "class_inherits",
        "class_name_regex",
        "function_name_regex",
        "directory",
        "decorator_usage",
        "bool",
        "custom",
    }
    RULE_KEYS = {
        "disallow_layer_dependencies",
        "disallow_external_imports",
        "enforce_class_naming",
        "enforce_function_naming",
        "enforce_class_decorator_usage",
        "enforce_function_decorator_usage",
        "enforce_inheritance",
    }
    RULE_TYPES = {
        "class_name_regex",
        "function_name_regex",
        "class_decorator_name_regex",
        "function_decorator_name_regex",
        "class_inherits",
        "bool",
    }

    def __init__(self, config_path: Path):
        self.config_path = config_path

    def validate(self, config: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        if not isinstance(config, dict):
            return ["root: must be a mapping"]

        self._validate_known_keys(config, "", self.TOP_LEVEL_KEYS, errors)  # pragma: no mutate
        self._validate_paths(config.get("paths"), errors)
        self._validate_exclude_files(config.get("exclude_files"), errors)

        layer_names = self._validate_layers(config.get("layers"), errors)
        self._validate_ruleset(config.get("ruleset"), layer_names, errors)
        return errors

    def _validate_known_keys(self, config: Dict[str, Any], path: str, known_keys: Set[str], errors: List[str]) -> None:
        for key in config:
            if key not in known_keys:
                errors.append(f"{self._join(path, key)}: unknown key")

    def _validate_paths(self, paths: Any, errors: List[str]) -> None:
        if not self._is_string_list(paths):
            errors.append("paths: must be a non-empty list of strings")
            return

        for index, path in enumerate(paths):
            if not Path(path).exists():
                errors.append(f"paths[{index}]: path does not exist: {path}")

    def _validate_exclude_files(self, exclude_files: Any, errors: List[str]) -> None:
        if not isinstance(exclude_files, list) or not all(isinstance(pattern, str) for pattern in exclude_files):
            errors.append("exclude_files: must be a list of strings")
            return

        for index, pattern in enumerate(exclude_files):
            self._validate_regex(pattern, f"exclude_files[{index}]", errors)

    def _validate_layers(self, layers: Any, errors: List[str]) -> Set[str]:
        if not isinstance(layers, list):
            errors.append("layers: must be a non-empty list")
            return set()
        if not layers:
            errors.append("layers: must contain at least one layer")
            return set()

        layer_names: Set[str] = set()
        for index, layer_config in enumerate(layers):
            layer_path = f"layers[{index}]"
            if not isinstance(layer_config, dict):
                errors.append(f"{layer_path}: must be a mapping")
                continue

            layer_name = layer_config.get("name")
            if not isinstance(layer_name, str) or not layer_name:
                errors.append(f"{layer_path}.name: required")
            elif layer_name in layer_names:
                errors.append(f"{layer_path}.name: duplicate layer name: {layer_name}")
            else:
                layer_names.add(layer_name)

            collectors = layer_config.get("collectors")
            if not isinstance(collectors, list):
                errors.append(f"{layer_path}.collectors: must be a non-empty list")
                continue
            if not collectors:
                errors.append(f"{layer_path}.collectors: must contain at least one collector")
                continue

            for collector_index, collector_config in enumerate(collectors):
                self._validate_collector(
                    collector_config,
                    f"{layer_path}.collectors[{collector_index}]",
                    errors,
                )

        return layer_names

    def _validate_collector(self, collector_config: Any, path: str, errors: List[str]) -> None:
        if not isinstance(collector_config, dict):
            errors.append(f"{path}: must be a mapping")
            return

        collector_type = collector_config.get("type")
        if not isinstance(collector_type, str) or not collector_type:
            errors.append(f"{path}.type: required")
            return
        if collector_type not in self.COLLECTOR_TYPES:
            errors.append(f"{path}.type: unknown collector type: {collector_type}")
            return

        if collector_type == "file_regex":
            self._validate_required_regex(collector_config, "regex", path, errors)
        elif collector_type == "class_inherits":
            self._validate_required_string(collector_config, "base_class", path, errors)
        elif collector_type == "class_name_regex":
            self._validate_required_regex(collector_config, "class_name_regex", path, errors)
        elif collector_type == "function_name_regex":
            self._validate_required_regex(collector_config, "function_name_regex", path, errors)
        elif collector_type == "directory":
            self._validate_required_string_list(collector_config, "directories", path, errors)
        elif collector_type == "decorator_usage":
            self._validate_decorator_collector(collector_config, path, errors)
        elif collector_type == "bool":
            self._validate_bool_group(collector_config, path, self._validate_collector, errors)
        elif collector_type == "custom":
            self._validate_custom_collector(collector_config, path, errors)

        exclude_files_regex = collector_config.get("exclude_files_regex")
        if isinstance(exclude_files_regex, str) and exclude_files_regex:
            self._validate_regex(exclude_files_regex, f"{path}.exclude_files_regex", errors)
        elif exclude_files_regex is not None:
            errors.append(f"{path}.exclude_files_regex: must be a string")

    def _validate_decorator_collector(self, collector_config: Dict[str, Any], path: str, errors: List[str]) -> None:
        decorator_name = collector_config.get("decorator_name")
        decorator_regex = collector_config.get("decorator_regex")
        if not decorator_name and not decorator_regex:
            errors.append(f"{path}: decorator_name or decorator_regex required")
            return
        if decorator_name is not None and not isinstance(decorator_name, str):
            errors.append(f"{path}.decorator_name: must be a string")
        if decorator_regex is not None:
            if isinstance(decorator_regex, str):
                self._validate_regex(decorator_regex, f"{path}.decorator_regex", errors)
            else:
                errors.append(f"{path}.decorator_regex: must be a string")

    def _validate_custom_collector(self, collector_config: Dict[str, Any], path: str, errors: List[str]) -> None:
        class_path = collector_config.get("class")
        if not isinstance(class_path, str) or not class_path:
            errors.append(f"{path}.class: required")
            return

        try:
            module_name, class_name = class_path.rsplit(".", 1)
        except ValueError:
            errors.append(f"{path}.class: invalid class path format: {class_path}")
            return

        try:
            module = __import__(module_name, fromlist=[class_name])
        except ImportError as exception:
            errors.append(f"{path}.class: failed to import module '{module_name}': {exception}")
            return

        collector_class = getattr(module, class_name, None)
        if collector_class is None:
            errors.append(f"{path}.class: class '{class_name}' not found in {module_name}")
            return
        if not isinstance(collector_class, type) or not issubclass(collector_class, BaseCollector):
            errors.append(f"{path}.class: class '{class_name}' must inherit from BaseCollector")

    def _validate_ruleset(self, ruleset: Any, layer_names: Set[str], errors: List[str]) -> None:
        if not isinstance(ruleset, dict):
            errors.append("ruleset: must be a mapping")
            return

        for layer_name, layer_rules in ruleset.items():
            layer_path = f"ruleset.{layer_name}"
            if not isinstance(layer_name, str) or not layer_name:
                errors.append("ruleset: layer names must be non-empty strings")
                continue
            if layer_name not in layer_names:
                errors.append(f"{layer_path}: unknown layer: {layer_name}")
            if not isinstance(layer_rules, dict):
                errors.append(f"{layer_path}: must be a mapping")
                continue

            for rule_key, rule_config in layer_rules.items():
                if rule_key not in self.RULE_KEYS:
                    errors.append(f"{layer_path}.{rule_key}: unknown rule key")
                    continue
                if rule_key == "disallow_layer_dependencies":
                    self._validate_layer_references(rule_config, f"{layer_path}.{rule_key}", layer_names, errors)
                elif rule_key == "disallow_external_imports":
                    self._validate_string_list(rule_config, f"{layer_path}.{rule_key}", errors)
                else:
                    self._validate_rule_list(rule_config, f"{layer_path}.{rule_key}", errors)

    def _validate_rule_list(self, rule_configs: Any, path: str, errors: List[str]) -> None:
        if not isinstance(rule_configs, list):
            errors.append(f"{path}: must be a list")
            return

        for index, rule_config in enumerate(rule_configs):
            self._validate_rule(rule_config, f"{path}[{index}]", errors)

    def _validate_rule(self, rule_config: Any, path: str, errors: List[str]) -> None:
        if not isinstance(rule_config, dict):
            errors.append(f"{path}: must be a mapping")
            return

        rule_type = rule_config.get("type")
        if not isinstance(rule_type, str) or not rule_type:
            errors.append(f"{path}.type: required")
            return
        if rule_type not in self.RULE_TYPES:
            errors.append(f"{path}.type: unknown rule type: {rule_type}")
            return

        if rule_type == "class_name_regex":
            self._validate_required_regex(rule_config, "class_name_regex", path, errors)
        elif rule_type == "function_name_regex":
            self._validate_required_regex(rule_config, "function_name_regex", path, errors)
        elif rule_type in {"class_decorator_name_regex", "function_decorator_name_regex"}:
            self._validate_required_regex(rule_config, "decorator_name_regex", path, errors)
        elif rule_type == "class_inherits":
            self._validate_required_string(rule_config, "base_class", path, errors)
        elif rule_type == "bool":
            self._validate_bool_group(rule_config, path, self._validate_rule, errors)

    def _validate_layer_references(self, values: Any, path: str, layer_names: Set[str], errors: List[str]) -> None:
        if not self._validate_string_list(values, path, errors):
            return

        for index, layer_name in enumerate(values):
            if layer_name not in layer_names:
                errors.append(f"{path}[{index}]: unknown layer: {layer_name}")

    def _validate_bool_group(self, config: Dict[str, Any], path: str, validator: Any, errors: List[str]) -> None:
        has_collectors = False  # pragma: no mutate
        for key in ("must", "any_of", "must_not"):
            values = config.get(key, [])
            if not isinstance(values, list):
                errors.append(f"{path}.{key}: must be a list")
                continue
            if values:
                has_collectors = True
            for index, value in enumerate(values):
                validator(value, f"{path}.{key}[{index}]", errors)

        if not has_collectors:
            errors.append(f"{path}: one of must, any_of, or must_not must contain collectors")

    def _validate_required_regex(
            self,
            config: Dict[str, Any],
            key: str,
            path: str,
            errors: List[str],
    ) -> None:
        value = config.get(key)
        if not isinstance(value, str) or not value:
            errors.append(f"{path}.{key}: required")
            return
        self._validate_regex(value, f"{path}.{key}", errors)

    def _validate_required_string(
            self,
            config: Dict[str, Any],
            key: str,
            path: str,
            errors: List[str],
    ) -> None:
        value = config.get(key)
        if not isinstance(value, str) or not value:
            errors.append(f"{path}.{key}: required")

    def _validate_required_string_list(
            self,
            config: Dict[str, Any],
            key: str,
            path: str,
            errors: List[str],
    ) -> None:
        value = config.get(key)
        if not self._is_string_list(value):
            errors.append(f"{path}.{key}: must be a non-empty list of strings")

    def _validate_string_list(self, values: Any, path: str, errors: List[str]) -> bool:
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            errors.append(f"{path}: must be a list of strings")
            return False
        return True

    def _validate_regex(self, pattern: str, path: str, errors: List[str]) -> None:
        try:
            re.compile(pattern)
        except re.error as exception:
            errors.append(f"{path}: invalid regex: {exception}")

    def _is_string_list(self, values: Any) -> bool:
        return isinstance(values, list) and bool(values) and all(isinstance(value, str) for value in values)

    def _join(self, path: str, key: str) -> str:
        if not path:
            return key
        return f"{path}.{key}"
