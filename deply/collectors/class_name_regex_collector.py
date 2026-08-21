import ast
import re
from pathlib import Path
from typing import List, Set, Dict

from deply.collectors import BaseCollector
from deply.models.code_element import CodeElement
from deply.utils.ast_utils import get_import_aliases, get_base_name, get_decorator_name, get_annotation_name


class ClassNameRegexCollector(BaseCollector):
    def __init__(self, config: dict, paths: List[str], exclude_files: List[str]):
        self.regex_pattern = config.get("class_name_regex", "")
        self.exclude_files_regex_pattern = config.get("exclude_files_regex", "")
        self.regex = re.compile(self.regex_pattern)
        self.exclude_regex = re.compile(self.exclude_files_regex_pattern) if self.exclude_files_regex_pattern else None

        self.paths = [Path(p) for p in paths]
        self.exclude_files = [re.compile(pattern) for pattern in exclude_files]

    def match_in_file(self, file_ast: ast.AST, file_path: Path) -> Set[CodeElement]:
        if self.exclude_regex and self.exclude_regex.search(str(file_path)):
            return set()

        import_aliases = get_import_aliases(file_ast)
        classes = set()

        for node in ast.walk(file_ast):
            if isinstance(node, ast.ClassDef):
                if self.regex.match(node.name):
                    # Gather inherits
                    inherits_list = []
                    for base in node.bases:
                        base_name = get_base_name(base, import_aliases)
                        inherits_list.append(base_name)

                    # Gather decorators
                    decorators_list = []
                    for d in node.decorator_list:
                        dec_name = get_decorator_name(d)
                        if dec_name is not None:
                            decorators_list.append(dec_name)

                    # Gather type annotations (class-level attributes)
                    type_annotations: Dict[str, str] = {}
                    for stmt in node.body:
                        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                            ann_name = get_annotation_name(stmt.annotation, import_aliases)
                            if ann_name is not None:
                                type_annotations[stmt.target.id] = ann_name

                    full_name = self._get_full_name(node)
                    code_element = CodeElement(
                        file=file_path,
                        name=full_name,
                        element_type='class',
                        line=node.lineno,
                        column=node.col_offset,
                        inherits=tuple(inherits_list),
                        decorators=tuple(decorators_list),
                        return_annotation=None,  # Classes do not have return annotations
                        type_annotations=frozenset(type_annotations.items())
                    )
                    classes.add(code_element)
        return classes

    def _get_full_name(self, node):
        names = []
        current = node
        while current is not None:
            if isinstance(current, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(current.name)
            current = getattr(current, 'parent', None)
        return '.'.join(reversed(names))
