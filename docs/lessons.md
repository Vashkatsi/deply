# Lessons

- In zsh scripts, use a task-specific exit variable; `status` is read-only.
- Normalize accepted `git diff --no-index` exit `1` explicitly before chaining checks.
- Fail closed when no elements map; update empty-analysis report expectations.
- Remove obsolete imports after moving parsing into a shared helper.
- Deply relative paths resolve from analysis working directory; place extracted configs at target root for end-to-end validation.
- Quote Jekyll braces in `rg` patterns.
- Branch independent technical debt from fresh `origin/main`; leave deferred draft branches untouched.
- Deduplicate configured paths by resolved identity, not lexical spelling.
