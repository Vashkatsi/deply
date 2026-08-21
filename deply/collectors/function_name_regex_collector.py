import ast
import re
from pathlib import Path
from typing import Set, Dict

from deply.collectors import BaseCollector
from deply.models.code_element import CodeElement
from deply.utils.ast_utils import get_import_aliases, get_decorator_name, get_annotation_name


class FunctionNameRegexCollector(BaseCollector):
    def __init__(self, config: dict):
        self.regex_pattern = config.get("function_name_regex", "")
        self.exclude_files_regex_pattern = config.get("exclude_files_regex", "")
        self.regex = re.compile(self.regex_pattern)
        self.exclude_regex = re.compile(self.exclude_files_regex_pattern) if self.exclude_files_regex_pattern else None

    def match_in_file(self, file_ast: ast.AST, file_path: Path) -> Set[CodeElement]:
        if self.exclude_regex and self.exclude_regex.search(str(file_path)):
            return set()

        import_aliases = get_import_aliases(file_ast)
        functions = set()

        for node in ast.walk(file_ast):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self.regex.match(node.name):
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
                    # Positional args
                    for arg in node.args.args:
                        if arg.annotation is not None:
                            ann_name = get_annotation_name(arg.annotation, import_aliases)
                            if ann_name is not None:
                                type_ann_map[arg.arg] = ann_name
                    # Kw-only args
                    for arg in node.args.kwonlyargs:
                        if arg.annotation is not None:
                            ann_name = get_annotation_name(arg.annotation, import_aliases)
                            if ann_name is not None:
                                type_ann_map[arg.arg] = ann_name
                    # Pos-only args
                    if hasattr(node.args, 'posonlyargs'):
                        for arg in node.args.posonlyargs:
                            if arg.annotation is not None:
                                ann_name = get_annotation_name(arg.annotation, import_aliases)
                                if ann_name is not None:
                                    type_ann_map[arg.arg] = ann_name
                    # Vararg and kwarg
                    if node.args.vararg and node.args.vararg.annotation:
                        ann_name = get_annotation_name(node.args.vararg.annotation, import_aliases)
                        if ann_name is not None:
                            type_ann_map[node.args.vararg.arg] = ann_name
                    if node.args.kwarg and node.args.kwarg.annotation:
                        ann_name = get_annotation_name(node.args.kwarg.annotation, import_aliases)
                        if ann_name is not None:
                            type_ann_map[node.args.kwarg.arg] = ann_name

                    code_element = CodeElement(
                        file=file_path,
                        name=full_name,
                        element_type='function',
                        line=node.lineno,
                        column=node.col_offset,
                        inherits=tuple(),  # Functions do not inherit
                        decorators=tuple(decorators_list),
                        return_annotation=return_annotation,
                        type_annotations=frozenset(type_ann_map.items())
                    )
                    functions.add(code_element)

        return functions

    def _get_full_name(self, node):
        names = []
        current = node
        while current is not None:
            if isinstance(current, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(current.name)
            current = getattr(current, 'parent', None)
        return '.'.join(reversed(names))
