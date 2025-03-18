import ast
import unittest

from deply.utils.ast_utils import (
    get_import_aliases,
    get_base_name,
    get_decorator_name,
    get_annotation_name,
    set_ast_parents,
)


class TestASTUtils(unittest.TestCase):
    def test_get_import_aliases(self):
        code = """
import os
import sys as system
from math import sqrt, pi as PI
from collections import defaultdict
"""
        tree = ast.parse(code)
        aliases = get_import_aliases(tree)
        expected = {
            "os": "os",
            "system": "sys",
            "sqrt": "math.sqrt",
            "PI": "math.pi",
            "defaultdict": "collections.defaultdict",
        }
        self.assertEqual(aliases, expected)

    def test_get_base_name_with_name_node(self):
        # For an ast.Name node, it returns the alias if available
        import_aliases = {"MyClass": "module.MyClass"}
        node = ast.Name(id="MyClass", ctx=ast.Load())
        result = get_base_name(node, import_aliases)
        self.assertEqual(result, "module.MyClass")

    def test_get_base_name_with_attribute_node(self):
        # For a chained attribute, e.g. x.y, where import_aliases maps x to "mod.x"
        import_aliases = {"x": "mod.x"}
        expr = ast.parse("x.y", mode="eval").body  # returns an Attribute node
        result = get_base_name(expr, import_aliases)
        self.assertEqual(result, "mod.x.y")

    def test_get_decorator_name_name(self):
        # Test a simple decorator: @mydecorator
        code = """
@mydecorator
def foo(): pass
"""
        tree = ast.parse(code)
        decorator_node = tree.body[0].decorator_list[0]
        result = get_decorator_name(decorator_node)
        self.assertEqual(result, "mydecorator")

    def test_get_decorator_name_attribute(self):
        # Test a decorator with attribute: @module.decorator
        code = """
@module.decorator
def foo(): pass
"""
        tree = ast.parse(code)
        decorator_node = tree.body[0].decorator_list[0]
        result = get_decorator_name(decorator_node)
        self.assertEqual(result, "module.decorator")

    def test_get_decorator_name_call(self):
        # Test a decorator that is a call: @decorator(arg)
        code = """
@decorator(42)
def foo(): pass
"""
        tree = ast.parse(code)
        decorator_node = tree.body[0].decorator_list[0]
        result = get_decorator_name(decorator_node)
        self.assertEqual(result, "decorator")

    def test_get_annotation_name_simple(self):
        # Test with a simple annotation (Name node)
        tree = ast.parse("int", mode="eval")
        annotation_node = tree.body
        result = get_annotation_name(annotation_node, {})
        self.assertEqual(result, "int")

    def test_get_annotation_name_with_alias(self):
        # Test with a mapped name using import_aliases
        tree = ast.parse("MyType", mode="eval")
        annotation_node = tree.body
        import_aliases = {"MyType": "module.MyType"}
        result = get_annotation_name(annotation_node, import_aliases)
        self.assertEqual(result, "module.MyType")

    def test_get_annotation_name_with_attribute(self):
        # Test annotation for an attribute: module.attr
        tree = ast.parse("mod.attr", mode="eval")
        annotation_node = tree.body
        import_aliases = {"mod": "module.mod"}
        result = get_annotation_name(annotation_node, import_aliases)
        self.assertEqual(result, "module.mod.attr")

    def test_get_annotation_name_subscript(self):
        # Test a generic type: List[int]
        tree = ast.parse("List[int]", mode="eval")
        annotation_node = tree.body
        import_aliases = {"List": "typing.List"}
        result = get_annotation_name(annotation_node, import_aliases)
        self.assertEqual(result, "typing.List[int]")

    def test_set_ast_parents(self):
        code = "a = 1"
        tree = ast.parse(code)
        set_ast_parents(tree)
        # Check that the child node of the Assign has a parent attribute
        assign_node = tree.body[0]
        self.assertTrue(hasattr(assign_node.value, "parent"))
        self.assertEqual(assign_node.value.parent, assign_node)


if __name__ == "__main__":
    unittest.main()
