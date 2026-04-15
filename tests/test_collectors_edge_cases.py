import ast
import tempfile
import unittest
from pathlib import Path

from deply.collectors.decorator_usage_collector import DecoratorUsageCollector
from deply.collectors.directory_collector import DirectoryCollector
from deply.collectors.file_regex_collector import FileRegexCollector
from deply.collectors.function_name_regex_collector import FunctionNameRegexCollector


class TestCollectorEdgeCases(unittest.TestCase):
    def _parse(self, source_code: str) -> ast.AST:
        return ast.parse(source_code)

    def test_file_regex_collector_full_path_fallback_and_exclude_files_regex(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            target_file_path = project_path / "services" / "target.py"
            target_file_path.parent.mkdir(parents=True)

            source_tree = self._parse("class ExampleService:\n    pass\n")

            collector_with_full_path_regex = FileRegexCollector(
                config={"regex": str(target_file_path)},
                paths=[str(project_path / "unrelated")],
                exclude_files=[],
            )
            matched_elements = collector_with_full_path_regex.match_in_file(source_tree, target_file_path)
            self.assertEqual({element.name for element in matched_elements}, {"ExampleService"})

            collector_with_exclude_regex = FileRegexCollector(
                config={
                    "regex": str(target_file_path),
                    "exclude_files_regex": r"target\.py$",
                },
                paths=[str(project_path / "unrelated")],
                exclude_files=[],
            )
            excluded_elements = collector_with_exclude_regex.match_in_file(source_tree, target_file_path)
            self.assertEqual(excluded_elements, set())

    def test_file_regex_collector_variable_mode_skips_class_fields(self):
        source_tree = self._parse(
            """
class Example:
    class_field: int = 1
    another_field = 2

module_annotated: str = \"value\"
module_plain = 100
            """
        )

        collector = FileRegexCollector(
            config={"regex": r".*target\.py$", "element_type": "variable"},
            paths=["/tmp/unrelated"],
            exclude_files=[],
        )
        collected_elements = collector.match_in_file(source_tree, Path("/tmp/project/target.py"))

        collected_names = {element.name for element in collected_elements}
        self.assertEqual(collected_names, {"module_annotated", "module_plain"})

    def test_directory_collector_handles_annotations_and_exclusions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            file_path = project_path / "services" / "module.py"
            file_path.parent.mkdir(parents=True)

            source_tree = self._parse(
                """
@service_decorator
def collect_data(pos_only: int, /, normal: str, *var_args: float, key_only: bool, **key_values: bytes) -> ReturnType:
    return 1
                """
            )

            collector = DirectoryCollector(
                config={"directories": ["services"], "element_type": "function"},
                paths=[str(project_path)],
                exclude_files=[],
            )
            collected_elements = collector.match_in_file(source_tree, file_path)
            self.assertEqual(len(collected_elements), 1)

            collected_element = next(iter(collected_elements))
            self.assertEqual(collected_element.decorators, ("service_decorator",))
            self.assertEqual(collected_element.return_annotation, "ReturnType")
            self.assertEqual(
                dict(collected_element.type_annotations),
                {
                    "pos_only": "int",
                    "normal": "str",
                    "var_args": "float",
                    "key_only": "bool",
                    "key_values": "bytes",
                },
            )

            excluded_collector = DirectoryCollector(
                config={
                    "directories": ["services"],
                    "element_type": "function",
                    "exclude_files_regex": r"module\.py$",
                },
                paths=[str(project_path)],
                exclude_files=[],
            )
            self.assertEqual(excluded_collector.match_in_file(source_tree, file_path), set())

    def test_directory_collector_returns_empty_for_file_outside_base_paths(self):
        collector = DirectoryCollector(
            config={"directories": ["services"]},
            paths=["/tmp/project"],
            exclude_files=[],
        )
        source_tree = self._parse("class Example:\n    pass\n")

        collected_elements = collector.match_in_file(source_tree, Path("/another/location/module.py"))
        self.assertEqual(collected_elements, set())

    def test_function_name_regex_collector_captures_all_annotation_kinds_and_exclude_regex(self):
        source_tree = self._parse(
            """
def collect_metrics(pos_only: int, /, normal: str, *var_args: float, key_only: bool, **key_values: bytes) -> ReturnType:
    return 1
            """
        )

        collector = FunctionNameRegexCollector({"function_name_regex": r"^collect_.*$"})
        collected_elements = collector.match_in_file(source_tree, Path("/tmp/metrics.py"))
        self.assertEqual(len(collected_elements), 1)

        collected_element = next(iter(collected_elements))
        self.assertEqual(collected_element.return_annotation, "ReturnType")
        self.assertEqual(
            dict(collected_element.type_annotations),
            {
                "normal": "str",
                "key_only": "bool",
                "pos_only": "int",
                "var_args": "float",
                "key_values": "bytes",
            },
        )

        excluded_collector = FunctionNameRegexCollector(
            {
                "function_name_regex": r"^collect_.*$",
                "exclude_files_regex": r"metrics\.py$",
            }
        )
        self.assertEqual(excluded_collector.match_in_file(source_tree, Path("/tmp/metrics.py")), set())

    def test_decorator_usage_collector_captures_all_annotation_kinds_and_exclude_regex(self):
        source_tree = self._parse(
            """
@track_usage
def collect_metrics(pos_only: int, /, normal: str, *var_args: float, key_only: bool, **key_values: bytes) -> ReturnType:
    return 1
            """
        )

        collector = DecoratorUsageCollector({"decorator_regex": r"^track_.*$"})
        collected_elements = collector.match_in_file(source_tree, Path("/tmp/metrics.py"))
        self.assertEqual(len(collected_elements), 1)

        collected_element = next(iter(collected_elements))
        self.assertEqual(collected_element.decorators, ("track_usage",))
        self.assertEqual(collected_element.return_annotation, "ReturnType")
        self.assertEqual(
            dict(collected_element.type_annotations),
            {
                "normal": "str",
                "key_only": "bool",
                "pos_only": "int",
                "var_args": "float",
                "key_values": "bytes",
            },
        )

        excluded_collector = DecoratorUsageCollector(
            {
                "decorator_regex": r"^track_.*$",
                "exclude_files_regex": r"metrics\.py$",
            }
        )
        self.assertEqual(excluded_collector.match_in_file(source_tree, Path("/tmp/metrics.py")), set())


if __name__ == "__main__":
    unittest.main()
