import ast
import logging
from typing import Callable, Dict, List, Optional, Set

from deply.models.code_element import CodeElement
from deply.models.dependency import Dependency


class DependencyVisitor(ast.NodeVisitor):
    def __init__(
            self,
            code_elements_in_file: Dict[str, CodeElement],
            dependency_types: List[str],
            dependency_handler: Callable[[Dependency], None],
            name_to_elements: Dict[str, Set[CodeElement]],
    ):
        self.code_elements_in_file = code_elements_in_file
        self.dependency_types = dependency_types
        self.dependency_handler = dependency_handler
        self.name_to_elements = name_to_elements
        self.current_code_element: Optional[CodeElement] = None
        logging.debug(f"DependencyVisitor created for file with {len(code_elements_in_file)} code elements")

    def visit_FunctionDef(self, node):
        full_name = self._get_definition_full_name(node)
        self.current_code_element = self.code_elements_in_file.get(full_name)
        if 'decorator' in self.dependency_types and self.current_code_element:
            self._process_decorators(node)
        if 'type_annotation' in self.dependency_types and self.current_code_element:
            if node.returns:
                self._process_annotation(node.returns)
            for arg in node.args.args + node.args.kwonlyargs:
                if arg.annotation:
                    self._process_annotation(arg.annotation)
        self.generic_visit(node)
        self.current_code_element = None

    def visit_ClassDef(self, node):
        full_name = self._get_definition_full_name(node)
        self.current_code_element = self.code_elements_in_file.get(full_name)
        if 'class_inheritance' in self.dependency_types and self.current_code_element:
            for base in node.bases:
                base_name = self._get_full_name(base)
                if base_name is None:
                    continue
                dep_elements = self.name_to_elements.get(base_name, set())
                for dep_element in dep_elements:
                    dependency = Dependency(
                        code_element=self.current_code_element,
                        depends_on_code_element=dep_element,
                        dependency_type='class_inheritance',
                        line=base.lineno,
                        column=base.col_offset
                    )
                    self.dependency_handler(dependency)
        if 'decorator' in self.dependency_types and self.current_code_element:
            self._process_decorators(node)
        if 'metaclass' in self.dependency_types and self.current_code_element:
            for keyword in node.keywords:
                if keyword.arg == 'metaclass':
                    metaclass_name = self._get_full_name(keyword.value)
                    if metaclass_name is None:
                        continue
                    dep_elements = self.name_to_elements.get(metaclass_name, set())
                    for dep_element in dep_elements:
                        dependency = Dependency(
                            code_element=self.current_code_element,
                            depends_on_code_element=dep_element,
                            dependency_type='metaclass',
                            line=keyword.value.lineno,
                            column=keyword.value.col_offset
                        )
                        self.dependency_handler(dependency)
        self.generic_visit(node)
        self.current_code_element = None

    def visit_Call(self, node):
        if 'function_call' in self.dependency_types and self.current_code_element:
            if isinstance(node.func, ast.Name):
                name = node.func.id
                dep_elements = self.name_to_elements.get(name, set())
                for dep_element in dep_elements:
                    dependency = Dependency(
                        code_element=self.current_code_element,
                        depends_on_code_element=dep_element,
                        dependency_type='function_call',
                        line=node.lineno,
                        column=node.col_offset
                    )
                    self.dependency_handler(dependency)
            elif isinstance(node.func, ast.Attribute):
                full_name = self._get_full_name(node.func)
                if full_name is None:
                    self.generic_visit(node)
                    return
                dep_elements = self.name_to_elements.get(full_name, set())
                for dep_element in dep_elements:
                    dependency = Dependency(
                        code_element=self.current_code_element,
                        depends_on_code_element=dep_element,
                        dependency_type='function_call',
                        line=node.lineno,
                        column=node.col_offset
                    )
                    self.dependency_handler(dependency)
        self.generic_visit(node)

    def visit_Import(self, node):
        if 'import' in self.dependency_types:
            for alias in node.names:
                name = alias.asname or alias.name.split('.')[0]
                dep_elements = self.name_to_elements.get(name, set())
                for dep_element in dep_elements:
                    for code_element in self.code_elements_in_file.values():
                        dependency = Dependency(
                            code_element=code_element,
                            depends_on_code_element=dep_element,
                            dependency_type='import',
                            line=node.lineno,
                            column=node.col_offset
                        )
                        self.dependency_handler(dependency)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if 'import_from' in self.dependency_types:
            for alias in node.names:
                name = alias.asname or alias.name
                dep_elements = self.name_to_elements.get(name, set())
                for dep_element in dep_elements:
                    for code_element in self.code_elements_in_file.values():
                        dependency = Dependency(
                            code_element=code_element,
                            depends_on_code_element=dep_element,
                            dependency_type='import_from',
                            line=node.lineno,
                            column=node.col_offset
                        )
                        self.dependency_handler(dependency)
        self.generic_visit(node)

    def visit_Name(self, node):
        if 'name_load' in self.dependency_types and self.current_code_element:
            if isinstance(node.ctx, ast.Load):
                name = node.id
                dep_elements = self.name_to_elements.get(name, set())
                for dep_element in dep_elements:
                    dependency = Dependency(
                        code_element=self.current_code_element,
                        depends_on_code_element=dep_element,
                        dependency_type='name_load',
                        line=node.lineno,
                        column=node.col_offset
                    )
                    self.dependency_handler(dependency)
        self.generic_visit(node)

    def _process_decorators(self, node):
        if self.current_code_element is None:
            return

        for decorator in node.decorator_list:
            decorator_name = self._get_full_name(decorator)
            if decorator_name is None:
                continue
            dep_elements = self.name_to_elements.get(decorator_name, set())
            for dep_element in dep_elements:
                dependency = Dependency(
                    code_element=self.current_code_element,
                    depends_on_code_element=dep_element,
                    dependency_type='decorator',
                    line=decorator.lineno,
                    column=decorator.col_offset
                )
                self.dependency_handler(dependency)

    def _process_annotation(self, annotation):
        if self.current_code_element is None:
            return

        annotation_name = self._get_full_name(annotation)
        if annotation_name is None:
            return
        dep_elements = self.name_to_elements.get(annotation_name, set())
        for dep_element in dep_elements:
            dependency = Dependency(
                code_element=self.current_code_element,
                depends_on_code_element=dep_element,
                dependency_type='type_annotation',
                line=getattr(annotation, 'lineno', 0),
                column=getattr(annotation, 'col_offset', 0)
            )
            self.dependency_handler(dependency)

    def _get_definition_full_name(self, node):
        parts = [node.name]
        parent = getattr(node, 'parent', None)
        while parent is not None:
            if isinstance(parent, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                parts.append(parent.name)
            parent = getattr(parent, 'parent', None)
        return ".".join(reversed(parts))

    def _get_full_name(self, node: Optional[ast.AST]) -> Optional[str]:
        if node is None:
            return None

        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_full_name(node.value)
            if value:
                return f"{value}.{node.attr}"
            else:
                return node.attr
        elif isinstance(node, ast.Call):
            return self._get_full_name(node.func)
        elif isinstance(node, ast.Subscript):
            return self._get_full_name(node.value)
        elif isinstance(node, ast.Index):
            return self._get_full_name(getattr(node, "value", None))
        elif isinstance(node, ast.Constant):
            return str(node.value)
        else:
            return None
