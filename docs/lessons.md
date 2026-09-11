# Lessons

- In zsh scripts, use a task-specific exit variable; `status` is read-only.
- Normalize accepted `git diff --no-index` exit `1` explicitly before chaining checks.
- Fail closed when no elements map; update empty-analysis report expectations.
- Remove obsolete imports after moving parsing into a shared helper.
- Deply relative paths resolve from analysis working directory; place extracted configs at target root for end-to-end validation.
- Quote Jekyll braces in `rg` patterns.
- Branch independent technical debt from fresh `origin/main`; leave deferred draft branches untouched.
- Deduplicate configured paths by resolved identity, not lexical spelling.
- Run skill validation with the project virtualenv.
- Match local release builds to the workflow command.
- Run setup.py checks in the build virtualenv.
- Recreate temporary smoke environments before reuse.
- Verify test filenames with `rg --files`; review suggestions may name nonexistent modules.
- Build CLI test configs from existing rule examples; ruleset layer values are mappings.
- Use the project virtualenv for YAML checks; resolve schema download paths from the upstream tree.
