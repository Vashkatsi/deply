import ast
import logging
import os
from importlib.util import resolve_name
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from deply.models.code_element import CodeElement
from deply.models.dependency import Dependency
from deply.utils.ast_utils import parse_python_file, set_ast_parents
from deply.utils.dependency_visitor import DependencyVisitor


class CodeAnalyzer:
    def __init__(
            self,
            code_elements: Set[CodeElement],
            dependency_handler: Callable[[Dependency], None],
            analysis_paths: Optional[List[Path]] = None,
    ):
        self.code_elements = code_elements
        self.dependency_handler = dependency_handler
        self.analysis_paths = analysis_paths or self._infer_analysis_paths()
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
        symbol_to_elements = self._build_symbol_index()
        logging.debug(f"Symbol index built with {len(symbol_to_elements)} identities.")
        analysis_errors: List[str] = []

        file_to_elements: Dict[Path, Set[CodeElement]] = {}
        for code_element in self.code_elements:
            file_to_elements.setdefault(code_element.file, set()).add(code_element)

        for file_path, elements_in_file in file_to_elements.items():
            logging.debug(f"Analyzing file: {file_path} with {len(elements_in_file)} code elements")
            analysis_errors.extend(
                self._extract_dependencies_from_file(
                    file_path,
                    elements_in_file,
                    symbol_to_elements,
                )
            )
        logging.debug("Completed analysis of code elements.")
        return analysis_errors

    def _infer_analysis_paths(self) -> List[Path]:
        if not self.code_elements:
            return []
        common_path = Path(os.path.commonpath([str(element.file.resolve()) for element in self.code_elements]))
        return [common_path.parent if common_path.suffix == ".py" else common_path]

    def _build_symbol_index(self) -> Dict[str, Set[CodeElement]]:
        canonical_symbols: Dict[str, Set[CodeElement]] = {}
        fallback_symbols: Dict[str, Set[CodeElement]] = {}
        for element in self.code_elements:
            canonical_module = self._get_module_name(element.file)
            canonical_symbol = (
                f"{canonical_module}.{element.name}"
                if canonical_module
                else element.name
            )
            canonical_symbols.setdefault(canonical_symbol, set()).add(element)
            for module_name in self._get_module_names(element.file) - {canonical_module}:
                fallback_symbol = f"{module_name}.{element.name}"
                fallback_symbols.setdefault(fallback_symbol, set()).add(element)
        return {**fallback_symbols, **canonical_symbols}

    def _get_module_name(self, file_path: Path) -> str:
        analysis_root = self._get_analysis_root(file_path)
        if analysis_root is None:
            return file_path.stem

        resolved_file = file_path.resolve()
        module_parts = list(resolved_file.relative_to(analysis_root).with_suffix("").parts)
        if module_parts and module_parts[-1] == "__init__":
            module_parts.pop()
        if (analysis_root / "__init__.py").is_file():
            module_parts.insert(0, analysis_root.name)
        return ".".join(module_parts)

    def _get_module_names(self, file_path: Path) -> Set[str]:
        module_name = self._get_module_name(file_path)
        module_names = {module_name}
        analysis_root = self._get_analysis_root(file_path)
        if (
                analysis_root is None
                or (analysis_root / "__init__.py").is_file()
                or not module_name
        ):
            return module_names

        root_name = analysis_root.name
        if module_name != root_name and not module_name.startswith(f"{root_name}."):
            module_names.add(f"{root_name}.{module_name}")
        return module_names

    def _get_analysis_root(self, file_path: Path) -> Optional[Path]:
        resolved_file = file_path.resolve()
        matching_paths = []
        for analysis_path in self.analysis_paths:
            resolved_path = analysis_path.resolve()
            try:
                resolved_file.relative_to(resolved_path)
            except ValueError:
                continue
            matching_paths.append(resolved_path)

        if not matching_paths:
            return None
        return max(matching_paths, key=lambda path: len(path.parts))

    def _build_file_name_map(
            self,
            tree,
            file_path: Path,
            code_elements_in_file: Set[CodeElement],
            symbol_to_elements: Dict[str, Set[CodeElement]],
            analysis_errors: List[str],
    ) -> Tuple[
        Dict[str, Set[CodeElement]],
        Dict[Tuple[int, int], Dict[str, Set[CodeElement]]],
        Dict[Tuple[int, int], Set[CodeElement]],
    ]:
        name_to_elements: Dict[str, Set[CodeElement]] = {}
        local_import_bindings: Dict[Tuple[int, int], Dict[str, Set[CodeElement]]] = {}
        import_dependencies: Dict[Tuple[int, int], Set[CodeElement]] = {}
        for element in code_elements_in_file:
            name_to_elements.setdefault(element.name, set()).add(element)

        module_name = self._get_module_name(file_path)
        module_names = [
            module_name,
            *sorted(self._get_module_names(file_path) - {module_name}),
        ]
        package_names = []
        for current_module_name in module_names:
            package_name = (
                current_module_name
                if file_path.name == "__init__.py"
                else current_module_name.rpartition(".")[0]
            )
            if package_name not in package_names:
                package_names.append(package_name)
        import_nodes = sorted(
            (
                node
                for node in DependencyVisitor._walk_reachable(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
            ),
            key=lambda node: (node.lineno, node.col_offset),
        )
        for node in import_nodes:
            bindings, dependencies = self._get_import_bindings(
                node,
                package_names,
                file_path,
                symbol_to_elements,
                analysis_errors,
            )
            import_dependencies[(node.lineno, node.col_offset)] = dependencies
            local_import_bindings[(node.lineno, node.col_offset)] = bindings

        module_binding_visitor = DependencyVisitor(
            code_elements_in_file={
                element.name: element
                for element in code_elements_in_file
            },
            dependency_types=[],
            dependency_handler=lambda _dependency: None,
            name_to_elements=name_to_elements,
            local_import_bindings=local_import_bindings,
        )
        module_binding_visitor.visit(tree)
        for binding_name in module_binding_visitor.module_binding_names:
            self._remove_name_bindings(name_to_elements, binding_name)
        name_to_elements.update(module_binding_visitor.final_module_bindings)
        return name_to_elements, local_import_bindings, import_dependencies

    def _get_import_bindings(
            self,
            node,
            package_names: List[str],
            file_path: Path,
            symbol_to_elements: Dict[str, Set[CodeElement]],
            analysis_errors: List[str],
    ) -> Tuple[Dict[str, Set[CodeElement]], Set[CodeElement]]:
        bindings: Dict[str, Set[CodeElement]] = {}
        dependencies: Set[CodeElement] = set()
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]
                binding_name = local_name if alias.asname else alias.name
                self._remove_name_bindings(bindings, local_name)
                self._add_module_binding(
                    bindings,
                    binding_name,
                    alias.name,
                    file_path,
                    symbol_to_elements,
                    analysis_errors,
                )
                imported_elements = self._resolve_module(
                    alias.name,
                    file_path,
                    symbol_to_elements,
                    analysis_errors,
                )
                if imported_elements:
                    dependencies.update(imported_elements)
            return bindings, dependencies

        imported_module = node.module or ""
        if node.level:
            relative_import = f"{'.' * node.level}{imported_module}"
            resolution_errors = []
            for package_name in package_names:
                try:
                    imported_module = resolve_name(relative_import, package_name)
                    break
                except (ImportError, ValueError) as exception:
                    resolution_errors.append(exception)
            else:
                analysis_errors.append(
                    f"failed to resolve relative import '{relative_import}' "
                    f"in {file_path}:{node.lineno}: {resolution_errors[0]}"
                )
                return bindings, dependencies

        for alias in node.names:
            if alias.name == "*":
                continue
            local_name = alias.asname or alias.name
            self._remove_name_bindings(bindings, local_name)
            imported_name = f"{imported_module}.{alias.name}" if imported_module else alias.name
            imported_elements = self._resolve_symbol(
                imported_name,
                file_path,
                symbol_to_elements,
                analysis_errors,
            )
            if imported_elements:
                bindings[local_name] = imported_elements
                dependencies.update(imported_elements)
                if any(
                        element.element_type == "class"
                        for element in imported_elements
                ):
                    self._add_class_member_bindings(
                        bindings,
                        local_name,
                        imported_name,
                        file_path,
                        symbol_to_elements,
                        analysis_errors,
                    )
            else:
                self._add_module_binding(
                    bindings,
                    local_name,
                    imported_name,
                    file_path,
                    symbol_to_elements,
                    analysis_errors,
                )
                imported_elements = self._resolve_module(
                    imported_name,
                    file_path,
                    symbol_to_elements,
                    analysis_errors,
                )
                if imported_elements:
                    dependencies.update(imported_elements)
        return bindings, dependencies

    def _add_class_member_bindings(
            self,
            bindings: Dict[str, Set[CodeElement]],
            local_name: str,
            imported_class: str,
            file_path: Path,
            symbol_to_elements: Dict[str, Set[CodeElement]],
            analysis_errors: List[str],
    ) -> None:
        member_prefix = f"{imported_class}."
        for symbol_name in symbol_to_elements:
            if not symbol_name.startswith(member_prefix):
                continue
            elements = self._resolve_symbol(
                symbol_name,
                file_path,
                symbol_to_elements,
                analysis_errors,
            )
            if not elements:
                continue
            local_symbol = f"{local_name}.{symbol_name[len(member_prefix):]}"
            bindings.setdefault(local_symbol, set()).update(elements)

    @staticmethod
    def _remove_name_bindings(
            bindings: Dict[str, Set[CodeElement]],
            name: str,
    ) -> None:
        binding_prefix = f"{name}."
        for binding_name in list(bindings):
            if binding_name == name or binding_name.startswith(binding_prefix):
                bindings.pop(binding_name)

    def _add_module_binding(
            self,
            name_to_elements: Dict[str, Set[CodeElement]],
            local_name: str,
            imported_module: str,
            file_path: Path,
            symbol_to_elements: Dict[str, Set[CodeElement]],
            analysis_errors: List[str],
    ) -> None:
        imported_prefix = f"{imported_module}."
        for symbol_name in symbol_to_elements:
            if symbol_name.startswith(imported_prefix):
                symbol_elements = symbol_to_elements[symbol_name]
                if not any(
                        imported_module in self._get_module_names(element.file)
                        for element in symbol_elements
                ):
                    continue
                local_symbol = f"{local_name}.{symbol_name[len(imported_prefix):]}"
                elements = self._resolve_symbol(
                    symbol_name,
                    file_path,
                    symbol_to_elements,
                    analysis_errors,
                )
                if elements:
                    name_to_elements.setdefault(local_symbol, set()).update(elements)

    def _resolve_symbol(
            self,
            symbol_name: str,
            file_path: Path,
            symbol_to_elements: Dict[str, Set[CodeElement]],
            analysis_errors: List[str],
    ) -> Set[CodeElement]:
        elements = symbol_to_elements.get(symbol_name, set())
        if not elements:
            return set()

        analysis_root = self._get_analysis_root(file_path)
        same_root_elements = {
            element
            for element in elements
            if self._get_analysis_root(element.file) == analysis_root
        }
        candidates = same_root_elements or elements
        if len({element.file.resolve() for element in candidates}) == 1:
            return candidates

        matching_files = ", ".join(sorted(str(element.file) for element in candidates))
        analysis_error = (
            f"ambiguous internal import '{symbol_name}' in {file_path}: "
            f"matches {matching_files}"
        )
        if analysis_error not in analysis_errors:
            analysis_errors.append(analysis_error)
        return set()

    def _resolve_module(
            self,
            module_name: str,
            file_path: Path,
            symbol_to_elements: Dict[str, Set[CodeElement]],
            analysis_errors: List[str],
    ) -> Set[CodeElement]:
        module_elements: Set[CodeElement] = set()
        module_prefix = f"{module_name}."
        for symbol_name in symbol_to_elements:
            if symbol_name.startswith(module_prefix):
                symbol_elements = symbol_to_elements[symbol_name]
                if not any(
                        module_name in self._get_module_names(element.file)
                        for element in symbol_elements
                ):
                    continue
                module_elements.update(
                    self._resolve_symbol(
                        symbol_name,
                        file_path,
                        symbol_to_elements,
                        analysis_errors,
                    )
                )
        return module_elements

    def _extract_dependencies_from_file(
            self,
            file_path: Path,
            code_elements_in_file: Set[CodeElement],
            symbol_to_elements: Dict[str, Set[CodeElement]],
    ) -> List[str]:
        logging.debug(f"Extracting dependencies from file: {file_path}")
        try:
            tree, _ = parse_python_file(file_path)
            set_ast_parents(tree)
            logging.debug(f"AST parsing completed for {file_path}.")
        except (OSError, SyntaxError, UnicodeError) as exception:
            return [f"failed to analyze {file_path}: {exception}"]

        elements_in_file_by_name = {elem.name: elem for elem in code_elements_in_file}
        analysis_errors: List[str] = []
        name_to_elements, local_import_bindings, import_dependencies = self._build_file_name_map(
            tree,
            file_path,
            code_elements_in_file,
            symbol_to_elements,
            analysis_errors,
        )
        if analysis_errors:
            return analysis_errors

        visitor = DependencyVisitor(
            code_elements_in_file=elements_in_file_by_name,
            dependency_types=self.dependency_types,
            dependency_handler=self.dependency_handler,
            name_to_elements=name_to_elements,
            local_import_bindings=local_import_bindings,
            import_dependencies=import_dependencies,
        )
        logging.debug(f"Starting AST traversal for file: {file_path}")
        visitor.visit(tree)
        logging.debug(f"Completed AST traversal for file: {file_path}")
        return []
