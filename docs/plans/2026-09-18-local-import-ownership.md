# Local import ownership

Status: implementation authorized and completed; verification results below.
Base: `origin/main` at `b0f1b01` (SARIF output merged).

## Next technical-debt task

Deliver one bounded part of roadmap P0 item 3: attribute internal import edges
to the scope containing the import. Keep the full module-aware resolver pending.
Baseline and cycle detection still depend on that resolver.

## Verified defect

Both `DependencyVisitor.visit_Import` and `visit_ImportFrom` emit an edge for
every collected element in the file, including when the import is local.
`CodeAnalyzer` supplies the visitor to the runner, which evaluates each emitted
edge against layer rules; unrelated functions can therefore gain violations.

On the base commit, this source produces both `first -> Target` and
`second -> Target` import edges at line 2:

```python
def first():
    from target import Target

def second():
    pass
```

The correct import owner is `first` only. This probe isolates `import_from`
dependencies; no name or call inference is involved.

## Contract

- For `import` and `from ... import ...` inside a function, async function,
  method, or class body, emit edges only from the nearest enclosing definition
  when that definition is collected.
- An uncollected nested definition must not transfer its imports to an outer
  element or unrelated elements. This matches existing nested-scope handling.
- Imports under `if`, `try`, or loops retain their enclosing definition owner.
- Module-level imports retain the existing file-wide propagation policy,
  including imports inside module-level control-flow blocks.
- Preserve target lookup, dependency types, and import source locations.
  Alias resolution, relative-module resolution, and shadowing remain incomplete.

## Implementation steps

1. Add focused regression coverage to `tests/test_dependency_visitor.py` for
   both import forms: sibling isolation, async functions, class/method ownership,
   collected and uncollected nested definitions, restored ownership after a
   nested definition, and imports under control-flow blocks. Retain the existing
   module-import propagation test and cover a module-level conditional import.
2. In `deply/utils/dependency_visitor.py`, share import-source selection between
   the two import handlers. Reuse AST parent links installed by `CodeAnalyzer`
   to locate the nearest definition and its existing qualified-name lookup.
   Distinguish an uncollected definition from module scope explicitly:
   `current_code_element is None` alone cannot distinguish them. Do not add a
   second scope stack or change `CodeElement`.
3. Add a runner regression in `tests/test_deply_runner.py`: functions collected
   into different layers, a target forbidden only to the non-importing sibling,
   and a local import that must not cause a sibling violation. Also verify a
   forbidden importing owner still produces a violation. Exercise analysis
   through existing collector/rule setup and preserve reported source location.
4. Update `doc/technical-roadmap.md` to record this completed slice without
   marking P0 item 3 resolved; document local-import ownership and remaining
   inference limitations in `doc/features.md`.

## Scope boundaries

No module identity redesign, new module nodes, alias/shadowing resolver,
external-import rule changes, baseline, cycle detection, CLI/config changes,
report-schema changes, dependencies, or collector refactoring.

The remaining P0 work needs its own plan: module identities and import targets,
lexical bindings/shadowing, then explicit treatment of unresolved inference.
This change fixes source ownership only and does not claim graph completeness.

## Acceptance and verification

- Focused tests fail on the base commit for the incorrect extra source edges.
- They pass after the shared owner-selection fix; real owner violations remain.
- Run `./.venv/bin/python -m unittest tests.test_dependency_visitor tests.test_deply_runner`,
  then `make check` and `git diff --check`.
- Review both import handlers and their runner flow; ensure no fallback from an
  uncollected local scope to file-wide sources. This is a small isolated change
  for main-agent review, unless implementation expands beyond the stated scope.
- Regression tests reproduced extra local-import source edges and false sibling
  violations before the fix (24 failing subtests).
- Focused visitor/runner suite: 39 tests passed. `make check`: 183 tests passed,
  Ruff and mypy passed, dependency audit found no known vulnerabilities.
- Scoped diff and affected runner flow reviewed; `git diff --check` passed.
