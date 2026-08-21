import ast
import re
from pathlib import Path
from typing import List, Set, Dict

from deply.collectors import BaseCollector
from deply.models.code_element import CodeElement
from deply.utils.ast_utils import get_import_aliases, get_base_name, get_decorator_name, get_annotation_name, \
    set_ast_parents


class FileRegexCollector(BaseCollector):
    def __init__(self, config: dict, paths: List[str], exclude_files: List[str]):
        self.regex_pattern = config.get("regex", "")
        self.exclude_files_regex_pattern = config.get("exclude_files_regex", "")
        self.element_type = config.get("element_type", "")  # 'class', 'function', 'variable'
        self.regex = re.compile(self.regex_pattern)
        self.exclude_regex = re.compile(self.exclude_files_regex_pattern) if self.exclude_files_regex_pattern else None

        self.paths = [Path(p) for p in paths]
        self.exclude_files = [re.compile(pattern) for pattern in exclude_files]

    def match_in_file(self, file_ast: ast.AST, file_path: Path) -> Set[CodeElement]:
        # Mark parent pointers so we can detect if a node is inside a class
        set_ast_parents(file_ast)

        # Check global exclude patterns
        if any(pattern.search(str(file_path)) for pattern in self.exclude_files):
            return set()

        # Check collector-specific exclude pattern
        if self.exclude_regex and self.exclude_regex.search(str(file_path)):
            return set()

        # Check if file matches the given regex
        matched = False
        for base_path in self.paths:
            try:
                relative_path = str(file_path.relative_to(base_path))
                if self.regex.match(relative_path):
                    matched = True
                    break
            except ValueError:
                pass

        # Fallback: check full path
        if not matched and self.regex.match(str(file_path)):
            matched = True

        if not matched:
            return set()

        import_aliases = get_import_aliases(file_ast)
        elements = set()

        if not self.element_type or self.element_type == 'class':
            elements.update(self.get_classes(file_ast, file_path, import_aliases))
        if not self.element_type or self.element_type == 'function':
            elements.update(self.get_functions(file_ast, file_path, import_aliases))
        if not self.element_type or self.element_type == 'variable':
            elements.update(self.get_variables(file_ast, file_path, import_aliases))

        return elements

    def get_classes(self, tree: ast.AST, file_path: Path, import_aliases: Dict[str, str]) -> Set[CodeElement]:
        classes = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                full_name = self._get_full_name(node)

                # Inherits
                inherits_list = []
                for base in node.bases:
                    base_name = get_base_name(base, import_aliases)
                    inherits_list.append(base_name)

                # Decorators
                decorators_list = []
                for d in node.decorator_list:
                    dec_name = get_decorator_name(d)
                    if dec_name is not None:
                        decorators_list.append(dec_name)

                # Class-level type annotations
                type_annotations_map: Dict[str, str] = {}
                for stmt in node.body:
                    # We skip AnnAssign fields here because we only want them
                    # if "element_type" is specifically asked for 'variable' or if we
                    # want them stored as part of the class. But let's keep ignoring
                    # them for the 'class' code element.
                    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                        ann_name = get_annotation_name(stmt.annotation, import_aliases)
                        if ann_name is not None:
                            type_annotations_map[stmt.target.id] = ann_name

                code_element = CodeElement(
                    file=file_path,
                    name=full_name,
                    element_type='class',
                    line=node.lineno,
                    column=node.col_offset,
                    inherits=tuple(inherits_list),
                    decorators=tuple(decorators_list),
                    return_annotation=None,
                    type_annotations=frozenset(type_annotations_map.items())
                )
                classes.add(code_element)
        return classes

    def get_functions(self, tree: ast.AST, file_path: Path, import_aliases: Dict[str, str]) -> Set[CodeElement]:
        functions = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                full_name = self._get_full_name(node)

                # Decorators
                decorators_list = []
                for d in node.decorator_list:
                    dec_name = get_decorator_name(d)
                    if dec_name is not None:
                        decorators_list.append(dec_name)

                # Return annotation
                if getattr(node, 'returns', None):
                    return_annotation = get_annotation_name(node.returns, import_aliases)
                else:
                    return_annotation = None

                # Parameter type annotations
                type_ann_map: Dict[str, str] = {}
                # gather function param type annotations
                for arg in node.args.args + node.args.kwonlyargs:
                    if arg.annotation is not None:
                        ann_name = get_annotation_name(arg.annotation, import_aliases)
                        if ann_name:
                            type_ann_map[arg.arg] = ann_name
                if hasattr(node.args, 'posonlyargs'):
                    for arg in node.args.posonlyargs:
                        if arg.annotation:
                            ann_name = get_annotation_name(arg.annotation, import_aliases)
                            if ann_name:
                                type_ann_map[arg.arg] = ann_name
                if node.args.vararg and node.args.vararg.annotation:
                    ann_name = get_annotation_name(node.args.vararg.annotation, import_aliases)
                    if ann_name:
                        type_ann_map[node.args.vararg.arg] = ann_name
                if node.args.kwarg and node.args.kwarg.annotation:
                    ann_name = get_annotation_name(node.args.kwarg.annotation, import_aliases)
                    if ann_name:
                        type_ann_map[node.args.kwarg.arg] = ann_name

                code_element = CodeElement(
                    file=file_path,
                    name=full_name,
                    element_type='function',
                    line=node.lineno,
                    column=node.col_offset,
                    inherits=(),
                    decorators=tuple(decorators_list),
                    return_annotation=return_annotation,
                    type_annotations=frozenset(type_ann_map.items())
                )
                functions.add(code_element)
        return functions

    def get_variables(self, tree: ast.AST, file_path: Path, import_aliases: Dict[str, str]) -> Set[CodeElement]:
        """Collect only top-level variables (not inside a class)."""
        variables = set()

        def in_classdef(n: ast.AST) -> bool:
            parent = getattr(n, 'parent', None)
            while parent is not None:
                if isinstance(parent, ast.ClassDef):
                    return True
                parent = getattr(parent, 'parent', None)
            return False

        for node in ast.walk(tree):
            # Annotated variable
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if in_classdef(node):
                    # skip class fields
                    continue
                ann_name = get_annotation_name(node.annotation, import_aliases)
                type_ann_map = {node.target.id: ann_name} if ann_name else {}
                code_element = CodeElement(
                    file=file_path,
                    name=node.target.id,
                    element_type='variable',
                    line=node.lineno,
                    column=node.col_offset,
                    inherits=(),
                    decorators=(),
                    return_annotation=None,
                    type_annotations=frozenset(type_ann_map.items())
                )
                variables.add(code_element)
            # Un-annotated variable
            elif isinstance(node, ast.Assign):
                if in_classdef(node):
                    # skip class fields
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        code_element = CodeElement(
                            file=file_path,
                            name=target.id,
                            element_type='variable',
                            line=target.lineno,
                            column=target.col_offset,
                            inherits=(),
                            decorators=(),
                            return_annotation=None,
                            type_annotations=frozenset()
                        )
                        variables.add(code_element)
        return variables

    def _get_full_name(self, node):
        names = []
        current = node
        while current is not None:
            if isinstance(current, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(current.name)
            current = getattr(current, 'parent', None)
        return '.'.join(reversed(names)) if names else ''
