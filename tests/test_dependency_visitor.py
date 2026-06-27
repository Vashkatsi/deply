import ast
import textwrap
import unittest
from pathlib import Path

from deply.models.code_element import CodeElement
from deply.utils.ast_utils import set_ast_parents
from deply.utils.dependency_visitor import DependencyVisitor


class TestDependencyVisitor(unittest.TestCase):
    def _build_code_element(self, name: str, element_type: str = "function") -> CodeElement:
        return CodeElement(
            file=Path("sample.py"),
            name=name,
            element_type=element_type,
            line=1,
            column=0,
        )

    def test_visit_import_and_import_from_creates_dependencies_for_each_source_element(self):
        source_code = textwrap.dedent(
            """
            import package.module as imported_module
            import another.module
            from package.other import ImportedSymbol as imported_symbol

            def source_function():
                return imported_symbol()

            class SourceClass:
                pass
            """
        )
        syntax_tree = ast.parse(source_code)
        set_ast_parents(syntax_tree)

        source_function_element = self._build_code_element("source_function", "function")
        source_class_element = self._build_code_element("SourceClass", "class")

        imported_module_element = self._build_code_element("imported_module_dependency", "variable")
        another_module_element = self._build_code_element("another_module_dependency", "variable")
        imported_symbol_element = self._build_code_element("imported_symbol_dependency", "class")

        captured_dependencies = []
        visitor = DependencyVisitor(
            code_elements_in_file={
                "source_function": source_function_element,
                "SourceClass": source_class_element,
            },
            dependency_types=["import", "import_from"],
            dependency_handler=captured_dependencies.append,
            name_to_elements={
                "imported_module": {imported_module_element},
                "another": {another_module_element},
                "imported_symbol": {imported_symbol_element},
            },
        )

        visitor.visit(syntax_tree)

        actual_dependencies = {
            (
                dependency.dependency_type,
                dependency.code_element.name,
                dependency.depends_on_code_element.name,
                dependency.line,
                dependency.column,
            )
            for dependency in captured_dependencies
        }

        expected_dependencies = {
            ("import", "source_function", "imported_module_dependency", 2, 0),
            ("import", "SourceClass", "imported_module_dependency", 2, 0),
            ("import", "source_function", "another_module_dependency", 3, 0),
            ("import", "SourceClass", "another_module_dependency", 3, 0),
            ("import_from", "source_function", "imported_symbol_dependency", 4, 0),
            ("import_from", "SourceClass", "imported_symbol_dependency", 4, 0),
        }
        self.assertEqual(actual_dependencies, expected_dependencies)

    def test_visit_collects_function_call_attribute_call_and_inheritance_dependencies(self):
        source_code = textwrap.dedent(
            """
            class Base:
                pass

            class Child(Base):
                def method(self):
                    helper()
                    service.run()
            """
        )
        syntax_tree = ast.parse(source_code)
        set_ast_parents(syntax_tree)

        child_element = self._build_code_element("Child", "class")
        method_element = self._build_code_element("Child.method", "function")
        base_element = self._build_code_element("Base", "class")
        helper_element = self._build_code_element("helper", "function")
        run_element = self._build_code_element("service.run", "function")

        captured_dependencies = []
        visitor = DependencyVisitor(
            code_elements_in_file={
                "Child": child_element,
                "Child.method": method_element,
            },
            dependency_types=["class_inheritance", "function_call"],
            dependency_handler=captured_dependencies.append,
            name_to_elements={
                "Base": {base_element},
                "helper": {helper_element},
                "service.run": {run_element},
            },
        )

        visitor.visit(syntax_tree)

        actual_dependencies = {
            (
                dependency.dependency_type,
                dependency.code_element.name,
                dependency.depends_on_code_element.name,
                dependency.line,
                dependency.column,
            )
            for dependency in captured_dependencies
        }

        expected_dependencies = {
            ("class_inheritance", "Child", "Base", 5, 12),
            ("function_call", "Child.method", "helper", 7, 8),
            ("function_call", "Child.method", "service.run", 8, 8),
        }
        self.assertEqual(actual_dependencies, expected_dependencies)

    def test_visit_class_and_function_collects_decorator_annotation_and_metaclass_dependencies(self):
        source_code = textwrap.dedent(
            """
            @function_decorator()
            def source_function(parameter_annotation: ParameterType) -> ReturnType:
                return 1

            @class_decorator()
            class SourceClass(metaclass=MetaClass):
                pass
            """
        )
        syntax_tree = ast.parse(source_code)
        set_ast_parents(syntax_tree)

        source_function_node = syntax_tree.body[0]
        source_class_node = syntax_tree.body[1]

        source_function_element = self._build_code_element("source_function", "function")
        source_class_element = self._build_code_element("SourceClass", "class")

        function_decorator_element = self._build_code_element("function_decorator", "function")
        class_decorator_element = self._build_code_element("class_decorator", "class")
        parameter_type_element = self._build_code_element("ParameterType", "class")
        return_type_element = self._build_code_element("ReturnType", "class")
        metaclass_element = self._build_code_element("MetaClass", "class")

        captured_dependencies = []
        visitor = DependencyVisitor(
            code_elements_in_file={
                "source_function": source_function_element,
                "SourceClass": source_class_element,
            },
            dependency_types=["decorator", "type_annotation", "metaclass"],
            dependency_handler=captured_dependencies.append,
            name_to_elements={
                "function_decorator": {function_decorator_element},
                "class_decorator": {class_decorator_element},
                "ParameterType": {parameter_type_element},
                "ReturnType": {return_type_element},
                "MetaClass": {metaclass_element},
            },
        )

        visitor.visit(syntax_tree)

        actual_dependencies = {
            (
                dependency.dependency_type,
                dependency.code_element.name,
                dependency.depends_on_code_element.name,
                dependency.line,
                dependency.column,
            )
            for dependency in captured_dependencies
        }

        metaclass_node = source_class_node.keywords[0].value
        expected_dependencies = {
            (
                "decorator",
                "source_function",
                "function_decorator",
                source_function_node.decorator_list[0].lineno,
                source_function_node.decorator_list[0].col_offset,
            ),
            (
                "type_annotation",
                "source_function",
                "ParameterType",
                source_function_node.args.args[0].annotation.lineno,
                source_function_node.args.args[0].annotation.col_offset,
            ),
            (
                "type_annotation",
                "source_function",
                "ReturnType",
                source_function_node.returns.lineno,
                source_function_node.returns.col_offset,
            ),
            (
                "decorator",
                "SourceClass",
                "class_decorator",
                source_class_node.decorator_list[0].lineno,
                source_class_node.decorator_list[0].col_offset,
            ),
            (
                "metaclass",
                "SourceClass",
                "MetaClass",
                metaclass_node.lineno,
                metaclass_node.col_offset,
            ),
        }
        self.assertEqual(actual_dependencies, expected_dependencies)

    def test_visit_name_load_collects_dependency_for_loaded_names(self):
        source_code = textwrap.dedent(
            """
            def source_function():
                return shared_value
            """
        )
        syntax_tree = ast.parse(source_code)
        set_ast_parents(syntax_tree)

        source_function_element = self._build_code_element("source_function", "function")
        shared_value_element = self._build_code_element("shared_value", "variable")

        captured_dependencies = []
        visitor = DependencyVisitor(
            code_elements_in_file={
                "source_function": source_function_element,
            },
            dependency_types=["name_load"],
            dependency_handler=captured_dependencies.append,
            name_to_elements={
                "shared_value": {shared_value_element},
            },
        )

        visitor.visit(syntax_tree)

        self.assertEqual(len(captured_dependencies), 1)
        dependency = captured_dependencies[0]
        self.assertEqual(dependency.dependency_type, "name_load")
        self.assertEqual(dependency.code_element, source_function_element)
        self.assertEqual(dependency.depends_on_code_element, shared_value_element)
        self.assertEqual(dependency.line, 3)
        self.assertEqual(dependency.column, 11)

    def test_get_full_name_handles_subscript_constant_index_and_fallback(self):
        visitor = DependencyVisitor(
            code_elements_in_file={},
            dependency_types=[],
            dependency_handler=lambda _dependency: None,
            name_to_elements={},
        )

        subscript_node = ast.parse("Container[Item]", mode="eval").body
        self.assertEqual(visitor._get_full_name(subscript_node), "Container")

        constant_node = ast.Constant(value=123)
        self.assertEqual(visitor._get_full_name(constant_node), "123")

        attribute_with_unknown_value_node = ast.Attribute(
            value=ast.BinOp(
                left=ast.Constant(value=1),
                op=ast.Add(),
                right=ast.Constant(value=2),
            ),
            attr="field",
            ctx=ast.Load(),
        )
        self.assertEqual(visitor._get_full_name(attribute_with_unknown_value_node), "field")

        unsupported_node = ast.parse("left + right", mode="eval").body
        self.assertIsNone(visitor._get_full_name(unsupported_node))

        if hasattr(ast, "Index"):
            legacy_index_node = ast.Index(value=ast.Name(id="LegacyType", ctx=ast.Load()))
            self.assertEqual(visitor._get_full_name(legacy_index_node), "LegacyType")


if __name__ == "__main__":
    unittest.main()
