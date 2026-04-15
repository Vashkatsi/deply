import sys
import types
import unittest
from typing import List

from deply.collectors.base_collector import BaseCollector
from deply.collectors.bool_collector import BoolCollector
from deply.collectors.collector_factory import CollectorFactory
from deply.collectors.function_name_regex_collector import FunctionNameRegexCollector


class DummyCustomCollector(BaseCollector):
    def __init__(self, config: dict):
        self.config = config

    def match_in_file(self, file_ast, file_path) -> set:
        return set()


class WrongSignatureCollector(BaseCollector):
    def __init__(self):
        self.initialized = True

    def match_in_file(self, file_ast, file_path) -> set:
        return set()


class TestCollectorFactoryCustom(unittest.TestCase):
    def setUp(self):
        module_name = "dummy_custom_collectors"
        self.dummy_module = types.ModuleType(module_name)
        setattr(self.dummy_module, "DummyCustomCollector", DummyCustomCollector)
        setattr(self.dummy_module, "WrongSignatureCollector", WrongSignatureCollector)
        sys.modules[module_name] = self.dummy_module

    def tearDown(self):
        if "dummy_custom_collectors" in sys.modules:
            del sys.modules["dummy_custom_collectors"]

    def test_custom_collector_creation(self):
        config = {
            "type": "custom",
            "class": "dummy_custom_collectors.DummyCustomCollector",
            "params": {"foo": "bar"},
        }
        paths: List[str] = ["dummy_path"]
        exclude_files: List[str] = ["dummy_pattern"]
        collector = CollectorFactory.create(config, paths, exclude_files)

        self.assertIsInstance(collector, DummyCustomCollector)
        self.assertEqual(
            collector.config,
            {
                "params": {"foo": "bar"},
                "paths": paths,
                "exclude_files": exclude_files,
            },
        )

    def test_custom_collector_missing_class_field(self):
        config = {
            "type": "custom",
            "params": {"foo": "bar"},
        }
        with self.assertRaises(ValueError) as context:
            CollectorFactory.create(config, [], [])
        self.assertIn("Custom collector requires 'class' field", str(context.exception))

    def test_custom_collector_invalid_class_path(self):
        config = {
            "type": "custom",
            "class": "invalidpath",
            "params": {"foo": "bar"},
        }
        with self.assertRaises(ValueError) as context:
            CollectorFactory.create(config, [], [])
        self.assertIn("Invalid class path format", str(context.exception))

    def test_custom_collector_module_not_found(self):
        config = {
            "type": "custom",
            "class": "nonexistent_module.DummyCustomCollector",
            "params": {"foo": "bar"},
        }
        with self.assertRaises(ValueError) as context:
            CollectorFactory.create(config, [], [])
        self.assertIn("Failed to import module", str(context.exception))

    def test_custom_collector_class_not_found(self):
        config = {
            "type": "custom",
            "class": "dummy_custom_collectors.NonExistentClass",
            "params": {"foo": "bar"},
        }
        with self.assertRaises(ValueError) as context:
            CollectorFactory.create(config, [], [])
        self.assertIn("Class 'NonExistentClass' not found", str(context.exception))

    def test_custom_collector_type_error(self):
        config = {
            "type": "custom",
            "class": "dummy_custom_collectors.WrongSignatureCollector",
            "params": {"foo": "bar"},
        }
        with self.assertRaises(ValueError) as context:
            CollectorFactory.create(config, [], [])
        self.assertIn("Error initializing", str(context.exception))

    def test_function_name_regex_collector_creation(self):
        collector = CollectorFactory.create(
            {
                "type": "function_name_regex",
                "function_name_regex": r"^collect_.*$",
            },
            [],
            [],
        )
        self.assertIsInstance(collector, FunctionNameRegexCollector)

    def test_bool_collector_creation(self):
        collector = CollectorFactory.create(
            {
                "type": "bool",
                "must": [],
                "any_of": [],
                "must_not": [],
            },
            [],
            [],
        )
        self.assertIsInstance(collector, BoolCollector)

    def test_unknown_collector_type(self):
        with self.assertRaises(ValueError) as context:
            CollectorFactory.create({"type": "unknown"}, [], [])
        self.assertIn("Unknown collector type: unknown", str(context.exception))


if __name__ == "__main__":
    unittest.main()
