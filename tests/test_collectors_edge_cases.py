import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from deply.collectors.bool_collector import BoolCollector
from deply.collectors.class_inherits_collector import ClassInheritsCollector
from deply.collectors.decorator_usage_collector import DecoratorUsageCollector
from deply.collectors.directory_collector import DirectoryCollector
from deply.collectors.file_regex_collector import FileRegexCollector
from deply.collectors.function_name_regex_collector import FunctionNameRegexCollector
from deply.models.code_element import CodeElement


class TestCollectorEdgeCases(unittest.TestCase):
    def _parse(self, source_code: str) -> ast.AST:
        return ast.parse(source_code)

    def _unsupported_decorator_node(self) -> ast.AST:
        return ast.parse("decorators[0]", mode="eval").body

    def _prepend_unsupported_decorator(self, node: ast.AST) -> None:
        node.decorator_list.insert(0, self._unsupported_decorator_node())

    def _build_code_element(self, name: str, element_type: str = "class") -> CodeElement:
        return CodeElement(
            file=Path("sample.py"),
            name=name,
            element_type=element_type,
            line=1,
            column=0,
        )

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

    def test_file_regex_collector_hits_global_exclude_not_matched_and_type_filters(self):
        source_tree = self._parse(
            """
class ExampleService:
    pass

def utility_function():
    return 1

module_value = 10
            """
        )
        target_path = Path("/tmp/project/target.py")

        collector_with_global_exclude = FileRegexCollector(
            config={"regex": r".*target\.py$"},
            paths=["/tmp/project"],
            exclude_files=[r".*target\.py$"],
        )
        self.assertEqual(collector_with_global_exclude.match_in_file(source_tree, target_path), set())

        not_matched_collector = FileRegexCollector(
            config={"regex": r".*another\.py$"},
            paths=["/tmp/project"],
            exclude_files=[],
        )
        self.assertEqual(not_matched_collector.match_in_file(source_tree, target_path), set())

        class_only_collector = FileRegexCollector(
            config={"regex": r".*target\.py$", "element_type": "class"},
            paths=["/tmp/project"],
            exclude_files=[],
        )
        class_only_names = {
            element.name for element in class_only_collector.match_in_file(source_tree, target_path)
        }
        self.assertEqual(class_only_names, {"ExampleService"})

    def test_file_regex_collector_handles_partial_annotations_and_non_name_assign_targets(self):
        source_tree = self._parse(
            """
@visible
def collect_data(
    pos_only_annotated: int,
    pos_only_missing,
    /,
    regular_annotated: str,
    regular_missing,
    *var_args,
    key_only_annotated: bool,
    key_only_missing,
    **kwargs
) -> ReturnType:
    return 1

def no_return_annotation(parameter):
    return parameter

left, right = (1, 2)
module_value = 100
            """
        )
        for node in ast.walk(source_tree):
            if isinstance(node, ast.FunctionDef) and node.name in {"collect_data", "no_return_annotation"}:
                self._prepend_unsupported_decorator(node)
        target_path = Path("/tmp/project/target.py")

        function_collector = FileRegexCollector(
            config={"regex": r".*target\.py$", "element_type": "function"},
            paths=["/tmp/project"],
            exclude_files=[],
        )
        function_elements = function_collector.match_in_file(source_tree, target_path)
        function_names = {element.name for element in function_elements}
        self.assertEqual(function_names, {"collect_data", "no_return_annotation"})

        collect_data_element = next(element for element in function_elements if element.name == "collect_data")
        self.assertEqual(collect_data_element.return_annotation, "ReturnType")
        self.assertEqual(
            dict(collect_data_element.type_annotations),
            {
                "pos_only_annotated": "int",
                "regular_annotated": "str",
                "key_only_annotated": "bool",
            },
        )

        no_return_element = next(element for element in function_elements if element.name == "no_return_annotation")
        self.assertIsNone(no_return_element.return_annotation)
        self.assertEqual(dict(no_return_element.type_annotations), {})

        variable_collector = FileRegexCollector(
            config={"regex": r".*target\.py$", "element_type": "variable"},
            paths=["/tmp/project"],
            exclude_files=[],
        )
        variable_names = {
            element.name for element in variable_collector.match_in_file(source_tree, target_path)
        }
        self.assertEqual(variable_names, {"module_value"})

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

    def test_directory_collector_hits_global_exclude_and_element_type_branches(self):
        source_tree = self._parse(
            """
class ExampleService:
    pass

def helper():
    return 1
            """
        )
        target_path = Path("/tmp/project/services/module.py")

        collector_with_global_exclude = DirectoryCollector(
            config={"directories": ["services"]},
            paths=["/tmp/project"],
            exclude_files=[r".*services/module\.py$"],
        )
        self.assertEqual(collector_with_global_exclude.match_in_file(source_tree, target_path), set())

        class_only_collector = DirectoryCollector(
            config={"directories": ["services"], "element_type": "class"},
            paths=["/tmp/project"],
            exclude_files=[],
        )
        class_only_names = {
            element.name for element in class_only_collector.match_in_file(source_tree, target_path)
        }
        self.assertEqual(class_only_names, {"ExampleService"})

    def test_directory_collector_handles_optional_annotations_and_variable_fqn_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            file_path = project_path / "services" / "module.py"
            file_path.parent.mkdir(parents=True)

            source_tree = self._parse(
                """
@named_class_decorator
class Service:
    valid_field: str
    invalid_field: 1 + 2

@named_function_decorator
def execute(
    pos_only_annotated: int,
    pos_only_missing,
    /,
    regular_annotated: str,
    regular_missing,
    *var_args,
    key_only_annotated: bool,
    key_only_missing,
    **kwargs
):
    return 1

module_value = 5
                """
            )
            for node in ast.walk(source_tree):
                if isinstance(node, ast.ClassDef) and node.name == "Service":
                    self._prepend_unsupported_decorator(node)
                if isinstance(node, ast.FunctionDef) and node.name == "execute":
                    self._prepend_unsupported_decorator(node)

            collector = DirectoryCollector(
                config={"directories": ["services"]},
                paths=[str(project_path)],
                exclude_files=[],
            )
            collected_elements = collector.match_in_file(source_tree, file_path)

            variable_names = {element.name for element in collected_elements if element.element_type == "variable"}
            self.assertIn("Service.valid_field", variable_names)
            self.assertIn("Service.invalid_field", variable_names)
            self.assertIn("module_value", variable_names)

            function_element = next(
                element
                for element in collected_elements
                if element.element_type == "function" and element.name == "execute"
            )
            self.assertIsNone(function_element.return_annotation)
            self.assertEqual(
                dict(function_element.type_annotations),
                {
                    "pos_only_annotated": "int",
                    "regular_annotated": "str",
                    "key_only_annotated": "bool",
                },
            )

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

    def test_decorator_usage_collector_handles_no_match_and_optional_annotations(self):
        source_tree = self._parse(
            """
@track_usage
def tracked(
    pos_only_annotated: int,
    pos_only_missing,
    /,
    regular_annotated: str,
    regular_missing,
    *var_args,
    key_only_annotated: bool,
    key_only_missing,
    **kwargs
):
    return 1

def unmatched():
    return 1

class BaseModel:
    pass

@track_usage
class TrackedClass(BaseModel):
    valid_field: str
    invalid_field: 1 + 2
            """
        )
        for node in ast.walk(source_tree):
            if isinstance(node, ast.FunctionDef) and node.name in {"tracked", "unmatched"}:
                self._prepend_unsupported_decorator(node)
            if isinstance(node, ast.ClassDef) and node.name == "TrackedClass":
                self._prepend_unsupported_decorator(node)
        collector = DecoratorUsageCollector({"decorator_regex": r"^track_.*$"})
        collected_elements = collector.match_in_file(source_tree, Path("/tmp/metrics.py"))

        names = {element.name for element in collected_elements}
        self.assertEqual(names, {"tracked", "TrackedClass"})
        tracked_element = next(element for element in collected_elements if element.name == "tracked")
        self.assertEqual(
            dict(tracked_element.type_annotations),
            {
                "pos_only_annotated": "int",
                "regular_annotated": "str",
                "key_only_annotated": "bool",
            },
        )
        tracked_class = next(element for element in collected_elements if element.name == "TrackedClass")
        self.assertEqual(dict(tracked_class.type_annotations), {"valid_field": "str"})

    def test_function_name_regex_collector_handles_regex_miss_and_optional_annotations(self):
        source_tree = self._parse(
            """
@trace
def collect_items(
    pos_only_annotated: int,
    pos_only_missing,
    /,
    regular_annotated: str,
    regular_missing,
    *var_args,
    key_only_annotated: bool,
    key_only_missing,
    **kwargs
):
    return 1

def skip_items(parameter):
    return parameter
            """
        )
        for node in ast.walk(source_tree):
            if isinstance(node, ast.FunctionDef) and node.name == "collect_items":
                self._prepend_unsupported_decorator(node)
        collector = FunctionNameRegexCollector({"function_name_regex": r"^collect_.*$"})
        collected_elements = collector.match_in_file(source_tree, Path("/tmp/metrics.py"))

        self.assertEqual({element.name for element in collected_elements}, {"collect_items"})
        collect_element = next(iter(collected_elements))
        self.assertIsNone(collect_element.return_annotation)
        self.assertEqual(
            dict(collect_element.type_annotations),
            {
                "pos_only_annotated": "int",
                "regular_annotated": "str",
                "key_only_annotated": "bool",
            },
        )

    def test_class_inherits_collector_hits_exclude_and_no_match_branches(self):
        source_tree = self._parse(
            """
class BaseModel:
    pass

class UserModel(BaseModel):
    pass
            """
        )
        target_path = Path("/tmp/project/models/model.py")

        excluded_collector = ClassInheritsCollector(
            {"base_class": "BaseModel", "exclude_files_regex": r"model\.py$"}
        )
        self.assertEqual(excluded_collector.match_in_file(source_tree, target_path), set())

        non_matching_collector = ClassInheritsCollector({"base_class": "OtherBase"})
        self.assertEqual(non_matching_collector.match_in_file(source_tree, target_path), set())

    def test_class_inherits_collector_handles_decorators_and_partial_annotations(self):
        source_tree = self._parse(
            """
class BaseModel:
    pass

@entity
class UserModel(BaseModel):
    valid_field: str
    invalid_field: 1 + 2
            """
        )
        for node in ast.walk(source_tree):
            if isinstance(node, ast.ClassDef) and node.name == "UserModel":
                self._prepend_unsupported_decorator(node)
        collector = ClassInheritsCollector({"base_class": "BaseModel"})
        collected_elements = collector.match_in_file(source_tree, Path("/tmp/project/models/user_model.py"))

        self.assertEqual({element.name for element in collected_elements}, {"UserModel"})
        user_model_element = next(iter(collected_elements))
        self.assertEqual(user_model_element.decorators, ("entity",))
        self.assertEqual(dict(user_model_element.type_annotations), {"valid_field": "str"})

    def test_bool_collector_combines_must_any_of_and_must_not(self):
        source_tree = self._parse("value = 1")
        file_path = Path("/tmp/project/module.py")

        element_a = self._build_code_element("A")
        element_b = self._build_code_element("B")
        element_c = self._build_code_element("C")
        element_d = self._build_code_element("D")

        class DummyCollector:
            def __init__(self, collected_elements):
                self.collected_elements = set(collected_elements)

            def match_in_file(self, _file_ast, _file_path):
                return set(self.collected_elements)

        with patch(
            "deply.collectors.collector_factory.CollectorFactory.create",
            side_effect=[
                DummyCollector({element_a, element_b, element_c}),
                DummyCollector({element_b, element_c}),
                DummyCollector({element_c}),
            ],
        ):
            collector = BoolCollector(
                config={
                    "must": [{"type": "first"}],
                    "any_of": [{"type": "second"}],
                    "must_not": [{"type": "third"}],
                },
                paths=[],
                exclude_files=[],
            )
            self.assertEqual(collector.match_in_file(source_tree, file_path), {element_b})

        with patch(
            "deply.collectors.collector_factory.CollectorFactory.create",
            side_effect=[DummyCollector({element_a}), DummyCollector({element_b})],
        ):
            collector = BoolCollector(
                config={"any_of": [{"type": "first"}, {"type": "second"}]},
                paths=[],
                exclude_files=[],
            )
            self.assertEqual(collector.match_in_file(source_tree, file_path), {element_a, element_b})

        with patch(
            "deply.collectors.collector_factory.CollectorFactory.create",
            side_effect=[DummyCollector({element_a, element_b}), DummyCollector({element_b, element_d})],
        ):
            collector = BoolCollector(
                config={"must": [{"type": "first"}, {"type": "second"}]},
                paths=[],
                exclude_files=[],
            )
            self.assertEqual(collector.match_in_file(source_tree, file_path), {element_b})

        collector = BoolCollector(config={}, paths=[], exclude_files=[])
        self.assertEqual(collector.match_in_file(source_tree, file_path), set())


if __name__ == "__main__":
    unittest.main()
