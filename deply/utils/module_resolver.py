import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

from deply.models.code_element import CodeElement


_DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_FUNCTION_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda) + _COMPREHENSIONS


class _Binding(NamedTuple):
    node: ast.AST
    name: str


class _Reference(NamedTuple):
    module: str
    node: Optional[ast.AST] = None
    loaded_modules: Tuple[str, ...] = ()


@dataclass
class _Scope:
    node: ast.AST
    file: Path
    parent: Optional['_Scope']
    bindings: Dict[str, List[_Binding]] = field(default_factory=dict)
    globals: Set[str] = field(default_factory=set)
    nonlocals: Set[str] = field(default_factory=set)
    star_imports: List[ast.AST] = field(default_factory=list)
    type_parameters: Set[str] = field(default_factory=set)


class ModuleResolver:
    def __init__(
        self,
        trees: Dict[Path, ast.AST],
        code_elements: Set[CodeElement],
        analysis_paths: List[Path],
    ):
        self.trees = {file_path.resolve(): tree for file_path, tree in trees.items()}
        self.errors: Set[str] = set()
        self._modules: Dict[str, Set[Path]] = {}
        self._module_directories: Dict[str, Set[Path]] = {}
        self._regular_packages: Dict[str, Set[Path]] = {}
        self._resolved_module_paths: Dict[str, Set[Path]] = {}
        self._module_names: Set[str] = set()
        self._file_modules: Dict[Path, str] = {}
        self._scopes: Dict[ast.AST, _Scope] = {}
        self._node_scopes: Dict[ast.AST, _Scope] = {}
        self._elements: Dict[ast.AST, Set[CodeElement]] = {}
        self._future_annotations = {
            file_path for file_path, tree in self.trees.items()
            if any(isinstance(node, ast.ImportFrom) and node.module == '__future__'
                   and any(alias.name == 'annotations' for alias in node.names) for node in ast.iter_child_nodes(tree))
        }
        elements_by_location: Dict[Tuple[Path, int, int], Set[CodeElement]] = {}
        for element in code_elements:
            location = (element.file.resolve(), element.line, element.column)
            elements_by_location.setdefault(location, set()).add(element)
        self._index_modules(analysis_paths)
        for file_path, tree in self.trees.items():
            scope = _Scope(tree, file_path, None)
            self._scopes[tree] = scope
            self._index_node(tree, scope)
            for node in ast.walk(tree):
                location = (file_path, getattr(node, 'lineno', 0), getattr(node, 'col_offset', 0))
                if isinstance(node, _DEFINITIONS) or isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    self._elements[node] = elements_by_location.get(location, set())

    def resolve(self, file_path: Path, node: ast.AST, name: str) -> Set[CodeElement]:
        file_path = file_path.resolve()
        if file_path not in self.trees or not name:
            return set()
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            references = self._import_references(file_path, node, name, set(), direct=True)
            return self._reference_elements(references, expand_modules=True)
        scope = self._node_scopes.get(node)
        if scope is None or not self._has_static_root(node):
            return set()
        parts = name.split('.')
        references = self._lookup(scope, parts[0], node, set())
        elements = self._reference_elements(references)
        for member in parts[1:]:
            references = self._members(references, member, set())
            if not references:
                break
            member_elements = self._reference_elements(references)
            if member_elements:
                elements = member_elements
        return elements

    def _index_modules(self, analysis_paths: List[Path]) -> None:
        roots: Set[Path] = set()
        scan_paths = {analysis_path.resolve() for analysis_path in analysis_paths}
        scan_paths = {path for path in scan_paths if not any(parent in scan_paths for parent in path.parents)}
        for directory in scan_paths:
            if directory.is_file():
                directory = directory.parent
            while (directory / '__init__.py') in self.trees or (directory / '__init__.py').is_file():
                directory = directory.parent
            roots.add(directory)
            source_directory = directory / 'src'
            if source_directory.is_dir() and not (source_directory / '__init__.py').is_file():
                roots.add(source_directory)
        if not roots and self.trees:
            roots.update(file_path.parent for file_path in self.trees)
        for file_path in self.trees:
            containing_roots = [root for root in roots if root == file_path.parent or root in file_path.parents]
            if not containing_roots:
                continue
            root = max(containing_roots, key=lambda candidate: len(candidate.parts))
            parts = list(file_path.relative_to(root).with_suffix('').parts)
            if parts[-1] == '__init__':
                parts.pop()
            module_name = '.'.join(parts)
            if not module_name:
                continue
            self._file_modules[file_path] = module_name
            self._modules.setdefault(module_name, set()).add(file_path)
            for length in range(1, len(parts) + 1):
                parent_module = '.'.join(parts[:length])
                self._module_names.add(parent_module)
                if length < len(parts) or file_path.name == '__init__.py':
                    directory = root.joinpath(*parts[:length])
                    self._module_directories.setdefault(parent_module, set()).add(directory)
        for module_name in self._module_names:
            for root in roots:
                directory = root.joinpath(*module_name.split('.'))
                if (directory / '__init__.py').is_file():
                    self._regular_packages.setdefault(module_name, set()).add(directory)

    def _bind(self, scope: _Scope, name: str, node: ast.AST) -> None:
        scope.bindings.setdefault(name, []).append(_Binding(node, name))

    def _index_node(self, node: ast.AST, scope: _Scope) -> None:
        self._node_scopes[node] = scope
        if isinstance(node, _DEFINITIONS):
            self._bind(scope, node.name, node)
            type_parameters = getattr(node, 'type_params', [])
            annotation_scope = (
                _Scope(ast.AST(), scope.file, scope,
                       type_parameters={parameter.name for parameter in type_parameters})
                if type_parameters else scope
            )
            inner_scope = _Scope(node, scope.file, annotation_scope)
            self._scopes[node] = inner_scope
            for child in ast.iter_child_nodes(node):
                if child in node.body:
                    self._index_node(child, inner_scope)
                elif (type_parameters and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and child is node.args):
                    self._index_arguments(node.args, scope, annotation_scope)
                else:
                    is_annotation = child in type_parameters
                    if isinstance(node, ast.ClassDef):
                        is_annotation = is_annotation or child in node.bases or child in node.keywords
                    else:
                        is_annotation = is_annotation or child is node.returns
                    self._index_node(child, annotation_scope if is_annotation else scope)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._bind_arguments(inner_scope, node.args)
            return
        if isinstance(node, ast.Lambda):
            inner_scope = _Scope(node, scope.file, scope)
            self._scopes[node] = inner_scope
            self._index_node(node.args, scope)
            self._bind_arguments(inner_scope, node.args)
            self._index_node(node.body, inner_scope)
            return
        if isinstance(node, _COMPREHENSIONS):
            inner_scope = _Scope(node, scope.file, scope)
            self._scopes[node] = inner_scope
            for index, generator in enumerate(node.generators):
                self._index_node(generator.iter, scope if index == 0 else inner_scope)
                self._index_node(generator.target, inner_scope)
                for condition in generator.ifs:
                    self._index_node(condition, inner_scope)
            for field_name in ('elt', 'key', 'value'):
                expression = getattr(node, field_name, None)
                if expression is not None:
                    self._index_node(expression, inner_scope)
            return
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == '*':
                    scope.star_imports.append(node)
                else:
                    local_name = alias.asname or (
                        alias.name.split('.')[0] if isinstance(node, ast.Import) else alias.name
                    )
                    self._bind(scope, local_name, node)
        elif isinstance(node, ast.Global):
            scope.globals.update(node.names)
        elif isinstance(node, ast.Nonlocal):
            scope.nonlocals.update(node.names)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            self._bind(scope, node.name, node)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            binding_scope = scope
            parent = getattr(node, 'parent', None)
            if (isinstance(parent, ast.AnnAssign) and parent.value is None
                    and not isinstance(scope.node, _FUNCTION_SCOPES)):
                return
            if isinstance(parent, ast.NamedExpr):
                while isinstance(binding_scope.node, _COMPREHENSIONS) and binding_scope.parent is not None:
                    binding_scope = binding_scope.parent
            self._bind(binding_scope, node.id, node)
        elif type(node).__name__ in ('MatchAs', 'MatchStar') and getattr(node, 'name', None):
            self._bind(scope, getattr(node, 'name'), node)
        elif type(node).__name__ == 'MatchMapping' and getattr(node, 'rest', None):
            self._bind(scope, getattr(node, 'rest'), node)
        for child in ast.iter_child_nodes(node):
            self._index_node(child, scope)

    def _bind_arguments(self, scope: _Scope, arguments: ast.arguments) -> None:
        argument_nodes = list(arguments.posonlyargs) + list(arguments.args) + list(arguments.kwonlyargs)
        if arguments.vararg is not None:
            argument_nodes.append(arguments.vararg)
        if arguments.kwarg is not None:
            argument_nodes.append(arguments.kwarg)
        for argument in argument_nodes:
            self._bind(scope, argument.arg, argument)

    def _index_arguments(self, arguments: ast.arguments, scope: _Scope, annotation_scope: _Scope) -> None:
        self._node_scopes[arguments] = scope
        for child in ast.iter_child_nodes(arguments):
            if isinstance(child, ast.arg):
                self._node_scopes[child] = scope
                if child.annotation is not None:
                    self._index_node(child.annotation, annotation_scope)
            else:
                self._index_node(child, scope)

    def _lookup(
        self, scope: _Scope, name: str, node: ast.AST, seen: Set[Tuple[ast.AST, str]],
    ) -> Set[_Reference]:
        position: Optional[Tuple[int, int]] = (
            None if self._deferred_annotation(scope.file, node) else self._position(node)
        )
        current_scope: Optional[_Scope] = scope
        skip_class_namespaces = False
        while current_scope is not None:
            if name in current_scope.type_parameters:
                return set()
            if name in current_scope.globals and current_scope.parent is not None:
                if self._eligible_bindings(current_scope, name, position):
                    return self._binding_references(current_scope, name, position, seen)
                current_scope = self._scopes[self.trees[current_scope.file]]
                position = None
            elif name in current_scope.nonlocals:
                if self._eligible_bindings(current_scope, name, position):
                    return self._binding_references(current_scope, name, position, seen)
                current_scope = current_scope.parent
                while current_scope is not None and not isinstance(current_scope.node, _FUNCTION_SCOPES):
                    current_scope = current_scope.parent
                position = None
                continue
            if name in current_scope.bindings:
                references = self._binding_references(current_scope, name, position, seen)
                if references or isinstance(current_scope.node, _FUNCTION_SCOPES):
                    return references
                if self._eligible_bindings(current_scope, name, position):
                    return set()
            if self._star_imports(current_scope, position):
                return set()
            if isinstance(current_scope.node, _FUNCTION_SCOPES):
                position = None
            parent_scope = current_scope.parent
            if isinstance(current_scope.node, _FUNCTION_SCOPES + (ast.ClassDef,)):
                skip_class_namespaces = True
            if skip_class_namespaces:
                while parent_scope is not None and isinstance(parent_scope.node, ast.ClassDef):
                    parent_scope = parent_scope.parent
            current_scope = parent_scope
        return set()

    @staticmethod
    def _position(node: ast.AST) -> Tuple[int, int]:
        return getattr(node, 'lineno', 0), getattr(node, 'col_offset', 0)

    def _deferred_annotation(self, file_path: Path, node: ast.AST) -> bool:
        expression = node
        parent = getattr(expression, 'parent', None)
        while parent is not None:
            is_annotation = isinstance(parent, ast.arg) and expression is parent.annotation
            is_annotation = is_annotation or (
                isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)) and expression is parent.returns
            )
            is_annotation = is_annotation or isinstance(parent, ast.AnnAssign) and expression is parent.annotation
            if is_annotation:
                return sys.version_info >= (3, 14) or file_path in self._future_annotations or (
                    isinstance(node, ast.Constant) and isinstance(node.value, str)
                )
            expression = parent
            parent = getattr(parent, 'parent', None)
        return False

    def _eligible_bindings(
        self, scope: _Scope, name: str, position: Optional[Tuple[int, int]],
    ) -> List[_Binding]:
        bindings = scope.bindings.get(name, [])
        if position is None:
            return bindings
        return [binding for binding in bindings if self._binding_position(binding.node) < position]

    def _binding_position(self, node: ast.AST) -> Tuple[int, int]:
        statement = node
        parent = getattr(node, 'parent', None)
        if isinstance(node, ast.Name) and isinstance(parent, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            statement = parent
        if isinstance(statement, _DEFINITIONS + (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            return getattr(statement, 'end_lineno', statement.lineno), getattr(statement, 'end_col_offset', 0)
        return self._position(node)

    def _binding_references(
        self, scope: _Scope, name: str, position: Optional[Tuple[int, int]], seen: Set[Tuple[ast.AST, str]],
    ) -> Set[_Reference]:
        key = (scope.node, name)
        if key in seen:
            return set()
        bindings = self._eligible_bindings(scope, name, position)
        if not bindings:
            return set()
        binding = max(bindings, key=lambda candidate: self._position(candidate.node))
        if any(self._position(star_import) > self._binding_position(binding.node)
               for star_import in self._star_imports(scope, position)):
            return set()
        if self._conditional_binding(binding.node, scope.node):
            return set()
        node = binding.node
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            references = self._import_references(scope.file, node, name, seen | {key})
            return {
                _Reference(
                    reference.module, reference.node,
                    tuple(sorted(set(reference.loaded_modules)
                                 | self._loaded_modules(scope, reference.module, position, seen | {key}))),
                )
                if reference.node is None else reference
                for reference in references
            }
        parent = getattr(node, 'parent', None)
        if isinstance(parent, ast.AnnAssign) and parent.value is None:
            return set()
        if isinstance(node, _DEFINITIONS) or self._elements.get(node):
            return {_Reference(self._file_modules.get(scope.file, ''), node)}
        return set()

    def _star_imports(self, scope: _Scope, position: Optional[Tuple[int, int]]) -> List[ast.AST]:
        return [node for node in scope.star_imports if position is None or self._position(node) < position]

    def _loaded_modules(
        self, scope: _Scope, module: str, position: Optional[Tuple[int, int]], seen: Set[Tuple[ast.AST, str]],
    ) -> Set[str]:
        key = (scope.node, f'<loaded:{module}>')
        if key in seen:
            return set()
        loaded_modules: Set[str] = set()
        current_scope: Optional[_Scope] = scope
        while current_scope is not None:
            import_nodes = {binding.node for bindings in current_scope.bindings.values() for binding in bindings
                            if isinstance(binding.node, (ast.Import, ast.ImportFrom))}
            for import_node in import_nodes:
                if position is not None and self._position(import_node) >= position:
                    continue
                if self._conditional_binding(import_node, current_scope.node):
                    continue
                for alias in import_node.names:
                    imported_modules = {alias.name}
                    if isinstance(import_node, ast.ImportFrom):
                        references = self._import_references(
                            current_scope.file, import_node, alias.name, seen | {key}, direct=True,
                        )
                        if not references:
                            continue
                        imported_modules = {reference.module for reference in references}
                        source_module = self._import_from_module(current_scope.file, import_node)
                        if source_module:
                            imported_modules.add(source_module)
                    for imported_module in imported_modules:
                        if imported_module.startswith(f'{module}.') and self._module_references(imported_module):
                            loaded_modules.add(imported_module)
            if isinstance(current_scope.node, _FUNCTION_SCOPES):
                position = None
            parent_scope = current_scope.parent
            if isinstance(current_scope.node, _FUNCTION_SCOPES + (ast.ClassDef,)):
                while parent_scope is not None and isinstance(parent_scope.node, ast.ClassDef):
                    parent_scope = parent_scope.parent
            current_scope = parent_scope
        return loaded_modules

    @staticmethod
    def _conditional_binding(node: ast.AST, scope_node: ast.AST) -> bool:
        parent = getattr(node, 'parent', None)
        while parent is not None and parent is not scope_node:
            if isinstance(parent, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler)):
                return True
            if type(parent).__name__ in ('Match', 'TryStar'):
                return True
            parent = getattr(parent, 'parent', None)
        return False

    def _import_references(
        self, file_path: Path, node: ast.AST, name: str, seen: Set[Tuple[ast.AST, str]],
        direct: bool = False,
    ) -> Set[_Reference]:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            return set()
        for alias in reversed(node.names):
            local_name = alias.asname or (alias.name.split('.')[0] if isinstance(node, ast.Import) else alias.name)
            if (alias.name if direct else local_name) != name or alias.name == '*':
                continue
            if isinstance(node, ast.Import):
                module_name = alias.name if direct or alias.asname else alias.name.split('.')[0]
                if not self._module_references(alias.name):
                    return set()
                return {_Reference(reference.module, loaded_modules=(alias.name,))
                        for reference in self._module_references(module_name)}
            imported_module = self._import_from_module(file_path, node)
            if imported_module is not None:
                return self._members(self._module_references(imported_module), alias.name, seen, allow_submodule=True)
            return set()
        return set()

    def _import_from_module(self, file_path: Path, node: ast.ImportFrom) -> Optional[str]:
        if not node.level:
            return node.module or ''
        module_name = self._file_modules.get(file_path, '')
        package_parts = module_name.split('.') if file_path.name == '__init__.py' else module_name.split('.')[:-1]
        if not module_name or node.level > len(package_parts):
            return None
        parts = package_parts[:len(package_parts) - node.level + 1]
        if node.module:
            parts.extend(node.module.split('.'))
        return '.'.join(parts)

    def _module_references(self, module_name: str) -> Set[_Reference]:
        if module_name not in self._module_names:
            return set()
        package_directory: Optional[Path] = None
        parts = module_name.split('.')
        for length in range(1, len(parts)):
            parent_module = '.'.join(parts[:length])
            parent_paths = self._inside_package(self._modules.get(parent_module, set()), package_directory)
            regular_directories = self._inside_package(
                self._regular_packages.get(parent_module, set()), package_directory,
            )
            parent_locations = parent_paths | {directory / '__init__.py' for directory in regular_directories}
            if self._ambiguous_module(parent_module, parent_locations):
                return set()
            if parent_locations:
                parent_path = next(iter(parent_locations))
                if parent_path.name != '__init__.py':
                    return set()
                package_directory = parent_path.parent
        paths = self._inside_package(self._modules.get(module_name, set()), package_directory)
        regular_directories = self._inside_package(self._regular_packages.get(module_name, set()), package_directory)
        locations = paths | {directory / '__init__.py' for directory in regular_directories}
        if self._ambiguous_module(module_name, locations):
            return set()
        directories = self._inside_package(self._module_directories.get(module_name, set()), package_directory)
        if not locations and not directories:
            return set()
        self._resolved_module_paths[module_name] = paths
        return {_Reference(module_name)}

    @staticmethod
    def _inside_package(paths: Set[Path], package_directory: Optional[Path]) -> Set[Path]:
        if package_directory is None:
            return paths
        return {path for path in paths if path == package_directory or package_directory in path.parents}

    def _ambiguous_module(self, module_name: str, paths: Set[Path]) -> bool:
        if len(paths) < 2:
            return False
        candidates = ', '.join(str(path) for path in sorted(paths))
        self.errors.add(f"ambiguous module '{module_name}': {candidates}")
        return True

    def _members(
        self, references: Set[_Reference], name: str, seen: Set[Tuple[ast.AST, str]],
        allow_submodule: bool = False,
    ) -> Set[_Reference]:
        members: Set[_Reference] = set()
        for reference in references:
            if reference.node is not None:
                if isinstance(reference.node, ast.ClassDef):
                    members.update(self._binding_references(self._scopes[reference.node], name, None, seen))
                continue
            child_module = f'{reference.module}.{name}'
            if any(module == child_module or module.startswith(f'{child_module}.')
                   for module in reference.loaded_modules):
                members.update(_Reference(child.module, loaded_modules=reference.loaded_modules)
                               for child in self._module_references(child_module))
                continue
            paths = self._resolved_module_paths.get(reference.module, set())
            if len(paths) == 1:
                scope = self._scopes[self.trees[next(iter(paths))]]
                if name in scope.bindings:
                    members.update(self._binding_references(scope, name, None, seen))
                    if not allow_submodule or (scope.node, name) not in seen:
                        continue
                if self._star_imports(scope, None):
                    continue
                if scope.file.name != '__init__.py':
                    continue
                if '__getattr__' in scope.bindings:
                    continue
            if allow_submodule:
                members.update(self._module_references(child_module))
        return members

    def _reference_elements(self, references: Set[_Reference], expand_modules: bool = False) -> Set[CodeElement]:
        elements: Set[CodeElement] = set()
        for reference in references:
            if reference.node is not None:
                elements.update(self._elements.get(reference.node, set()))
            elif expand_modules:
                paths = self._resolved_module_paths.get(reference.module, set())
                if len(paths) != 1:
                    continue
                scope = self._scopes[self.trees[next(iter(paths))]]
                for name in scope.bindings:
                    members = self._binding_references(scope, name, None, set())
                    elements.update(self._reference_elements(members))
        return elements

    @staticmethod
    def _has_static_root(node: ast.AST) -> bool:
        if isinstance(node, ast.Constant):
            return isinstance(node.value, str)
        while isinstance(node, (ast.Attribute, ast.Call, ast.Subscript, ast.Index)):
            node = node.func if isinstance(node, ast.Call) else getattr(node, 'value')
        return isinstance(node, ast.Name)
