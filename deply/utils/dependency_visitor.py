import ast
import logging
from typing import Callable, Dict, List, Optional, Set, Tuple

from deply.models.code_element import CodeElement
from deply.models.dependency import Dependency


class DependencyVisitor(ast.NodeVisitor):
    def __init__(
            self,
            code_elements_in_file: Dict[str, CodeElement],
            dependency_types: List[str],
            dependency_handler: Callable[[Dependency], None],
            name_to_elements: Dict[str, Set[CodeElement]],
            local_import_bindings: Optional[
                Dict[Tuple[int, int], Dict[str, Set[CodeElement]]]
            ] = None,
            import_dependencies: Optional[
                Dict[Tuple[int, int], Set[CodeElement]]
            ] = None,
    ):
        self.code_elements_in_file = code_elements_in_file
        self.dependency_types = dependency_types
        self.dependency_handler = dependency_handler
        self.name_to_elements = name_to_elements
        self.current_code_element: Optional[CodeElement] = None
        self.scope_bound_names: List[Set[str]] = []
        self.local_import_bindings = local_import_bindings or {}
        self.import_dependencies = import_dependencies
        self.scope_import_bindings: List[Dict[str, Set[CodeElement]]] = []
        self.scope_lexical_import_bindings: List[Dict[str, Set[CodeElement]]] = []
        self.scope_types: List[str] = []
        logging.debug(f"DependencyVisitor created for file with {len(code_elements_in_file)} code elements")

    def visit_FunctionDef(self, node):
        self._visit_function_definition(node)
        self._replace_scope_name(node.name)

    def visit_AsyncFunctionDef(self, node):
        self._visit_function_definition(node)
        self._replace_scope_name(node.name)

    def _visit_function_definition(self, node):
        previous_code_element = self.current_code_element
        full_name = self._get_definition_full_name(node)
        self.current_code_element = self.code_elements_in_file.get(full_name)
        try:
            if 'decorator' in self.dependency_types and self.current_code_element:
                self._process_decorators(node)
            if 'type_annotation' in self.dependency_types and self.current_code_element:
                if node.returns:
                    self._process_annotation(node.returns)
                for arg in node.args.args + node.args.kwonlyargs:
                    if arg.annotation:
                        self._process_annotation(arg.annotation)
            for default in node.args.defaults + node.args.kw_defaults:
                if default:
                    self.visit(default)
            self.scope_bound_names.append(self._get_function_bound_names(node))
            self.scope_import_bindings.append({})
            self.scope_lexical_import_bindings.append(
                self._get_function_import_bindings(node)
            )
            self.scope_types.append("function")
            try:
                for statement in node.body:
                    self.visit(statement)
            finally:
                self.scope_types.pop()
                self.scope_lexical_import_bindings.pop()
                self.scope_import_bindings.pop()
                self.scope_bound_names.pop()
        finally:
            self.current_code_element = previous_code_element

    def visit_ClassDef(self, node):
        previous_code_element = self.current_code_element
        full_name = self._get_definition_full_name(node)
        self.current_code_element = self.code_elements_in_file.get(full_name)
        try:
            if 'class_inheritance' in self.dependency_types and self.current_code_element:
                for base in node.bases:
                    base_name = self._get_full_name(base)
                    if base_name is None:
                        continue
                    dep_elements = self._resolve_name(base_name)
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
                        dep_elements = self._resolve_name(metaclass_name)
                        for dep_element in dep_elements:
                            dependency = Dependency(
                                code_element=self.current_code_element,
                                depends_on_code_element=dep_element,
                                dependency_type='metaclass',
                                line=keyword.value.lineno,
                                column=keyword.value.col_offset
                            )
                            self.dependency_handler(dependency)
            self.scope_bound_names.append(set())
            self.scope_import_bindings.append({})
            self.scope_lexical_import_bindings.append({})
            self.scope_types.append("class")
            try:
                self.generic_visit(node)
            finally:
                self.scope_types.pop()
                self.scope_lexical_import_bindings.pop()
                self.scope_import_bindings.pop()
                self.scope_bound_names.pop()
        finally:
            self.current_code_element = previous_code_element
        self._replace_scope_name(node.name)

    def visit_Assign(self, node):
        assigned_elements = [
            element
            for target in node.targets
            if (element := self._get_assigned_element(target)) is not None
        ]
        if not assigned_elements:
            self.visit(node.value)
            for target in node.targets:
                self.visit(target)
            return

        previous_code_element = self.current_code_element
        try:
            for assigned_element in assigned_elements:
                self.current_code_element = assigned_element
                self.visit(node.value)
        finally:
            self.current_code_element = previous_code_element
        for target in node.targets:
            self.visit(target)

    def visit_AnnAssign(self, node):
        assigned_element = self._get_assigned_element(node.target)
        if assigned_element is None:
            self.visit(node.annotation)
            if node.value:
                self.visit(node.value)
                self.visit(node.target)
            return

        previous_code_element = self.current_code_element
        self.current_code_element = assigned_element
        try:
            if 'type_annotation' in self.dependency_types:
                self._process_annotation(node.annotation)
            if node.value:
                self.visit(node.value)
        finally:
            self.current_code_element = previous_code_element
        if node.value:
            self.visit(node.target)

    def visit_Lambda(self, node):
        for default in node.args.defaults + node.args.kw_defaults:
            if default:
                self.visit(default)

        self.scope_bound_names.append(self._get_argument_names(node.args))
        self.scope_import_bindings.append({})
        self.scope_lexical_import_bindings.append({})
        self.scope_types.append("function")
        try:
            self.visit(node.body)
        finally:
            self.scope_types.pop()
            self.scope_lexical_import_bindings.pop()
            self.scope_import_bindings.pop()
            self.scope_bound_names.pop()

    def visit_ListComp(self, node):
        self._visit_comprehension(node, [node.elt])

    def visit_SetComp(self, node):
        self._visit_comprehension(node, [node.elt])

    def visit_GeneratorExp(self, node):
        self._visit_comprehension(node, [node.elt])

    def visit_DictComp(self, node):
        self._visit_comprehension(node, [node.key, node.value])

    def visit_For(self, node):
        self._visit_for(node)

    def visit_AsyncFor(self, node):
        self._visit_for(node)

    def _visit_for(self, node):
        self.visit(node.iter)
        scope_state = self._snapshot_scope()
        try:
            self.visit(node.target)
            for statement in node.body:
                self.visit(statement)
        finally:
            self._restore_scope(scope_state)
        for statement in node.orelse:
            self.visit(statement)

    def visit_NamedExpr(self, node):
        self.visit(node.value)
        for scope_index in range(len(self.scope_types) - 1, -1, -1):
            if self.scope_types[scope_index] != "comprehension":
                self._replace_scope_bindings(node.target, scope_index)
                return
        self.visit(node.target)

    def visit_BoolOp(self, node):
        self.visit(node.values[0])
        completed_states = []
        for value in node.values[1:]:
            completed_states.append(self._snapshot_scope())
            self.visit(value)
        completed_states.append(self._snapshot_scope())
        self._restore_scope(self._merge_scope_states(completed_states))

    def visit_Match(self, node):
        self.visit(node.subject)
        fallthrough_state = self._snapshot_scope()
        completed_states = []
        can_fall_through = True
        for case in node.cases:
            if not can_fall_through:
                break
            self._restore_scope(fallthrough_state)
            capture_names = self._get_pattern_tree_bound_names(case.pattern)
            guard_state, body_state = self._visit_match_case(
                case,
                capture_names,
            )
            completed_states.append(body_state)

            next_states = []
            if not self._is_irrefutable_pattern(case.pattern):
                next_states.append(fallthrough_state)
            if case.guard is not None:
                next_states.append(guard_state)
            if not next_states:
                can_fall_through = False
                continue
            fallthrough_state = self._merge_scope_states(next_states)

        if can_fall_through:
            completed_states.append(fallthrough_state)
        self._restore_scope(self._merge_scope_states(completed_states))

    def visit_match_case(self, node):
        scope_state = self._snapshot_scope()
        try:
            self._visit_match_case(
                node,
                self._get_pattern_tree_bound_names(node.pattern),
            )
        finally:
            self._restore_scope(scope_state)

    def _visit_match_case(self, node, capture_names: Set[str]):
        self.visit(node.pattern)
        for bound_name in capture_names:
            self._replace_scope_name(bound_name)
        if node.guard:
            self.visit(node.guard)
        guard_state = self._snapshot_scope()
        for statement in node.body:
            self.visit(statement)
        return guard_state, self._snapshot_scope()

    def visit_Call(self, node):
        if 'function_call' in self.dependency_types and self.current_code_element:
            if isinstance(node.func, ast.Name):
                name = node.func.id
                dep_elements = self._resolve_name(name)
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
                dep_elements = self._resolve_name(full_name)
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
        self._activate_import_bindings(node)
        if 'import' in self.dependency_types:
            names = [alias.asname or alias.name.split('.')[0] for alias in node.names]
            for dep_element in self._get_import_dependencies(node, names):
                for code_element in self._get_import_sources():
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
        self._activate_import_bindings(node)
        if 'import_from' in self.dependency_types:
            names = [alias.asname or alias.name for alias in node.names]
            for dep_element in self._get_import_dependencies(node, names):
                for code_element in self._get_import_sources():
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
        if isinstance(node.ctx, ast.Store):
            self._replace_scope_bindings(node)
        elif isinstance(node.ctx, ast.Del):
            self._delete_scope_bindings(node)
        if 'name_load' in self.dependency_types and self.current_code_element:
            if isinstance(node.ctx, ast.Load):
                name = node.id
                dep_elements = self._resolve_name(name)
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
            dep_elements = self._resolve_name(decorator_name)
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
        dep_elements = self._resolve_name(annotation_name)
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

    def _get_assigned_element(self, target) -> Optional[CodeElement]:
        if not isinstance(target, ast.Name):
            return None

        name_parts = [target.id]
        parent = getattr(target, "parent", None)
        while parent is not None:
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                return None
            if isinstance(parent, ast.ClassDef):
                name_parts.append(parent.name)
            parent = getattr(parent, "parent", None)
        return self.code_elements_in_file.get(".".join(reversed(name_parts)))

    def _resolve_name(self, name: Optional[str]) -> Set[CodeElement]:
        first_name = name.partition(".")[0] if name else ""
        resolved_elements: Set[CodeElement] = set()
        skip_class_scopes = False
        current_function_index = None
        for index in range(len(self.scope_types) - 1, -1, -1):
            if self.scope_types[index] == "comprehension":
                continue
            if self.scope_types[index] == "function":
                current_function_index = index
            break
        for index in range(len(self.scope_types) - 1, -1, -1):
            scope_type = self.scope_types[index]
            if scope_type == "class" and skip_class_scopes:
                continue
            import_bindings = self.scope_import_bindings[index]
            if (
                    current_function_index is not None
                    and index < current_function_index
                    and scope_type == "function"
            ):
                import_bindings = self.scope_lexical_import_bindings[index]
            bound_names = self.scope_bound_names[index]
            elements = self._resolve_from_map(name, import_bindings)
            resolved_elements.update(elements)
            if first_name in bound_names:
                return resolved_elements
            skip_class_scopes = True
        resolved_elements.update(
            self._resolve_from_map(name, self.name_to_elements)
        )
        return resolved_elements

    @staticmethod
    def _resolve_from_map(
            name: Optional[str],
            name_to_elements: Dict[str, Set[CodeElement]],
    ) -> Set[CodeElement]:
        while name:
            elements = name_to_elements.get(name)
            if elements:
                return elements
            name = name.rpartition(".")[0]
        return set()

    def _activate_import_bindings(self, node) -> None:
        if not self.scope_import_bindings:
            return
        self.scope_import_bindings[-1].update(
            self.local_import_bindings.get((node.lineno, node.col_offset), {})
        )
        self.scope_bound_names[-1].update(self._get_import_names(node))

    def _replace_scope_bindings(self, target, scope_index: int = -1) -> None:
        if not self.scope_import_bindings:
            return
        target_names = self._get_target_names(target)
        self.scope_bound_names[scope_index].update(target_names)
        for target_name in target_names:
            self._remove_import_bindings(
                self.scope_import_bindings[scope_index],
                target_name,
            )

    def _replace_scope_name(self, name: str) -> None:
        if not self.scope_import_bindings:
            return
        self.scope_bound_names[-1].add(name)
        self._remove_import_bindings(self.scope_import_bindings[-1], name)

    def _snapshot_scope(
            self,
    ) -> Optional[Tuple[Set[str], Dict[str, Set[CodeElement]]]]:
        if not self.scope_import_bindings:
            return None
        return (
            set(self.scope_bound_names[-1]),
            dict(self.scope_import_bindings[-1]),
        )

    def _restore_scope(
            self,
            scope_state: Optional[Tuple[Set[str], Dict[str, Set[CodeElement]]]],
    ) -> None:
        if scope_state is None:
            return
        bound_names, import_bindings = scope_state
        self.scope_bound_names[-1] = set(bound_names)
        self.scope_import_bindings[-1] = dict(import_bindings)

    @staticmethod
    def _merge_scope_states(scope_states):
        available_states = [state for state in scope_states if state is not None]
        if not available_states:
            return None

        bound_names = set.intersection(
            *(state[0] for state in available_states)
        )
        import_bindings: Dict[str, Set[CodeElement]] = {}
        for _, state_import_bindings in available_states:
            for binding_name, elements in state_import_bindings.items():
                import_bindings.setdefault(binding_name, set()).update(elements)
        return bound_names, import_bindings

    def _delete_scope_bindings(self, target) -> None:
        if not self.scope_import_bindings:
            return
        target_names = self._get_target_names(target)
        for target_name in target_names:
            self._remove_import_bindings(
                self.scope_import_bindings[-1],
                target_name,
            )
        if self.scope_types[-1] == "class":
            self.scope_bound_names[-1].difference_update(target_names)

    @staticmethod
    def _remove_import_bindings(
            import_bindings: Dict[str, Set[CodeElement]],
            bound_name: str,
    ) -> None:
        binding_prefix = f"{bound_name}."
        for binding_name in list(import_bindings):
            if binding_name == bound_name or binding_name.startswith(binding_prefix):
                import_bindings.pop(binding_name)

    def _visit_comprehension(self, node, value_nodes) -> None:
        first_generator = node.generators[0]
        self.visit(first_generator.iter)

        self.scope_bound_names.append(set())
        self.scope_import_bindings.append({})
        self.scope_lexical_import_bindings.append({})
        self.scope_types.append("comprehension")
        try:
            self._replace_scope_bindings(first_generator.target)
            for condition in first_generator.ifs:
                self.visit(condition)
            for generator in node.generators[1:]:
                self.visit(generator.iter)
                self._replace_scope_bindings(generator.target)
                for condition in generator.ifs:
                    self.visit(condition)
            for value_node in value_nodes:
                self.visit(value_node)
        finally:
            self.scope_types.pop()
            self.scope_lexical_import_bindings.pop()
            self.scope_import_bindings.pop()
            self.scope_bound_names.pop()

    @staticmethod
    def _get_target_names(target) -> Set[str]:
        return {
            descendant.id
            for descendant in ast.walk(target)
            if isinstance(descendant, ast.Name)
            and isinstance(descendant.ctx, (ast.Store, ast.Del))
        }

    @staticmethod
    def _get_import_names(node) -> Set[str]:
        if isinstance(node, ast.Import):
            return {alias.asname or alias.name.split(".")[0] for alias in node.names}
        return {
            alias.asname or alias.name
            for alias in node.names
            if alias.name != "*"
        }

    def _get_import_sources(self) -> List[CodeElement]:
        if not self.scope_import_bindings:
            return list(self.code_elements_in_file.values())
        return [self.current_code_element] if self.current_code_element else []

    def _get_import_dependencies(self, node, names) -> Set[CodeElement]:
        if self.import_dependencies is not None:
            return self.import_dependencies.get((node.lineno, node.col_offset), set())

        dependencies: Set[CodeElement] = set()
        for name in names:
            dependencies.update(self._resolve_name(name))
        return dependencies

    def _get_function_import_bindings(
            self,
            node,
    ) -> Dict[str, Set[CodeElement]]:
        import_bindings: Dict[str, Set[CodeElement]] = {}

        for statement in node.body:
            for descendant in ast.walk(statement):
                if not isinstance(descendant, (ast.Import, ast.ImportFrom)):
                    continue
                if not self._belongs_to_function_scope(descendant, node):
                    continue
                node_bindings = self.local_import_bindings.get(
                    (descendant.lineno, descendant.col_offset),
                    {},
                )
                for binding_name, elements in node_bindings.items():
                    import_bindings.setdefault(binding_name, set()).update(elements)

            for bound_name in self._get_definite_statement_bound_names(statement):
                self._remove_import_bindings(import_bindings, bound_name)

        return import_bindings

    @staticmethod
    def _get_definite_statement_bound_names(statement) -> Set[str]:
        if isinstance(statement, ast.Assign):
            bound_names = {
                bound_name
                for target in statement.targets
                for bound_name in DependencyVisitor._get_target_names(target)
            }
            bound_names.update(
                DependencyVisitor._get_direct_named_expr_bound_names(
                    statement.value
                )
            )
            return bound_names
        if isinstance(statement, ast.AnnAssign):
            if statement.value is None:
                return set()
            return (
                DependencyVisitor._get_target_names(statement.target)
                | DependencyVisitor._get_direct_named_expr_bound_names(
                    statement.value
                )
            )
        if isinstance(statement, ast.AugAssign):
            return (
                DependencyVisitor._get_target_names(statement.target)
                | DependencyVisitor._get_direct_named_expr_bound_names(
                    statement.value
                )
            )
        if isinstance(statement, ast.Delete):
            return {
                bound_name
                for target in statement.targets
                for bound_name in DependencyVisitor._get_target_names(target)
            }
        if isinstance(statement, ast.Expr):
            return DependencyVisitor._get_direct_named_expr_bound_names(
                statement.value
            )
        if isinstance(
                statement,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            return {statement.name}
        match_type = getattr(ast, "Match", None)
        if match_type is not None and isinstance(statement, match_type):
            return DependencyVisitor._get_match_definite_bound_names(statement)
        return set()

    @staticmethod
    def _get_direct_named_expr_bound_names(expression) -> Set[str]:
        if not isinstance(expression, ast.NamedExpr):
            return set()
        return DependencyVisitor._get_target_names(expression.target)

    @staticmethod
    def _get_match_definite_bound_names(node) -> Set[str]:
        fallthrough_bound_names: Set[str] = set()
        completed_bound_name_sets = []
        can_fall_through = True

        for case in node.cases:
            if not can_fall_through:
                break
            capture_names = DependencyVisitor._get_pattern_tree_bound_names(
                case.pattern
            )
            guard_bound_names = fallthrough_bound_names | capture_names
            body_bound_names = set(guard_bound_names)
            for statement in case.body:
                if isinstance(statement, (ast.Import, ast.ImportFrom)):
                    body_bound_names.difference_update(
                        DependencyVisitor._get_import_names(statement)
                    )
                    continue
                body_bound_names.update(
                    DependencyVisitor._get_definite_statement_bound_names(
                        statement
                    )
                )
            completed_bound_name_sets.append(body_bound_names)

            next_bound_name_sets = []
            if not DependencyVisitor._is_irrefutable_pattern(case.pattern):
                next_bound_name_sets.append(fallthrough_bound_names)
            if case.guard is not None:
                next_bound_name_sets.append(guard_bound_names)
            if not next_bound_name_sets:
                can_fall_through = False
                continue
            fallthrough_bound_names = set.intersection(
                *next_bound_name_sets
            )

        if can_fall_through:
            completed_bound_name_sets.append(fallthrough_bound_names)
        return set.intersection(*completed_bound_name_sets)

    @staticmethod
    def _get_function_bound_names(node) -> Set[str]:
        bound_names = DependencyVisitor._get_argument_names(node.args)

        global_names = set()
        nonlocal_names = set()
        for descendant in ast.walk(node):
            if descendant is node:
                continue
            belongs_to_function = DependencyVisitor._belongs_to_function_scope(descendant, node)
            if not belongs_to_function:
                if (
                        isinstance(descendant, ast.NamedExpr)
                        and DependencyVisitor._belongs_to_function_scope(
                            descendant,
                            node,
                            include_comprehensions=True,
                        )
                ):
                    bound_names.update(
                        DependencyVisitor._get_target_names(descendant.target)
                    )
                continue
            if isinstance(descendant, ast.Name) and isinstance(descendant.ctx, (ast.Store, ast.Del)):
                bound_names.add(descendant.id)
            elif isinstance(descendant, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bound_names.add(descendant.name)
            elif isinstance(descendant, ast.Import):
                bound_names.update(alias.asname or alias.name.split(".")[0] for alias in descendant.names)
            elif isinstance(descendant, ast.ImportFrom):
                bound_names.update(alias.asname or alias.name for alias in descendant.names if alias.name != "*")
            elif isinstance(descendant, ast.ExceptHandler) and descendant.name:
                bound_names.add(descendant.name)
            elif isinstance(descendant, ast.Global):
                global_names.update(descendant.names)
            elif isinstance(descendant, ast.Nonlocal):
                nonlocal_names.update(descendant.names)
            bound_names.update(
                DependencyVisitor._get_pattern_bound_names(descendant)
            )

        return bound_names - global_names - nonlocal_names

    @staticmethod
    def _get_argument_names(arguments) -> Set[str]:
        argument_nodes = (
            list(getattr(arguments, "posonlyargs", []))
            + list(arguments.args)
            + list(arguments.kwonlyargs)
        )
        argument_names = {argument.arg for argument in argument_nodes}
        if arguments.vararg:
            argument_names.add(arguments.vararg.arg)
        if arguments.kwarg:
            argument_names.add(arguments.kwarg.arg)
        return argument_names

    @staticmethod
    def _get_pattern_bound_names(node) -> Set[str]:
        match_mapping_type = getattr(ast, "MatchMapping", None)
        if match_mapping_type is not None and isinstance(node, match_mapping_type):
            return {node.rest} if node.rest else set()
        match_name_types = tuple(
            node_type
            for node_type in (
                getattr(ast, "MatchAs", None),
                getattr(ast, "MatchStar", None),
            )
            if node_type is not None
        )
        if match_name_types and isinstance(node, match_name_types):
            return {node.name} if node.name else set()
        return set()

    @staticmethod
    def _get_pattern_tree_bound_names(node) -> Set[str]:
        return {
            bound_name
            for descendant in ast.walk(node)
            for bound_name in DependencyVisitor._get_pattern_bound_names(descendant)
        }

    @staticmethod
    def _is_irrefutable_pattern(node) -> bool:
        match_as_type = getattr(ast, "MatchAs", None)
        if match_as_type is not None and isinstance(node, match_as_type):
            return (
                node.pattern is None
                or DependencyVisitor._is_irrefutable_pattern(node.pattern)
            )
        match_or_type = getattr(ast, "MatchOr", None)
        return (
            match_or_type is not None
            and isinstance(node, match_or_type)
            and any(
                DependencyVisitor._is_irrefutable_pattern(pattern)
                for pattern in node.patterns
            )
        )

    @staticmethod
    def _belongs_to_function_scope(
            descendant,
            function_node,
            include_comprehensions: bool = False,
    ) -> bool:
        parent = getattr(descendant, "parent", None)
        while parent is not None and parent is not function_node:
            scope_boundaries = (
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                    ast.Lambda,
                )
                if include_comprehensions
                else (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                    ast.Lambda,
                    ast.ListComp,
                    ast.SetComp,
                    ast.DictComp,
                    ast.GeneratorExp,
                )
            )
            if isinstance(parent, scope_boundaries):
                return False
            parent = getattr(parent, "parent", None)
        return parent is function_node

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
