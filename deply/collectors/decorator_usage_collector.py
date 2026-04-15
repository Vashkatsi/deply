import ast
import re
from pathlib import Path
from typing import Set, Dict

from deply.collectors import BaseCollector
from deply.models.code_element import CodeElement
from deply.utils.ast_utils import get_import_aliases, get_base_name, get_decorator_name, get_annotation_name


class DecoratorUsageCollector(BaseCollector):
    def __init__(self, config: dict):
        self.decorator_name = config.get("decorator_name", "")
        self.decorator_regex_pattern = config.get("decorator_regex", "")
        self.exclude_files_regex_pattern = config.get("exclude_files_regex", "")
        self.decorator_regex = re.compile(self.decorator_regex_pattern) if self.decorator_regex_pattern else None
        self.exclude_regex = re.compile(self.exclude_files_regex_pattern) if self.exclude_files_regex_pattern else None

    def match_in_file(self, file_ast: ast.AST, file_path: Path) -> Set[CodeElement]:
        if self.exclude_regex and self.exclude_regex.search(str(file_path)):
            return set()

        import_aliases = get_import_aliases(file_ast)
        elements = set()

        for node in ast.walk(file_ast):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                decorators_list = []
                matched = False
                for dec_node in node.decorator_list:
                    d_name = get_decorator_name(dec_node)
                    if d_name is not None:
                        decorators_list.append(d_name)
                        if (self.decorator_name and d_name == self.decorator_name) or \
                                (self.decorator_regex and self.decorator_regex.match(d_name)):
                            matched = True

                if not matched:
                    continue

                full_name = self._get_full_name(node)
                type_annotations: Dict[str, str] = {}

                if isinstance(node, ast.ClassDef):
                    element_type = 'class'
                    inherits_list = []
                    for base in node.bases:
                        base_name = get_base_name(base, import_aliases)
                        inherits_list.append(base_name)

                    return_annotation = None
                    for stmt in node.body:
                        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                            ann_name = get_annotation_name(stmt.annotation, import_aliases)
                            if ann_name is not None:
                                type_annotations[stmt.target.id] = ann_name

                else:
                    element_type = 'function'
                    inherits_list = []
                    if getattr(node, 'returns', None):
                        return_annotation = get_annotation_name(node.returns, import_aliases)
                    else:
                        return_annotation = None

                    for arg in node.args.args:
                        if arg.annotation is not None:
                            ann_name = get_annotation_name(arg.annotation, import_aliases)
                            if ann_name is not None:
                                type_annotations[arg.arg] = ann_name
                    for arg in node.args.kwonlyargs:
                        if arg.annotation is not None:
                            ann_name = get_annotation_name(arg.annotation, import_aliases)
                            if ann_name is not None:
                                type_annotations[arg.arg] = ann_name
                    if hasattr(node.args, 'posonlyargs'):
                        for arg in node.args.posonlyargs:
                            if arg.annotation is not None:
                                ann_name = get_annotation_name(arg.annotation, import_aliases)
                                if ann_name is not None:
                                    type_annotations[arg.arg] = ann_name
                    if node.args.vararg and node.args.vararg.annotation:
                        ann_name = get_annotation_name(node.args.vararg.annotation, import_aliases)
                        if ann_name is not None:
                            type_annotations[node.args.vararg.arg] = ann_name
                    if node.args.kwarg and node.args.kwarg.annotation:
                        ann_name = get_annotation_name(node.args.kwarg.annotation, import_aliases)
                        if ann_name is not None:
                            type_annotations[node.args.kwarg.arg] = ann_name

                code_element = CodeElement(
                    file=file_path,
                    name=full_name,
                    element_type=element_type,
                    line=node.lineno,
                    column=node.col_offset,
                    decorators=tuple(decorators_list),
                    inherits=tuple(inherits_list),
                    return_annotation=return_annotation,
                    type_annotations=frozenset(type_annotations.items())
                )
                elements.add(code_element)

        return elements

    def _get_full_name(self, node):
        names = []
        current = node
        while isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(current.name)
            current = getattr(current, 'parent', None)
        return '.'.join(reversed(names))
