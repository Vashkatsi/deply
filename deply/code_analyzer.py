import ast
import logging
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from deply.models.code_element import CodeElement
from deply.models.dependency import Dependency
from deply.utils.ast_utils import parse_python_file, set_ast_parents
from deply.utils.dependency_visitor import DependencyVisitor
from deply.utils.module_resolver import ModuleResolver


class CodeAnalyzer:
    def __init__(
            self,
            code_elements: Set[CodeElement],
            dependency_handler: Callable[[Dependency], None],
            analysis_paths: Optional[List[Path]] = None,
            files: Optional[List[Path]] = None,
    ):
        self.code_elements = code_elements
        self.dependency_handler = dependency_handler
        self.analysis_paths = analysis_paths
        self.files = files or []
        self.dependency_types = [
            'import',
            'import_from',
            'function_call',
            'class_inheritance',
            'decorator',
            'type_annotation',
            'exception_handling',
            'metaclass',
            'attribute_access',
            'name_load',
        ]
        logging.debug(f"Initialized CodeAnalyzer with {len(self.code_elements)} code elements.")

    def analyze(self) -> List[str]:
        logging.debug("Starting analysis of code elements.")
        analysis_errors: List[str] = []
        file_to_elements: Dict[Path, Set[CodeElement]] = {}
        files = {file_path.resolve(): file_path for file_path in self.files}
        for code_element in self.code_elements:
            file_path = code_element.file.resolve()
            file_to_elements.setdefault(file_path, set()).add(code_element)
            files.setdefault(file_path, code_element.file)

        trees: Dict[Path, ast.AST] = {}
        for file_path, original_path in sorted(files.items()):
            try:
                tree, _ = parse_python_file(original_path)
                set_ast_parents(tree)
                trees[file_path] = tree
            except (OSError, SyntaxError, UnicodeError) as exception:
                analysis_errors.append(f"failed to analyze {original_path}: {exception}")
        if analysis_errors:
            return analysis_errors

        analysis_paths = self.analysis_paths
        if analysis_paths is None:
            analysis_paths = [Path(os.path.commonpath([str(file.parent) for file in files]))] if files else []
        resolver = ModuleResolver(trees, self.code_elements, analysis_paths)
        for file_path, elements_in_file in sorted(file_to_elements.items()):
            self._extract_dependencies_from_file(file_path, trees[file_path], elements_in_file, resolver)
        analysis_errors.extend(sorted(resolver.errors))
        logging.debug("Completed analysis of code elements.")
        return analysis_errors

    def _extract_dependencies_from_file(
            self,
            file_path: Path,
            tree: ast.AST,
            code_elements_in_file: Set[CodeElement],
            resolver: ModuleResolver,
    ) -> None:
        logging.debug(f"Extracting dependencies from file: {file_path}")
        elements_in_file_by_name = {elem.name: elem for elem in code_elements_in_file}

        visitor = DependencyVisitor(
            code_elements_in_file=elements_in_file_by_name,
            dependency_types=self.dependency_types,
            dependency_handler=self.dependency_handler,
            name_to_elements={},
            dependency_resolver=lambda name, node: resolver.resolve(file_path, node, name),
            code_elements_by_location={(elem.line, elem.column): elem for elem in code_elements_in_file},
        )
        logging.debug(f"Starting AST traversal for file: {file_path}")
        visitor.visit(tree)
        logging.debug(f"Completed AST traversal for file: {file_path}")
