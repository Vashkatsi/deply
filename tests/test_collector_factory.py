import sys
import types
import unittest
from typing import List

from deply.collectors.base_collector import BaseCollector
from deply.collectors.collector_factory import CollectorFactory


# Dummy custom collector implementing BaseCollector interface
class DummyCustomCollector(BaseCollector):
    def __init__(self, config: dict):
        self.config = config

    def match_in_file(self, file_ast, file_path) -> set:
        return set()


class TestCollectorFactoryCustom(unittest.TestCase):
    def setUp(self):
        # Inject dummy module into sys.modules so that it can be imported
        module_name = "dummy_custom_collectors"
        self.dummy_module = types.ModuleType(module_name)
        setattr(self.dummy_module, "DummyCustomCollector", DummyCustomCollector)
        sys.modules[module_name] = self.dummy_module

    def tearDown(self):
        # Clean up the injected module
        if "dummy_custom_collectors" in sys.modules:
            del sys.modules["dummy_custom_collectors"]

    def test_custom_collector_creation(self):
        config = {
            "type": "custom",
            "class": "dummy_custom_collectors.DummyCustomCollector",
            "params": {"foo": "bar"}
        }
        paths: List[str] = ["dummy_path"]
        exclude_files: List[str] = ["dummy_pattern"]
        collector = CollectorFactory.create(config, paths, exclude_files)
        # Assert that we got an instance of our dummy collector
        self.assertIsInstance(collector, DummyCustomCollector)
        # Expected config passed to the custom collector
        expected_config = {
            "params": {"foo": "bar"},
            "paths": paths,
            "exclude_files": exclude_files,
        }
        self.assertEqual(collector.config, expected_config)

    def test_custom_collector_missing_class_field(self):
        config = {
            "type": "custom",
            "params": {"foo": "bar"}
        }
        with self.assertRaises(ValueError) as context:
            CollectorFactory.create(config, [], [])
        self.assertIn("Custom collector requires 'class' field", str(context.exception))

    def test_custom_collector_invalid_class_path(self):
        config = {
            "type": "custom",
            "class": "invalidpath",
            "params": {"foo": "bar"}
        }
        with self.assertRaises(ValueError) as context:
            CollectorFactory.create(config, [], [])
        self.assertIn("Invalid class path format", str(context.exception))

    def test_custom_collector_module_not_found(self):
        config = {
            "type": "custom",
            "class": "nonexistent_module.DummyCustomCollector",
            "params": {"foo": "bar"}
        }
        with self.assertRaises(ValueError) as context:
            CollectorFactory.create(config, [], [])
        self.assertIn("Failed to import module", str(context.exception))

    def test_custom_collector_class_not_found(self):
        config = {
            "type": "custom",
            "class": "dummy_custom_collectors.NonExistentClass",
            "params": {"foo": "bar"}
        }
        with self.assertRaises(ValueError) as context:
            CollectorFactory.create(config, [], [])
        self.assertIn("Class 'NonExistentClass' not found", str(context.exception))


if __name__ == "__main__":
    unittest.main()
