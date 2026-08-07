# Async and Nested Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or `superpowers:executing-plans` to
> implement this plan task-by-task.

**Goal:** Attribute dependencies to top-level and nested async/sync functions
and classes while restoring the enclosing scope after each nested definition.

**Architecture:** Keep `DependencyVisitor`'s current single active element, but
save and restore it recursively. Route `FunctionDef` and `AsyncFunctionDef`
through one function visitor; apply the same restoration to `ClassDef`.

**Tech Stack:** Python 3.8-3.14, `ast.NodeVisitor`, `unittest`.

## Global Constraints

- No CLI, configuration, report, or `CodeElement` changes.
- No module-aware resolution, import alias, or shadowing work.
- Preserve existing decorator, annotation, inheritance, and metaclass behavior.
- Use TDD and keep docs and behavior in separate commits.

## Task 1: Record technical debt

**Files:**

- Modify: `README.md`
- Create: `doc/technical-roadmap.md`
- Create: `docs/lessons.md`
- Create: `docs/superpowers/plans/2026-08-07-async-nested-scope.md`

- [ ] Verify the documentation diff with `git diff --check`.
- [ ] Commit as `docs: record technical roadmap`.

## Task 2: Add regression tests

**Files:**

- Modify: `tests/test_dependency_visitor.py`

- [ ] Add a test proving a top-level async function owns its call dependency.
- [ ] Add a test proving nested sync/async functions own their dependencies and
      restore the outer function.
- [ ] Add a test proving an uncollected nested function does not inherit the
      outer scope and the outer scope is restored afterward.
- [ ] Add a test proving a nested class owns its dependencies and restores its
      enclosing class.
- [ ] Run the new tests and confirm they fail for the expected current behavior.

## Task 3: Restore nested scopes

**Files:**

- Modify: `deply/utils/dependency_visitor.py`
- Modify: `doc/technical-roadmap.md`

- [ ] Route `visit_FunctionDef` and `visit_AsyncFunctionDef` through a shared
      `_visit_function_definition` method.
- [ ] Save `current_code_element`, set the new scope including `None`, traverse
      it, and restore the previous value in `finally`.
- [ ] Apply the same save/restore behavior to `visit_ClassDef` without changing
      its rule processing.
- [ ] Mark the roadmap item resolved after tests pass.
- [ ] Commit as `fix: track nested async scopes`.

## Verification

- [ ] `./.venv/bin/python -m unittest tests.test_dependency_visitor`
- [ ] `make check`
- [ ] `make mutation`
- [ ] `git diff --check`
- [ ] Independent high-effort review of the complete scoped diff.
