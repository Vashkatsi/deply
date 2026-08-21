# Lessons

- In zsh scripts, use a task-specific exit variable; `status` is read-only.
- Normalize accepted `git diff --no-index` exit `1` explicitly before chaining checks.
- Fail closed when no elements map; update empty-analysis report expectations.
- Remove obsolete imports after moving parsing into a shared helper.
- Deply relative paths resolve from analysis working directory; place extracted configs at target root for end-to-end validation.
- Quote Jekyll braces in `rg` patterns.
- Use valid import paths in dependency-resolution fixtures.
- Avoid widening typed AST tuples in place.
- Use exact unittest class names from test modules.
- Copy restored branch state before mutating it.
- Include test method names in expectation patches.
- Run behavior tests on the oldest supported Python.
- Ensure compatibility fixtures reach dependency analysis.
