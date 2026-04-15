import ast
import logging
from pathlib import Path
from typing import Dict, Set, Callable

from deply.models.code_element import CodeElement
from deply.models.dependency import Dependency
from deply.utils.ast_utils import set_ast_parents
from deply.utils.dependency_visitor import DependencyVisitor


class CodeAnalyzer:
    def __init__(
            self,
            code_elements: Set[CodeElement],
            dependency_handler: Callable[[Dependency], None],
    ):
        self.code_elements = code_elements
        self.dependency_handler = dependency_handler
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

    def analyze(self) -> None:
        logging.debug("Starting analysis of code elements.")
        name_to_elements = self._build_name_to_element_map()
        logging.debug(f"Name to elements map built with {len(name_to_elements)} names.")

        file_to_elements: Dict[Path, Set[CodeElement]] = {}
        for code_element in self.code_elements:
            file_to_elements.setdefault(code_element.file, set()).add(code_element)

        for file_path, elements_in_file in file_to_elements.items():
            logging.debug(f"Analyzing file: {file_path} with {len(elements_in_file)} code elements")
            self._extract_dependencies_from_file(file_path, elements_in_file, name_to_elements)
        logging.debug("Completed analysis of code elements.")

    def _build_name_to_element_map(self) -> Dict[str, Set[CodeElement]]:
        logging.debug("Building name to element map.")
        name_to_element: Dict[str, Set[CodeElement]] = {}
        for elem in self.code_elements:
            name_to_element.setdefault(elem.name, set()).add(elem)
        logging.debug(f"Name to element map contains {len(name_to_element)} entries.")
        return name_to_element

    def _extract_dependencies_from_file(
            self,
            file_path: Path,
            code_elements_in_file: Set[CodeElement],
            name_to_elements: Dict[str, Set[CodeElement]]
    ) -> None:
        logging.debug(f"Extracting dependencies from file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            logging.debug(f"File {file_path} read successfully.")
            tree = ast.parse(source_code, filename=str(file_path))
            set_ast_parents(tree)
            logging.debug(f"AST parsing completed for {file_path}.")
        except (SyntaxError, FileNotFoundError, UnicodeDecodeError) as e:
            logging.warning(f"Failed to parse {file_path}: {e}")
            return

        elements_in_file_by_name = {elem.name: elem for elem in code_elements_in_file}

        visitor = DependencyVisitor(
            code_elements_in_file=elements_in_file_by_name,
            dependency_types=self.dependency_types,
            dependency_handler=self.dependency_handler,
            name_to_elements=name_to_elements,
        )
        logging.debug(f"Starting AST traversal for file: {file_path}")
        visitor.visit(tree)
        logging.debug(f"Completed AST traversal for file: {file_path}")
