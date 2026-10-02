import ast
import logging
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from deply.models.code_element import CodeElement
from deply.models.dependency import Dependency


class DependencyVisitor(ast.NodeVisitor):
    def __init__(
            self,
            code_elements_in_file: Dict[str, CodeElement],
            dependency_types: List[str],
            dependency_handler: Callable[[Dependency], None],
            name_to_elements: Dict[str, Set[CodeElement]],
            dependency_resolver: Optional[Callable[[str, ast.AST], Set[CodeElement]]] = None,
            code_elements_by_location: Optional[Dict[Tuple[int, int], CodeElement]] = None,
    ):
        self.code_elements_in_file = code_elements_in_file
        self.dependency_types = dependency_types
        self.dependency_handler = dependency_handler
        self.name_to_elements = name_to_elements
        self.dependency_resolver = dependency_resolver
        self.code_elements_by_location = code_elements_by_location
        self.current_code_element: Optional[CodeElement] = None
        logging.debug(f"DependencyVisitor created for file with {len(code_elements_in_file)} code elements")

    def _get_definition_element(self, node: ast.AST) -> Optional[CodeElement]:
        if self.code_elements_by_location is not None:
            return self.code_elements_by_location.get((getattr(node, 'lineno', 0), getattr(node, 'col_offset', 0)))
        return self.code_elements_in_file.get(self._get_definition_full_name(node))

    def _emit_dependencies(
            self,
            name: Optional[str],
            node: ast.AST,
            dependency_type: str,
            sources: Optional[Iterable[CodeElement]] = None,
    ) -> None:
        if not name or dependency_type not in self.dependency_types:
            return
        source_elements = tuple(sources) if sources is not None else (
            (self.current_code_element,) if self.current_code_element is not None else ()
        )
        if not source_elements:
            return
        targets = (self.dependency_resolver(name, node) if self.dependency_resolver is not None
                   else self.name_to_elements.get(name, set()))
        for target in sorted(targets, key=lambda element: (
                str(element.file), element.name, element.line, element.column)):
            for source in source_elements:
                self.dependency_handler(Dependency(
                    code_element=source,
                    depends_on_code_element=target,
                    dependency_type=dependency_type,
                    line=getattr(node, 'lineno', 0),
                    column=getattr(node, 'col_offset', 0),
                ))

    def visit_FunctionDef(self, node):
        self._visit_function_definition(node)

    def visit_AsyncFunctionDef(self, node):
        self._visit_function_definition(node)

    def _visit_function_definition(self, node):
        previous_code_element = self.current_code_element
        self.current_code_element = self._get_definition_element(node)
        try:
            self._process_decorators(node)
            if node.returns:
                self._process_annotation(node.returns)
            arguments = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
            if node.args.vararg:
                arguments.append(node.args.vararg)
            if node.args.kwarg:
                arguments.append(node.args.kwarg)
            for argument in arguments:
                if argument.annotation:
                    self._process_annotation(argument.annotation)
            self.generic_visit(node)
        finally:
            self.current_code_element = previous_code_element

    def visit_ClassDef(self, node):
        previous_code_element = self.current_code_element
        self.current_code_element = self._get_definition_element(node)
        try:
            for base in node.bases:
                self._emit_dependencies(self._get_full_name(base), base, 'class_inheritance')
            self._process_decorators(node)
            for keyword in node.keywords:
                if keyword.arg == 'metaclass':
                    self._emit_dependencies(self._get_full_name(keyword.value), keyword.value, 'metaclass')
            self.generic_visit(node)
        finally:
            self.current_code_element = previous_code_element

    def visit_Call(self, node):
        self._emit_dependencies(self._get_full_name(node.func), node, 'function_call')
        self.generic_visit(node)

    def visit_Attribute(self, node):
        parent = getattr(node, 'parent', None)
        if not (isinstance(parent, ast.Attribute) or isinstance(parent, ast.Call) and parent.func is node):
            self._emit_dependencies(self._get_full_name(node), node, 'attribute_access')
        self.generic_visit(node)

    def visit_Import(self, node):
        sources = self._get_import_sources(node)
        for alias in node.names:
            name = alias.name if self.dependency_resolver is not None else alias.asname or alias.name.split('.')[0]
            self._emit_dependencies(name, node, 'import', sources)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        sources = self._get_import_sources(node)
        for alias in node.names:
            name = alias.name if self.dependency_resolver is not None else alias.asname or alias.name
            self._emit_dependencies(name, node, 'import_from', sources)
        self.generic_visit(node)

    def _get_import_sources(self, node: ast.AST) -> Iterable[CodeElement]:
        parent = getattr(node, 'parent', None)
        while parent is not None:
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                owner = self._get_definition_element(parent)
                return (owner,) if owner is not None else ()
            parent = getattr(parent, 'parent', None)
        if self.code_elements_by_location is not None:
            return self.code_elements_by_location.values()
        return self.code_elements_in_file.values()

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self._emit_dependencies(node.id, node, 'name_load')
        self.generic_visit(node)

    def visit_Assign(self, node):
        self._visit_assignment(node, node.targets)

    def visit_AnnAssign(self, node):
        self._visit_assignment(node, [node.target])

    def _visit_assignment(self, node, targets):
        parent = getattr(node, 'parent', None)
        while parent is not None:
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                self.generic_visit(node)
                return
            parent = getattr(parent, 'parent', None)
        previous_code_element = self.current_code_element
        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            if self.code_elements_by_location is not None:
                element = self.code_elements_by_location.get((target.lineno, target.col_offset))
            else:
                element = self.code_elements_in_file.get(target.id)
            self.current_code_element = element
            try:
                if isinstance(node, ast.AnnAssign):
                    self._process_annotation(node.annotation)
                    self.visit(node.annotation)
                if node.value is not None:
                    self.visit(node.value)
            finally:
                self.current_code_element = previous_code_element

    def _process_decorators(self, node):
        for decorator in node.decorator_list:
            self._emit_dependencies(self._get_full_name(decorator), decorator, 'decorator')

    def _process_annotation(self, annotation):
        self._emit_dependencies(self._get_full_name(annotation), annotation, 'type_annotation')

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
        if isinstance(node, ast.Attribute):
            value = self._get_full_name(node.value)
            return f"{value}.{node.attr}" if value else node.attr
        if isinstance(node, ast.Call):
            return self._get_full_name(node.func)
        if isinstance(node, ast.Subscript):
            return self._get_full_name(node.value)
        if isinstance(node, ast.Index):
            return self._get_full_name(getattr(node, "value", None))
        if isinstance(node, ast.Constant):
            return str(node.value)
        return None
