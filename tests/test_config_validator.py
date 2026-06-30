import sys
import tempfile
import types
import unittest
from pathlib import Path

from deply.collectors.base_collector import BaseCollector
from deply.config_validator import ConfigValidator


class DummyCustomCollector(BaseCollector):
    def __init__(self, config: dict):
        self.config = config

    def match_in_file(self, file_ast, file_path) -> set:
        return set()


class TestConfigValidator(unittest.TestCase):
    def _validate(self, config):
        return ConfigValidator(Path("deply.yaml")).validate(config)

    def test_preserves_config_path(self):
        config_path = Path("custom.yaml")

        validator = ConfigValidator(config_path)

        self.assertEqual(validator.config_path, config_path)

    def test_reports_non_mapping_root(self):
        errors = self._validate([])

        self.assertEqual(errors, ["root: must be a mapping"])

    def test_accepts_valid_configuration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            config = {
                "paths": [str(project_path)],
                "exclude_files": [r".*\.venv/.*"],
                "layers": [
                    {
                        "name": "domain",
                        "collectors": [
                            {
                                "type": "class_name_regex",
                                "class_name_regex": r".*Entity$",
                            }
                        ],
                    },
                    {
                        "name": "app",
                        "collectors": [
                            {
                                "type": "bool",
                                "must": [
                                    {
                                        "type": "directory",
                                        "directories": ["app"],
                                    }
                                ],
                            }
                        ],
                    },
                ],
                "ruleset": {
                    "app": {
                        "disallow_layer_dependencies": ["domain"],
                        "disallow_external_imports": ["django"],
                        "enforce_function_decorator_usage": [
                            {
                                "type": "function_decorator_name_regex",
                                "decorator_name_regex": r"^transactional$",
                            }
                        ],
                    }
                },
            }

            errors = ConfigValidator(project_path / "deply.yaml").validate(config)

        self.assertEqual(errors, [])

    def test_reports_empty_layers(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            config = {
                "paths": [str(project_path)],
                "exclude_files": [],
                "layers": [],
                "ruleset": {},
            }

            errors = self._validate(config)

        self.assertEqual(errors, ["layers: must contain at least one layer"])

    def test_reports_top_level_and_regex_errors(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            config = {
                "paths": [str(project_path)],
                "exclude_files": ["["],
                "layers": [
                    {
                        "name": "domain",
                        "collectors": [
                            {
                                "type": "class_name_regex",
                                "class_name_regex": "[",
                            }
                        ],
                    }
                ],
                "ruleset": {},
                "unexpected": True,
            }

            errors = ConfigValidator(project_path / "deply.yaml").validate(config)

        self.assertIn("unexpected: unknown key", errors)
        self.assertTrue(any(error.startswith("exclude_files[0]: invalid regex") for error in errors))
        self.assertTrue(
            any(error.startswith("layers[0].collectors[0].class_name_regex: invalid regex") for error in errors)
        )

    def test_reports_duplicate_layers_and_unknown_collector(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            config = {
                "paths": [str(project_path)],
                "exclude_files": [],
                "layers": [
                    {
                        "name": "domain",
                        "collectors": [
                            {
                                "type": "unknown",
                            }
                        ],
                    },
                    {
                        "name": "domain",
                        "collectors": [
                            {
                                "type": "file_regex",
                            }
                        ],
                    },
                ],
                "ruleset": {},
            }

            errors = ConfigValidator(project_path / "deply.yaml").validate(config)

        self.assertIn("layers[0].collectors[0].type: unknown collector type: unknown", errors)
        self.assertIn("layers[1].name: duplicate layer name: domain", errors)
        self.assertIn("layers[1].collectors[0].regex: required", errors)

    def test_reports_basic_shape_errors(self):
        config = {
            "paths": ("not-list",),
            "exclude_files": "not-list",
            "layers": [
                "not-mapping",
                {
                    "name": 123,
                    "collectors": "not-list",
                },
                {
                    "name": "empty",
                    "collectors": [],
                },
                {
                    "name": "after_empty",
                    "collectors": [
                        {
                            "type": "unknown",
                        }
                    ],
                },
            ],
            "ruleset": [],
        }

        errors = self._validate(config)

        self.assertIn("paths: must be a non-empty list of strings", errors)
        self.assertIn("exclude_files: must be a list of strings", errors)
        self.assertIn("layers[0]: must be a mapping", errors)
        self.assertIn("layers[1].name: required", errors)
        self.assertIn("layers[1].collectors: must be a non-empty list", errors)
        self.assertIn("layers[2].collectors: must contain at least one collector", errors)
        self.assertIn("layers[3].collectors[0].type: unknown collector type: unknown", errors)
        self.assertIn("ruleset: must be a mapping", errors)

    def test_reports_collector_required_field_errors(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            config = {
                "paths": [str(project_path)],
                "exclude_files": [],
                "layers": [
                    {
                        "name": "domain",
                        "collectors": [
                            {
                                "type": "file_regex",
                            },
                            {
                                "type": "class_inherits",
                            },
                            {
                                "type": "function_name_regex",
                            },
                            {
                                "type": "directory",
                            },
                            {
                                "type": "custom",
                            },
                            {
                                "type": "class_name_regex",
                                "class_name_regex": r".*Entity$",
                                "exclude_files_regex": "[",
                            },
                            {
                                "type": 123,
                            },
                            {
                                "type": "function_name_regex",
                                "function_name_regex": ".*",
                                "exclude_files_regex": 123,
                            },
                        ],
                    }
                ],
                "ruleset": {},
            }

            errors = self._validate(config)

        self.assertIn("layers[0].collectors[0].regex: required", errors)
        self.assertIn("layers[0].collectors[1].base_class: required", errors)
        self.assertIn("layers[0].collectors[2].function_name_regex: required", errors)
        self.assertIn("layers[0].collectors[3].directories: must be a non-empty list of strings", errors)
        self.assertIn("layers[0].collectors[4].class: required", errors)
        self.assertTrue(
            any(
                error.startswith("layers[0].collectors[5].exclude_files_regex: invalid regex")
                for error in errors
            )
        )
        self.assertIn("layers[0].collectors[6].type: required", errors)
        self.assertIn("layers[0].collectors[7].exclude_files_regex: must be a string", errors)

    def test_accepts_valid_custom_collector(self):
        module_name = "dummy_validator_collectors"
        dummy_module = types.ModuleType(module_name)
        setattr(dummy_module, "DummyCustomCollector", DummyCustomCollector)
        sys.modules[module_name] = dummy_module
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                project_path = Path(temporary_directory)
                config = {
                    "paths": [str(project_path)],
                    "exclude_files": [],
                    "layers": [
                        {
                            "name": "domain",
                            "collectors": [
                                {
                                    "type": "custom",
                                    "class": f"{module_name}.DummyCustomCollector",
                                }
                            ],
                        }
                    ],
                    "ruleset": {},
                }

                errors = self._validate(config)
        finally:
            del sys.modules[module_name]

        self.assertEqual(errors, [])

    def test_accepts_decorator_collector_name_or_regex_and_reports_bad_values(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            config = {
                "paths": [str(project_path)],
                "exclude_files": [],
                "layers": [
                    {
                        "name": "domain",
                        "collectors": [
                            {
                                "type": "decorator_usage",
                                "decorator_name": "entity",
                            },
                            {
                                "type": "decorator_usage",
                                "decorator_regex": r"^entity_",
                            },
                            {
                                "type": "decorator_usage",
                                "decorator_name": 123,
                                "decorator_regex": "[",
                            },
                        ],
                    }
                ],
                "ruleset": {},
            }

            errors = self._validate(config)

        self.assertNotIn("layers[0].collectors[0]: decorator_name or decorator_regex required", errors)
        self.assertNotIn("layers[0].collectors[0].decorator_name: must be a string", errors)
        self.assertNotIn("layers[0].collectors[1]: decorator_name or decorator_regex required", errors)
        self.assertIn("layers[0].collectors[2].decorator_name: must be a string", errors)
        self.assertTrue(
            any(error.startswith("layers[0].collectors[2].decorator_regex: invalid regex") for error in errors)
        )

    def test_reports_nested_bool_collector_errors(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            config = {
                "paths": [str(project_path)],
                "exclude_files": [],
                "layers": [
                    {
                        "name": "domain",
                        "collectors": [
                            {
                                "type": "bool",
                                "must": [
                                    {
                                        "type": "decorator_usage",
                                    }
                                ],
                            },
                            {
                                "type": "bool",
                                "must": [],
                            },
                        ],
                    }
                ],
                "ruleset": {},
            }

            errors = ConfigValidator(project_path / "deply.yaml").validate(config)

        self.assertIn(
            "layers[0].collectors[0].must[0]: decorator_name or decorator_regex required",
            errors,
        )
        self.assertIn(
            "layers[0].collectors[1]: one of must, any_of, or must_not must contain collectors",
            errors,
        )

    def test_reports_bool_collector_must_not_errors(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            config = {
                "paths": [str(project_path)],
                "exclude_files": [],
                "layers": [
                    {
                        "name": "domain",
                        "collectors": [
                            {
                                "type": "bool",
                                "must_not": [
                                    {
                                        "type": "function_name_regex",
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "ruleset": {},
            }

            errors = self._validate(config)

        self.assertIn("layers[0].collectors[0].must_not[0].function_name_regex: required", errors)

    def test_reports_rule_errors(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            config = {
                "paths": [str(project_path)],
                "exclude_files": [],
                "layers": [
                    {
                        "name": "domain",
                        "collectors": [
                            {
                                "type": "class_inherits",
                                "base_class": "Entity",
                            }
                        ],
                    }
                ],
                "ruleset": {
                    "missing": {
                        "allow_layer_dependencies": ["domain"],
                    },
                    "domain": {
                        "disallow_layer_dependencies": ["missing"],
                        "enforce_class_naming": [
                            {
                                "type": "unknown",
                            },
                            {
                                "type": "class_name_regex",
                                "class_name_regex": "[",
                            },
                        ],
                        "enforce_inheritance": [
                            {
                                "type": "bool",
                                "any_of": [
                                    {
                                        "type": "class_inherits",
                                    }
                                ],
                            }
                        ],
                    },
                },
            }

            errors = ConfigValidator(project_path / "deply.yaml").validate(config)

        self.assertIn("ruleset.missing: unknown layer: missing", errors)
        self.assertIn("ruleset.missing.allow_layer_dependencies: unknown rule key", errors)
        self.assertIn("ruleset.domain.disallow_layer_dependencies[0]: unknown layer: missing", errors)
        self.assertIn("ruleset.domain.enforce_class_naming[0].type: unknown rule type: unknown", errors)
        self.assertTrue(
            any(error.startswith("ruleset.domain.enforce_class_naming[1].class_name_regex: invalid regex") for error in errors)
        )
        self.assertIn("ruleset.domain.enforce_inheritance[0].any_of[0].base_class: required", errors)

    def test_reports_rule_shape_errors(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            config = {
                "paths": [str(project_path)],
                "exclude_files": [],
                "layers": [
                    {
                        "name": "domain",
                        "collectors": [
                            {
                                "type": "class_name_regex",
                                "class_name_regex": ".*",
                            }
                        ],
                    }
                ],
                "ruleset": {
                    123: {},
                    "domain": {
                        "unknown": [],
                        "disallow_external_imports": "django",
                        "enforce_function_naming": "not-list",
                    },
                },
            }

            errors = self._validate(config)

        self.assertIn("ruleset: layer names must be non-empty strings", errors)
        self.assertIn("ruleset.domain.unknown: unknown rule key", errors)
        self.assertIn("ruleset.domain.disallow_external_imports: must be a list of strings", errors)
        self.assertIn("ruleset.domain.enforce_function_naming: must be a list", errors)

    def test_reports_rule_required_field_errors(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            config = {
                "paths": [str(project_path)],
                "exclude_files": [],
                "layers": [
                    {
                        "name": "domain",
                        "collectors": [
                            {
                                "type": "class_name_regex",
                                "class_name_regex": ".*",
                            }
                        ],
                    }
                ],
                "ruleset": {
                    "domain": {
                        "enforce_function_naming": [
                            {
                                "type": "function_name_regex",
                            }
                        ],
                        "enforce_class_decorator_usage": [
                            {
                                "type": "class_decorator_name_regex",
                            }
                        ],
                        "enforce_function_decorator_usage": [
                            {
                                "type": "function_decorator_name_regex",
                            }
                        ],
                        "enforce_inheritance": [
                            {
                                "type": "class_inherits",
                            },
                            {
                                "type": "bool",
                                "must_not": [
                                    {
                                        "type": "class_name_regex",
                                    }
                                ],
                            },
                        ],
                    }
                },
            }

            errors = self._validate(config)

        self.assertIn("ruleset.domain.enforce_function_naming[0].function_name_regex: required", errors)
        self.assertIn("ruleset.domain.enforce_class_decorator_usage[0].decorator_name_regex: required", errors)
        self.assertIn("ruleset.domain.enforce_function_decorator_usage[0].decorator_name_regex: required", errors)
        self.assertIn("ruleset.domain.enforce_inheritance[0].base_class: required", errors)
        self.assertIn("ruleset.domain.enforce_inheritance[1].must_not[0].class_name_regex: required", errors)

    def test_continues_after_unknown_rule_key(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            config = {
                "paths": [str(project_path)],
                "exclude_files": [],
                "layers": [
                    {
                        "name": "domain",
                        "collectors": [
                            {
                                "type": "class_name_regex",
                                "class_name_regex": ".*",
                            }
                        ],
                    }
                ],
                "ruleset": {
                    "domain": {
                        "unknown": [],
                        "disallow_layer_dependencies": "not-list",
                    }
                },
            }

            errors = self._validate(config)

        self.assertIn("ruleset.domain.unknown: unknown rule key", errors)
        self.assertIn("ruleset.domain.disallow_layer_dependencies: must be a list of strings", errors)
        self.assertFalse(any("unknown layer" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
