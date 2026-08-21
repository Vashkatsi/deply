import ast
import logging
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Set, Tuple

from deply.models.code_element import CodeElement
from deply.models.dependency import Dependency

_TRY_TYPES = (ast.Try, getattr(ast, "TryStar", ast.Try))
_ScopeState = Tuple[Set[str], Dict[str, Set[CodeElement]]]


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
        self.has_local_import_bindings = local_import_bindings is not None
        self.local_import_bindings = local_import_bindings or {}
        self.import_dependencies = import_dependencies
        self.scope_import_bindings: List[Dict[str, Set[CodeElement]]] = []
        self.scope_lexical_import_bindings: List[Dict[str, Set[CodeElement]]] = []
        self.scope_types: List[str] = []
        self.scope_nodes: List[ast.AST] = []
        self.scope_deferred_bindings: List[Dict[str, ast.AST]] = []
        self.scope_deferred_nodes: List[List[ast.AST]] = []
        self.deferred_definition_states: Dict[ast.AST, Optional[_ScopeState]] = {}
        self.analyzed_deferred_nodes: Set[ast.AST] = set()
        self.active_deferred_nodes: Set[ast.AST] = set()
        self.runtime_closure_depth = 0
        self.loop_break_states: List[List[Optional[_ScopeState]]] = []
        self.loop_continue_states: List[List[Optional[_ScopeState]]] = []
        self.exception_handler_states: List[List[Optional[_ScopeState]]] = []
        self.finally_exit_states: List[List[Optional[_ScopeState]]] = []
        self.finally_deferred_nodes: List[Optional[Set[ast.AST]]] = []
        self.module_binding_names: Set[str] = set()
        self.final_module_bindings: Dict[str, Set[CodeElement]] = {}
        logging.debug(f"DependencyVisitor created for file with {len(code_elements_in_file)} code elements")

    def visit_Module(self, node):
        if not self.has_local_import_bindings:
            self.generic_visit(node)
            return
        self.scope_bound_names.append(set())
        self.scope_import_bindings.append({})
        self.scope_lexical_import_bindings.append({})
        self.scope_types.append("module")
        self.scope_nodes.append(node)
        self.scope_deferred_bindings.append({})
        self.scope_deferred_nodes.append([])
        try:
            self._visit_statements(node.body)
            self._analyze_unused_deferred_nodes()
        finally:
            self.final_module_bindings = dict(self.scope_import_bindings[-1])
            self.scope_deferred_nodes.pop()
            self.scope_deferred_bindings.pop()
            self.scope_nodes.pop()
            self.scope_types.pop()
            self.scope_lexical_import_bindings.pop()
            self.scope_import_bindings.pop()
            self.scope_bound_names.pop()

    def visit_FunctionDef(self, node):
        defer_body = self._should_defer_function_body()
        self._visit_function_definition(node, visit_body=not defer_body)
        self._replace_scope_name(node.name, is_definition=True)
        if defer_body:
            self._register_deferred_node(node.name, node)

    def visit_AsyncFunctionDef(self, node):
        defer_body = self._should_defer_function_body()
        self._visit_function_definition(node, visit_body=not defer_body)
        self._replace_scope_name(node.name, is_definition=True)
        if defer_body:
            self._register_deferred_node(node.name, node)

    def _visit_function_definition(self, node, visit_body: bool = True):
        previous_code_element = self.current_code_element
        full_name = self._get_definition_full_name(node)
        self.current_code_element = self.code_elements_in_file.get(full_name)
        try:
            if 'decorator' in self.dependency_types and self.current_code_element:
                self._process_decorators(node)
            for decorator in node.decorator_list:
                self.visit(decorator)
            if 'type_annotation' in self.dependency_types and self.current_code_element:
                if node.returns:
                    self._process_annotation(node.returns)
                for arg in node.args.args + node.args.kwonlyargs:
                    if arg.annotation:
                        self._process_annotation(arg.annotation)
            for default in node.args.defaults + node.args.kw_defaults:
                if default:
                    self.visit(default)
            if visit_body:
                self._visit_function_body(node)
        finally:
            self.current_code_element = previous_code_element

    def _visit_function_body(self, node) -> None:
        self.scope_bound_names.append(self._get_function_bound_names(node))
        self.scope_import_bindings.append({})
        self.scope_lexical_import_bindings.append(
            self._get_function_import_bindings(node)
        )
        self.scope_types.append("function")
        self.scope_nodes.append(node)
        self.scope_deferred_bindings.append({})
        self.scope_deferred_nodes.append([])
        previous_flow_state = self._suspend_flow_state()
        try:
            self._visit_statements(node.body)
            self._analyze_unused_deferred_nodes()
        finally:
            self._restore_flow_state(previous_flow_state)
            self.scope_deferred_nodes.pop()
            self.scope_deferred_bindings.pop()
            self.scope_nodes.pop()
            self.scope_types.pop()
            self.scope_lexical_import_bindings.pop()
            self.scope_import_bindings.pop()
            self.scope_bound_names.pop()

    def _should_defer_function_body(self) -> bool:
        return bool(self.scope_types) and self.scope_types[-1] == "function"

    def _register_deferred_node(
            self,
            name: Optional[str],
            node: ast.AST,
    ) -> None:
        if not self.scope_deferred_bindings:
            return
        if node not in self.deferred_definition_states:
            self.deferred_definition_states[node] = self._snapshot_scope()
            self.scope_deferred_nodes[-1].append(node)
        if name:
            self.scope_deferred_bindings[-1][name] = node

    def _analyze_unused_deferred_nodes(self) -> None:
        for node in list(self.scope_deferred_nodes[-1]):
            if node in self.analyzed_deferred_nodes:
                continue
            self._analyze_deferred_node(
                node,
                self.deferred_definition_states[node],
            )

    def _analyze_deferred_node(
            self,
            node: ast.AST,
            scope_state: Optional[_ScopeState] = None,
    ) -> None:
        if node in self.active_deferred_nodes:
            return
        current_scope_state = self._snapshot_scope()
        if scope_state is not None:
            self._restore_scope(scope_state)
        self.analyzed_deferred_nodes.add(node)
        self.active_deferred_nodes.add(node)
        self.runtime_closure_depth += 1
        try:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                previous_code_element = self.current_code_element
                self.current_code_element = self.code_elements_in_file.get(
                    self._get_definition_full_name(node)
                )
                try:
                    self._visit_function_body(node)
                finally:
                    self.current_code_element = previous_code_element
            elif isinstance(node, ast.Lambda):
                self._visit_lambda_body(node)
            elif isinstance(node, ast.GeneratorExp):
                self._visit_generator_expression_body(node)
        finally:
            self.runtime_closure_depth -= 1
            self.active_deferred_nodes.remove(node)
            self._restore_scope(current_scope_state)

    def _get_deferred_node(self, name: str) -> Optional[ast.AST]:
        for scope_index in range(len(self.scope_types) - 1, -1, -1):
            deferred_node = self.scope_deferred_bindings[scope_index].get(name)
            if deferred_node is not None:
                return deferred_node
            if name in self.scope_bound_names[scope_index]:
                return None
        return None

    def _get_deferred_value_node(self, value: ast.AST) -> Optional[ast.AST]:
        if value in self.deferred_definition_states:
            return value
        if isinstance(value, ast.Name):
            return self._get_deferred_node(value.id)
        return None

    def _bind_deferred_value(self, value: ast.AST, target: ast.AST) -> None:
        if isinstance(target, ast.Name):
            deferred_node = self._get_deferred_value_node(value)
            if deferred_node is not None:
                self.scope_deferred_bindings[-1][target.id] = deferred_node
            return
        if not isinstance(target, (ast.Tuple, ast.List)):
            return
        if not isinstance(value, (ast.Tuple, ast.List)):
            return
        for value_element, target_element in zip(value.elts, target.elts):
            self._bind_deferred_value(value_element, target_element)

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
            for decorator in node.decorator_list:
                self.visit(decorator)
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
            for base in node.bases:
                self.visit(base)
            for keyword in node.keywords:
                self.visit(keyword.value)
            self.scope_bound_names.append(set())
            self.scope_import_bindings.append({})
            self.scope_lexical_import_bindings.append({})
            self.scope_types.append("class")
            self.scope_nodes.append(node)
            self.scope_deferred_bindings.append({})
            self.scope_deferred_nodes.append([])
            try:
                self._visit_statements(node.body)
                self._analyze_unused_deferred_nodes()
            finally:
                self.scope_deferred_nodes.pop()
                self.scope_deferred_bindings.pop()
                self.scope_nodes.pop()
                self.scope_types.pop()
                self.scope_lexical_import_bindings.pop()
                self.scope_import_bindings.pop()
                self.scope_bound_names.pop()
        finally:
            self.current_code_element = previous_code_element
        self._replace_scope_name(node.name, is_definition=True)

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
                self._bind_deferred_value(node.value, target)
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
            self._bind_deferred_value(node.value, target)

    def visit_AnnAssign(self, node):
        assigned_element = self._get_assigned_element(node.target)
        if assigned_element is None:
            self.visit(node.annotation)
            if node.value:
                self.visit(node.value)
                self.visit(node.target)
                self._bind_deferred_value(node.value, node.target)
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
            self._bind_deferred_value(node.value, node.target)

    def visit_Lambda(self, node):
        for default in node.args.defaults + node.args.kw_defaults:
            if default:
                self.visit(default)
        if self._should_defer_function_body():
            self._register_deferred_node(None, node)
            return

        self._visit_lambda_body(node)

    def _visit_lambda_body(self, node) -> None:
        self.scope_bound_names.append(self._get_argument_names(node.args))
        self.scope_import_bindings.append({})
        self.scope_lexical_import_bindings.append({})
        self.scope_types.append("function")
        self.scope_nodes.append(node)
        self.scope_deferred_bindings.append({})
        self.scope_deferred_nodes.append([])
        previous_flow_state = self._suspend_flow_state()
        try:
            self.visit(node.body)
            self._analyze_unused_deferred_nodes()
        finally:
            self._restore_flow_state(previous_flow_state)
            self.scope_deferred_nodes.pop()
            self.scope_deferred_bindings.pop()
            self.scope_nodes.pop()
            self.scope_types.pop()
            self.scope_lexical_import_bindings.pop()
            self.scope_import_bindings.pop()
            self.scope_bound_names.pop()

    def visit_ListComp(self, node):
        self._visit_comprehension(node, [node.elt])

    def visit_SetComp(self, node):
        self._visit_comprehension(node, [node.elt])

    def visit_GeneratorExp(self, node):
        self.visit(node.generators[0].iter)
        if self._should_defer_function_body():
            self._register_deferred_node(None, node)
            return
        self._visit_generator_expression_body(node)

    def _visit_generator_expression_body(self, node) -> None:
        self._visit_comprehension(
            node,
            [node.elt],
            scope_type="function",
            visit_first_iter=False,
        )

    def visit_DictComp(self, node):
        self._visit_comprehension(node, [node.key, node.value])

    def visit_Return(self, node):
        self.generic_visit(node)
        self._capture_finally_exit_state()
        return False

    def visit_Raise(self, node):
        self.generic_visit(node)
        if self.exception_handler_states:
            self.exception_handler_states[-1].append(self._snapshot_scope())
        self._capture_finally_exit_state()
        return False

    def visit_Break(self, _node):
        if self.loop_break_states:
            self.loop_break_states[-1].append(self._snapshot_scope())
        self._capture_finally_exit_state()
        return False

    def visit_Continue(self, _node):
        if self.loop_continue_states:
            self.loop_continue_states[-1].append(self._snapshot_scope())
        self._capture_finally_exit_state()
        return False

    def _capture_finally_exit_state(self) -> None:
        scope_state = self._snapshot_scope()
        for exit_states in self.finally_exit_states:
            exit_states.append(scope_state)

    def _suspend_flow_state(self):
        previous_flow_state = (
            self.loop_break_states,
            self.loop_continue_states,
            self.exception_handler_states,
            self.finally_exit_states,
            self.finally_deferred_nodes,
        )
        self.loop_break_states = []
        self.loop_continue_states = []
        self.exception_handler_states = []
        self.finally_exit_states = []
        self.finally_deferred_nodes = []
        return previous_flow_state

    def _restore_flow_state(self, previous_flow_state) -> None:
        (
            self.loop_break_states,
            self.loop_continue_states,
            self.exception_handler_states,
            self.finally_exit_states,
            self.finally_deferred_nodes,
        ) = previous_flow_state

    def _visit_statements(self, statements) -> bool:
        for statement in statements:
            if self._statement_may_raise(statement):
                scope_state = self._snapshot_scope()
                if self.exception_handler_states:
                    self.exception_handler_states[-1].append(scope_state)
            if self.visit(statement) is False:
                return False
        return True

    @staticmethod
    def _statements_may_raise(statements: Sequence[ast.stmt]) -> bool:
        return any(
            DependencyVisitor._statement_may_raise(statement)
            for statement in DependencyVisitor._get_reachable_statements(
                statements
            )
        )

    @staticmethod
    def _statement_may_raise(statement: ast.stmt) -> bool:
        if isinstance(
                statement,
                (ast.Pass, ast.Break, ast.Continue, ast.Import, ast.ImportFrom),
        ):
            return False
        if isinstance(statement, ast.Raise):
            return True
        if isinstance(statement, ast.Return):
            return statement.value is not None
        if isinstance(statement, ast.Expr):
            return not isinstance(statement.value, ast.Constant)
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return bool(
                statement.decorator_list
                or statement.args.defaults
                or any(statement.args.kw_defaults)
            )
        if isinstance(statement, ast.If):
            truthiness = DependencyVisitor._get_known_truthiness(
                statement.test
            )
            if truthiness is True:
                return DependencyVisitor._statements_may_raise(statement.body)
            if truthiness is False:
                return DependencyVisitor._statements_may_raise(
                    statement.orelse
                )
            return True
        if isinstance(statement, _TRY_TYPES):
            handler_may_raise = any(
                DependencyVisitor._statements_may_raise(handler.body)
                for handler in statement.handlers
            )
            return (
                handler_may_raise
                or DependencyVisitor._statements_may_raise(statement.orelse)
                or DependencyVisitor._statements_may_raise(
                    statement.finalbody
                )
                or (
                    not statement.handlers
                    and DependencyVisitor._statements_may_raise(
                        statement.body
                    )
                )
            )
        return True

    def visit_For(self, node):
        return self._visit_for(node)

    def visit_AsyncFor(self, node):
        return self._visit_for(node)

    def _visit_for(self, node):
        self.visit(node.iter)
        initial_state = self._snapshot_scope()
        self.loop_break_states.append([])
        self.loop_continue_states.append([])
        try:
            self.visit(node.target)
            iterable_values = (
                node.iter.elts
                if isinstance(node.iter, (ast.Tuple, ast.List, ast.Set))
                else [node.iter]
            )
            for iterable_value in iterable_values:
                if self._get_deferred_value_node(iterable_value) is not None:
                    self._bind_deferred_value(iterable_value, node.target)
            body_continues = self._visit_statements(node.body)
            body_states = list(self.loop_continue_states[-1])
            if body_continues:
                body_states.append(self._snapshot_scope())

            zero_iteration_states = (
                [] if self._iterable_is_definitely_nonempty(node.iter)
                else [initial_state]
            )
            self._restore_scope(
                self._merge_scope_states([*zero_iteration_states, *body_states])
            )
            else_continues = self._visit_statements(node.orelse)
            completed_states = list(self.loop_break_states[-1])
            if else_continues:
                completed_states.append(self._snapshot_scope())
            self._restore_scope(self._merge_scope_states(completed_states))
            return bool(completed_states)
        finally:
            self.loop_continue_states.pop()
            self.loop_break_states.pop()

    def visit_NamedExpr(self, node):
        self.visit(node.value)
        for scope_index in range(len(self.scope_types) - 1, -1, -1):
            if self.scope_types[scope_index] != "comprehension":
                self._replace_scope_bindings(node.target, scope_index)
                if scope_index == len(self.scope_types) - 1:
                    self._bind_deferred_value(node.value, node.target)
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

    def visit_IfExp(self, node):
        self.visit(node.test)
        initial_state = self._snapshot_scope()
        self.visit(node.body)
        body_state = self._snapshot_scope()
        self._restore_scope(initial_state)
        self.visit(node.orelse)
        self._restore_scope(
            self._merge_scope_states([body_state, self._snapshot_scope()])
        )

    def visit_Compare(self, node):
        self.visit(node.left)
        if not node.comparators:
            return
        self.visit(node.comparators[0])
        completed_states = []
        for comparator in node.comparators[1:]:
            completed_states.append(self._snapshot_scope())
            self.visit(comparator)
        completed_states.append(self._snapshot_scope())
        self._restore_scope(self._merge_scope_states(completed_states))

    def visit_With(self, node):
        return self._visit_with(node)

    def visit_AsyncWith(self, node):
        return self._visit_with(node)

    def _visit_with(self, node):
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars:
                self.visit(item.optional_vars)
        return self._visit_statements(node.body)

    def visit_If(self, node):
        self.visit(node.test)
        truthiness = self._get_known_truthiness(node.test)
        if truthiness is not None:
            selected_statements = node.body if truthiness else node.orelse
            return self._visit_statements(selected_statements)
        initial_state = self._snapshot_scope()
        completed_states = []
        if self._visit_statements(node.body):
            completed_states.append(self._snapshot_scope())
        self._restore_scope(initial_state)
        if self._visit_statements(node.orelse):
            completed_states.append(self._snapshot_scope())
        self._restore_scope(self._merge_scope_states(completed_states))
        return bool(completed_states)

    def visit_While(self, node):
        self.visit(node.test)
        initial_state = self._snapshot_scope()
        truthiness = self._get_known_truthiness(node.test)
        if truthiness is False:
            return self._visit_statements(node.orelse)
        self.loop_break_states.append([])
        self.loop_continue_states.append([])
        try:
            body_continues = self._visit_statements(node.body)
            body_states = list(self.loop_continue_states[-1])
            if body_continues:
                body_states.append(self._snapshot_scope())

            zero_iteration_states = [] if truthiness is True else [initial_state]
            self._restore_scope(
                self._merge_scope_states([*zero_iteration_states, *body_states])
            )
            else_continues = self._visit_statements(node.orelse)
            completed_states = list(self.loop_break_states[-1])
            if else_continues:
                completed_states.append(self._snapshot_scope())
            self._restore_scope(self._merge_scope_states(completed_states))
            return bool(completed_states)
        finally:
            self.loop_continue_states.pop()
            self.loop_break_states.pop()

    def visit_Try(self, node):
        return self._visit_try(node)

    def visit_TryStar(self, node):
        return self._visit_try(node)

    def _visit_try(self, node):
        initial_state = self._snapshot_scope()
        break_state_markers = [
            (states, len(states)) for states in self.loop_break_states
        ]
        continue_state_markers = [
            (states, len(states)) for states in self.loop_continue_states
        ]
        deferred_nodes_before = (
            set(self.scope_deferred_nodes[-1])
            if self.scope_deferred_nodes
            else set()
        )
        handler_entry_states = []
        body_continues = True
        self.finally_exit_states.append([])
        self.finally_deferred_nodes.append(set() if node.finalbody else None)
        self.exception_handler_states.append([])
        try:
            body_continues = self._visit_statements(node.body)
        finally:
            handler_entry_states.extend(self.exception_handler_states.pop())

        completed_states = []
        terminal_states = []
        if body_continues and self._visit_statements(node.orelse):
            completed_states.append(self._snapshot_scope())
        else:
            terminal_states.append(self._snapshot_scope())

        if handler_entry_states:
            handler_entry_state = self._merge_scope_states(handler_entry_states)
            for handler in node.handlers:
                self._restore_scope(handler_entry_state)
                if handler.type:
                    self.visit(handler.type)
                if handler.name:
                    self._replace_scope_name(handler.name)
                handler_continues = self._visit_statements(handler.body)
                if handler.name:
                    self._delete_scope_name(handler.name)
                handler_state = self._snapshot_scope()
                if handler_continues:
                    completed_states.append(handler_state)
                else:
                    terminal_states.append(handler_state)

        terminal_states.extend(self.finally_exit_states.pop())
        pending_deferred_nodes = self.finally_deferred_nodes.pop()
        finalbody_state = None

        if node.finalbody:
            finalbody_entry_states = [*completed_states, *terminal_states]
            self._restore_scope(
                self._merge_scope_states(finalbody_entry_states)
            )
            finalbody_continues = self._visit_statements(node.finalbody)
            finalbody_state = self._snapshot_scope()
            self._transform_exit_states(
                break_state_markers,
                node.finalbody,
            )
            self._transform_exit_states(
                continue_state_markers,
                node.finalbody,
            )
            if not completed_states or not finalbody_continues:
                completed_states = []
            elif terminal_states:
                self._restore_scope(self._merge_scope_states(completed_states))
                dependency_types = self.dependency_types
                self.dependency_types = []
                try:
                    continuing_finalbody = self._visit_statements(node.finalbody)
                finally:
                    self.dependency_types = dependency_types
                completed_states = (
                    [self._snapshot_scope()]
                    if continuing_finalbody
                    else []
                )
            else:
                completed_states = [self._snapshot_scope()]

            for deferred_node in (
                    set(self.scope_deferred_nodes[-1]) - deferred_nodes_before
            ):
                if deferred_node not in self.analyzed_deferred_nodes:
                    self.deferred_definition_states[deferred_node] = (
                        finalbody_state
                    )

            if pending_deferred_nodes:
                enclosing_pending_nodes = next(
                    (
                        pending_nodes
                        for pending_nodes in reversed(
                            self.finally_deferred_nodes
                        )
                        if pending_nodes is not None
                    ),
                    None,
                )
                if enclosing_pending_nodes is not None:
                    enclosing_pending_nodes.update(pending_deferred_nodes)
                else:
                    for deferred_node in pending_deferred_nodes:
                        self._analyze_deferred_node(
                            deferred_node,
                            finalbody_state,
                        )

        self._restore_scope(self._merge_scope_states(completed_states))
        return bool(completed_states)

    def _transform_exit_states(
            self,
            state_markers,
            finalbody: Sequence[ast.stmt],
    ) -> None:
        for exit_states, initial_count in state_markers:
            original_states = list(exit_states[initial_count:])
            del exit_states[initial_count:]
            for scope_state in original_states:
                transformed_state = self._apply_statements_to_state(
                    finalbody,
                    scope_state,
                )
                if transformed_state is not None:
                    exit_states.append(transformed_state)

    def _apply_statements_to_state(
            self,
            statements: Sequence[ast.stmt],
            scope_state: Optional[_ScopeState],
    ) -> Optional[_ScopeState]:
        current_state = self._snapshot_scope()
        dependency_types = self.dependency_types
        self.dependency_types = []
        self._restore_scope(scope_state)
        try:
            if not self._visit_statements(statements):
                return None
            return self._snapshot_scope()
        finally:
            self._restore_scope(current_state)
            self.dependency_types = dependency_types

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
            (
                guard_state,
                body_state,
                body_continues,
                guard_truthiness,
            ) = self._visit_match_case(
                case,
                capture_names,
            )
            if guard_truthiness is not False and body_continues:
                completed_states.append(body_state)

            next_states = []
            if not self._is_irrefutable_pattern(case.pattern):
                next_states.append(fallthrough_state)
            if case.guard is not None and guard_truthiness is not True:
                next_states.append(guard_state)
            if not next_states:
                can_fall_through = False
                continue
            fallthrough_state = self._merge_scope_states(next_states)

        if can_fall_through:
            completed_states.append(fallthrough_state)
        self._restore_scope(self._merge_scope_states(completed_states))
        return bool(completed_states)

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
        guard_truthiness = None
        if node.guard:
            self.visit(node.guard)
            guard_truthiness = self._get_known_truthiness(node.guard)
        guard_state = self._snapshot_scope()
        body_continues = (
            False
            if guard_truthiness is False
            else self._visit_statements(node.body)
        )
        return (
            guard_state,
            self._snapshot_scope(),
            body_continues,
            guard_truthiness,
        )

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
        if isinstance(node.func, ast.Lambda):
            self.visit(node.func)
            self._analyze_deferred_node(node.func)
            for argument in node.args:
                self.visit(argument)
            for keyword in node.keywords:
                self.visit(keyword.value)
            return
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
        elif isinstance(node.ctx, ast.Load):
            deferred_node = self._get_deferred_node(node.id)
            if deferred_node is not None:
                if not self._defer_node_until_finally(node, deferred_node):
                    self._analyze_deferred_node(deferred_node)
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

    def _defer_node_until_finally(
            self,
            node: ast.AST,
            deferred_node: ast.AST,
    ) -> bool:
        if not any(
                pending_nodes is not None
                for pending_nodes in self.finally_deferred_nodes
        ):
            return False
        parent = getattr(node, "parent", None)
        while parent is not None:
            if isinstance(parent, ast.Return):
                for pending_nodes in reversed(self.finally_deferred_nodes):
                    if pending_nodes is not None:
                        pending_nodes.add(deferred_node)
                        return True
            if isinstance(parent, ast.stmt):
                return False
            parent = getattr(parent, "parent", None)
        return False

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
            if current_function_index is not None and scope_type == "module":
                continue
            import_bindings = self.scope_import_bindings[index]
            if (
                    current_function_index is not None
                    and index < current_function_index
                    and scope_type == "function"
                    and self.runtime_closure_depth == 0
            ):
                lexical_bindings = self.scope_lexical_import_bindings[index]
                has_later_binding = self._has_reachable_later_binding(
                    self.scope_nodes[index],
                    self.scope_nodes[current_function_index],
                    first_name,
                )
                if has_later_binding:
                    import_bindings = lexical_bindings
            bound_names = self.scope_bound_names[index]
            elements = self._resolve_from_map(name, import_bindings)
            if (
                    self.runtime_closure_depth > 0
                    and current_function_index is not None
                    and index < current_function_index
                    and scope_type == "function"
                    and elements
            ):
                lexical_elements = self._resolve_from_map(
                    name,
                    self.scope_lexical_import_bindings[index],
                )
                if elements < lexical_elements:
                    elements = lexical_elements
            resolved_elements.update(elements)
            if scope_type == "module":
                return resolved_elements
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
        if not name:
            return set()
        for _ in range(name.count(".") + 1):
            elements = name_to_elements.get(name)
            if elements:
                return elements
            name = name.rpartition(".")[0]
        return set()

    def _has_reachable_later_binding(
            self,
            function_node: ast.AST,
            current_node: ast.AST,
            name: str,
    ) -> bool:
        for _ in ast.walk(function_node):
            if current_node is function_node:
                return False
            parent = getattr(current_node, "parent", None)
            if parent is None:
                return False
            following_statements = self._get_following_statements(
                parent,
                current_node,
            )
            execution_successors = self._get_execution_successors(
                parent,
                current_node,
            )
            if any(
                    self._statement_binds_name(
                        statement,
                        function_node,
                        name,
                    )
                    for statement in execution_successors
            ):
                return True
            next_node = None
            for statement in following_statements:
                if self._statement_binds_name(statement, function_node, name):
                    return True
                if isinstance(statement, ast.Return):
                    return self._enclosing_finally_binds_name(
                        statement,
                        function_node,
                        name,
                    )
                if isinstance(statement, ast.Raise):
                    if self._enclosing_finally_binds_name(
                            statement,
                            function_node,
                            name,
                    ):
                        return True
                    catching_try = self._find_catching_try(
                        statement,
                        function_node,
                    )
                    if catching_try is None:
                        return False
                    if any(
                            self._statement_binds_name(
                                handler_statement,
                                function_node,
                                name,
                            )
                            for handler in getattr(catching_try, "handlers", [])
                            for handler_statement in handler.body
                    ):
                        return True
                    next_node = catching_try
                    break
                if isinstance(statement, (ast.Break, ast.Continue)):
                    next_node = self._find_enclosing_loop(
                        statement,
                        function_node,
                    )
                    if next_node is None:
                        return False
                    break
            if next_node is not None:
                current_node = next_node
                continue
            current_node = parent
        return False

    @staticmethod
    def _enclosing_finally_binds_name(
            node: ast.AST,
            function_node: ast.AST,
            name: str,
    ) -> bool:
        child = node
        parent = getattr(node, "parent", None)
        for _ in ast.walk(function_node):
            if parent is None or parent is function_node:
                return False
            if (
                    isinstance(parent, _TRY_TYPES)
                    and child not in parent.finalbody
                    and any(
                    DependencyVisitor._statement_binds_name(
                        statement,
                        function_node,
                        name,
                    )
                    for statement in parent.finalbody
                    )
            ):
                return True
            child = parent
            parent = getattr(parent, "parent", None)
        return False

    @staticmethod
    def _find_catching_try(
            node: ast.AST,
            function_node: ast.AST,
    ) -> Optional[ast.AST]:
        child = node
        parent = getattr(node, "parent", None)
        for _ in ast.walk(function_node):
            if parent is None or parent is function_node:
                return None
            if (
                    isinstance(parent, _TRY_TYPES)
                    and child in parent.body
                    and parent.handlers
            ):
                return parent
            child = parent
            parent = getattr(parent, "parent", None)
        return None

    @staticmethod
    def _find_enclosing_loop(
            node: ast.AST,
            function_node: ast.AST,
    ) -> Optional[ast.AST]:
        parent = getattr(node, "parent", None)
        for _ in ast.walk(function_node):
            if parent is None or parent is function_node:
                return None
            if isinstance(parent, (ast.For, ast.AsyncFor, ast.While)):
                return parent
            parent = getattr(parent, "parent", None)
        return None

    @staticmethod
    def _get_following_statements(parent, child) -> List[ast.stmt]:
        for _, value in ast.iter_fields(parent):
            if not isinstance(value, list) or child not in value:
                continue
            child_index = value.index(child)
            return [
                statement
                for statement in value[child_index + 1:]
                if isinstance(statement, ast.stmt)
            ]
        return []

    @staticmethod
    def _get_execution_successors(parent, child) -> Sequence[ast.AST]:
        if isinstance(parent, (ast.Tuple, ast.List, ast.Set)):
            child_index = parent.elts.index(child)
            return parent.elts[child_index + 1:]
        if not isinstance(parent, (ast.If, ast.While)) or child is not parent.test:
            return []
        truthiness = DependencyVisitor._get_known_truthiness(parent.test)
        if truthiness is True:
            return DependencyVisitor._get_reachable_statements(parent.body)
        if truthiness is False:
            return DependencyVisitor._get_reachable_statements(parent.orelse)
        return [
            *DependencyVisitor._get_reachable_statements(parent.body),
            *DependencyVisitor._get_reachable_statements(parent.orelse),
        ]

    @staticmethod
    def _get_reachable_statements(
            statements: Sequence[ast.stmt],
    ) -> List[ast.stmt]:
        reachable_statements = []
        for statement in statements:
            reachable_statements.append(statement)
            if not DependencyVisitor._statement_can_fall_through(statement):
                break
        return reachable_statements

    @staticmethod
    def _statements_can_fall_through(statements: Sequence[ast.stmt]) -> bool:
        for statement in statements:
            if not DependencyVisitor._statement_can_fall_through(statement):
                return False
        return True

    @staticmethod
    def _statement_can_fall_through(statement: ast.stmt) -> bool:
        if isinstance(statement, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            return False
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            return DependencyVisitor._statements_can_fall_through(
                statement.body
            )
        if isinstance(statement, ast.If):
            truthiness = DependencyVisitor._get_known_truthiness(statement.test)
            if truthiness is True:
                return DependencyVisitor._statements_can_fall_through(
                    statement.body
                )
            if truthiness is False:
                return DependencyVisitor._statements_can_fall_through(
                    statement.orelse
                )
            return (
                DependencyVisitor._statements_can_fall_through(statement.body)
                or DependencyVisitor._statements_can_fall_through(
                    statement.orelse
                )
            )
        if isinstance(statement, _TRY_TYPES):
            if statement.finalbody and not (
                    DependencyVisitor._statements_can_fall_through(
                        statement.finalbody
                    )
            ):
                return False
            normal_flow = (
                DependencyVisitor._statements_can_fall_through(statement.body)
                and DependencyVisitor._statements_can_fall_through(
                    statement.orelse
                )
            )
            if normal_flow:
                return True
            if DependencyVisitor._statements_may_raise(statement.body):
                for handler in statement.handlers:
                    if DependencyVisitor._statements_can_fall_through(
                            handler.body
                    ):
                        return True
            return False
        return True

    @staticmethod
    def _walk_reachable(node: ast.AST) -> Iterator[ast.AST]:
        yield node
        if isinstance(node, ast.If):
            yield from DependencyVisitor._walk_reachable(node.test)
            truthiness = DependencyVisitor._get_known_truthiness(node.test)
            statement_groups = (
                [node.body] if truthiness is True
                else [node.orelse] if truthiness is False
                else [node.body, node.orelse]
            )
            for statements in statement_groups:
                for statement in DependencyVisitor._get_reachable_statements(
                        statements
                ):
                    yield from DependencyVisitor._walk_reachable(statement)
            return
        for _, value in ast.iter_fields(node):
            if isinstance(value, ast.AST):
                yield from DependencyVisitor._walk_reachable(value)
                continue
            if not isinstance(value, list):
                continue
            children = value
            if children and isinstance(children[0], ast.stmt):
                children = DependencyVisitor._get_reachable_statements(
                    children
                )
            for child in children:
                if isinstance(child, ast.AST):
                    yield from DependencyVisitor._walk_reachable(child)

    @staticmethod
    def _get_known_truthiness(node) -> Optional[bool]:
        if isinstance(node, ast.NamedExpr):
            return DependencyVisitor._get_known_truthiness(node.value)
        if isinstance(node, ast.Lambda):
            return True
        if isinstance(node, ast.Constant):
            return bool(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            truthiness = DependencyVisitor._get_known_truthiness(node.operand)
            return None if truthiness is None else not truthiness
        return None

    @staticmethod
    def _iterable_is_definitely_nonempty(node: ast.AST) -> bool:
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return bool(node.elts)
        if isinstance(node, ast.Dict):
            return bool(node.keys)
        if isinstance(node, ast.Constant):
            return isinstance(node.value, (str, bytes)) and bool(node.value)
        return False

    @staticmethod
    def _statement_binds_name(statement, function_node, name: str) -> bool:
        for descendant in DependencyVisitor._walk_reachable(statement):
            if not DependencyVisitor._belongs_to_function_scope(
                    descendant,
                    function_node,
            ):
                continue
            if isinstance(descendant, (ast.Import, ast.ImportFrom)):
                if name in DependencyVisitor._get_import_names(descendant):
                    return True
            elif isinstance(descendant, ast.Name) and isinstance(
                    descendant.ctx,
                    (ast.Store, ast.Del),
            ):
                if descendant.id == name:
                    return True
            elif isinstance(
                    descendant,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ) and descendant.name == name:
                return True
        return False

    def _activate_import_bindings(self, node) -> None:
        if not self.scope_import_bindings:
            return
        import_names = self._get_import_names(node)
        for import_name in import_names:
            self.scope_deferred_bindings[-1].pop(import_name, None)
        if self.scope_types[-1] == "module":
            self.module_binding_names.update(import_names)
        for import_name in import_names:
            self._remove_import_bindings(
                self.scope_import_bindings[-1],
                import_name,
            )
        self.scope_import_bindings[-1].update(
            self.local_import_bindings.get((node.lineno, node.col_offset), {})
        )
        self.scope_bound_names[-1].update(import_names)

    def _replace_scope_bindings(self, target, scope_index: int = -1) -> None:
        if not self.scope_import_bindings:
            return
        target_names = self._get_target_names(target)
        for target_name in target_names:
            self.scope_deferred_bindings[scope_index].pop(target_name, None)
        if self.scope_types[scope_index] == "module":
            self.module_binding_names.update(target_names)
        self.scope_bound_names[scope_index].update(target_names)
        for target_name in target_names:
            self._remove_import_bindings(
                self.scope_import_bindings[scope_index],
                target_name,
            )
            if self.scope_types[scope_index] == "module":
                assigned_element = self.code_elements_in_file.get(target_name)
                if assigned_element:
                    self.scope_import_bindings[scope_index][target_name] = {
                        assigned_element
                    }

    def _replace_scope_name(self, name: str, is_definition: bool = False) -> None:
        if not self.scope_import_bindings:
            return
        self.scope_deferred_bindings[-1].pop(name, None)
        if self.scope_types[-1] == "module":
            self.module_binding_names.add(name)
        self._remove_import_bindings(self.scope_import_bindings[-1], name)
        self.scope_bound_names[-1].add(name)
        if is_definition and self.scope_types[-1] == "module":
            definition_prefix = f"{name}."
            for element_name, element in self.code_elements_in_file.items():
                if element_name == name or element_name.startswith(definition_prefix):
                    self.scope_import_bindings[-1][element_name] = {element}

    def _snapshot_scope(
            self,
            scope_index: int = -1,
    ) -> Optional[Tuple[Set[str], Dict[str, Set[CodeElement]]]]:
        if not self.scope_import_bindings:
            return None
        return (
            set(self.scope_bound_names[scope_index]),
            dict(self.scope_import_bindings[scope_index]),
        )

    def _restore_scope(
            self,
            scope_state: Optional[Tuple[Set[str], Dict[str, Set[CodeElement]]]],
            scope_index: int = -1,
    ) -> None:
        if scope_state is None:
            return
        bound_names, import_bindings = scope_state
        self.scope_bound_names[scope_index] = set(bound_names)
        self.scope_import_bindings[scope_index] = dict(import_bindings)

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
            self.scope_deferred_bindings[-1].pop(target_name, None)
        if self.scope_types[-1] == "module":
            self.module_binding_names.update(target_names)
        for target_name in target_names:
            self._remove_import_bindings(
                self.scope_import_bindings[-1],
                target_name,
            )
        if self.scope_types[-1] == "class":
            self.scope_bound_names[-1].difference_update(target_names)

    def _delete_scope_name(self, name: str) -> None:
        if not self.scope_import_bindings:
            return
        self.scope_deferred_bindings[-1].pop(name, None)
        if self.scope_types[-1] == "module":
            self.module_binding_names.add(name)
        self._remove_import_bindings(self.scope_import_bindings[-1], name)
        if self.scope_types[-1] == "class":
            self.scope_bound_names[-1].discard(name)

    @staticmethod
    def _remove_import_bindings(
            import_bindings: Dict[str, Set[CodeElement]],
            bound_name: str,
    ) -> None:
        binding_prefix = f"{bound_name}."
        for binding_name in list(import_bindings):
            if binding_name == bound_name or binding_name.startswith(binding_prefix):
                import_bindings.pop(binding_name)

    def _visit_comprehension(
            self,
            node,
            value_nodes,
            scope_type: str = "comprehension",
            visit_first_iter: bool = True,
    ) -> None:
        first_generator = node.generators[0]
        if visit_first_iter:
            self.visit(first_generator.iter)
        enclosing_state = self._snapshot_scope()
        deferred_flow_state = (
            self._suspend_flow_state() if scope_type == "function" else None
        )

        self.scope_bound_names.append(set())
        self.scope_import_bindings.append({})
        self.scope_lexical_import_bindings.append({})
        self.scope_types.append(scope_type)
        self.scope_nodes.append(node)
        self.scope_deferred_bindings.append({})
        self.scope_deferred_nodes.append([])
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
            self._analyze_unused_deferred_nodes()
        finally:
            completed_enclosing_state = self._snapshot_scope(-2)
            self.scope_deferred_nodes.pop()
            self.scope_deferred_bindings.pop()
            self.scope_nodes.pop()
            self.scope_types.pop()
            self.scope_lexical_import_bindings.pop()
            self.scope_import_bindings.pop()
            self.scope_bound_names.pop()
            if deferred_flow_state is not None:
                self._restore_flow_state(deferred_flow_state)
                self._restore_scope(enclosing_state)
            else:
                self._restore_scope(
                    self._merge_scope_states(
                        [enclosing_state, completed_enclosing_state]
                    )
                )

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
        if not self.scope_types or self.scope_types[-1] == "module":
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
            for descendant in self._walk_reachable(statement):
                if not isinstance(descendant, (ast.Import, ast.ImportFrom)):
                    continue
                if not self._belongs_to_function_scope(descendant, node):
                    continue
                node_bindings = self.local_import_bindings.get(
                    (descendant.lineno, descendant.col_offset),
                    {},
                )
                if descendant is statement:
                    for import_name in self._get_import_names(descendant):
                        self._remove_import_bindings(
                            import_bindings,
                            import_name,
                        )
                for binding_name, elements in node_bindings.items():
                    import_bindings.setdefault(binding_name, set()).update(elements)

            for bound_name in self._get_definite_statement_bound_names(statement):
                self._remove_import_bindings(import_bindings, bound_name)

            if isinstance(statement, _TRY_TYPES):
                for final_statement in statement.finalbody:
                    self._apply_definite_statement_import_bindings(
                        final_statement,
                        import_bindings,
                    )

            if isinstance(statement, (ast.If, ast.While)):
                truthiness = self._get_known_truthiness(statement.test)
                if truthiness is not None:
                    selected_statements = (
                        statement.body
                        if truthiness
                        else statement.orelse
                    )
                    for selected_statement in self._get_reachable_statements(
                            selected_statements
                    ):
                        self._apply_definite_statement_import_bindings(
                            selected_statement,
                            import_bindings,
                        )

        return import_bindings

    def _apply_definite_statement_import_bindings(
            self,
            statement: ast.stmt,
            import_bindings: Dict[str, Set[CodeElement]],
    ) -> None:
        if isinstance(statement, (ast.Import, ast.ImportFrom)):
            for import_name in self._get_import_names(statement):
                self._remove_import_bindings(import_bindings, import_name)
            import_bindings.update(
                self.local_import_bindings.get(
                    (statement.lineno, statement.col_offset),
                    {},
                )
            )
            return
        if isinstance(statement, _TRY_TYPES):
            for final_statement in self._get_reachable_statements(
                    statement.finalbody
            ):
                self._apply_definite_statement_import_bindings(
                    final_statement,
                    import_bindings,
                )
            return
        if isinstance(statement, (ast.If, ast.While)):
            truthiness = self._get_known_truthiness(statement.test)
            if truthiness is None:
                return
            selected_statements = (
                statement.body if truthiness else statement.orelse
            )
            for selected_statement in self._get_reachable_statements(
                    selected_statements
            ):
                self._apply_definite_statement_import_bindings(
                    selected_statement,
                    import_bindings,
                )
            return
        for bound_name in self._get_definite_statement_bound_names(statement):
            self._remove_import_bindings(import_bindings, bound_name)

    @staticmethod
    def _get_definite_statement_bound_names(statement) -> Set[str]:
        if isinstance(statement, ast.Assign):
            bound_names = {
                bound_name
                for target in statement.targets
                for bound_name in DependencyVisitor._get_target_names(target)
            }
            bound_names.update(
                DependencyVisitor._get_definite_named_expr_bound_names(
                    statement.value
                )
            )
            return bound_names
        if isinstance(statement, ast.AnnAssign):
            if statement.value is None:
                return set()
            return (
                DependencyVisitor._get_target_names(statement.target)
                | DependencyVisitor._get_definite_named_expr_bound_names(
                    statement.value
                )
            )
        if isinstance(statement, ast.AugAssign):
            return (
                DependencyVisitor._get_target_names(statement.target)
                | DependencyVisitor._get_definite_named_expr_bound_names(
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
            return DependencyVisitor._get_definite_named_expr_bound_names(
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
    def _get_definite_named_expr_bound_names(expression) -> Set[str]:
        bound_names = set()
        if isinstance(expression, ast.NamedExpr):
            bound_names.update(
                DependencyVisitor._get_target_names(expression.target)
            )

        children: Sequence[ast.AST]
        if isinstance(expression, ast.Lambda):
            children = [
                *expression.args.defaults,
                *(
                    default
                    for default in expression.args.kw_defaults
                    if default is not None
                ),
            ]
        elif isinstance(
                expression,
                (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp),
        ):
            children = []
        elif isinstance(expression, ast.BoolOp):
            children = expression.values[:1]
        elif isinstance(expression, ast.IfExp):
            children = [expression.test]
        elif isinstance(expression, ast.Compare):
            children = [expression.left, *expression.comparators[:1]]
        else:
            children = list(ast.iter_child_nodes(expression))

        for child in children:
            bound_names.update(
                DependencyVisitor._get_definite_named_expr_bound_names(child)
            )
        return bound_names

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
