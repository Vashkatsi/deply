# Violation Triage

Use this after `deply analyze` reports violations.

## Classify Each Violation

- Real architecture issue: code depends outward or sideways against the chosen architecture.
- Broad collector: a layer includes tests, migrations, framework glue, generated code, or unrelated modules.
- Missing layer: dependency target is real architecture surface but no layer models it.
- Bad layer naming: layer names hide direction, ownership, or service boundaries.
- Too-strict rule: rule encodes desired future state but user chose current-state guardrails.
- Legacy debt: violation is real, accepted temporarily, and should be ratcheted down.

## Fix Order

1. Fix collectors and `exclude_files` for false positives.
2. Add missing layers for real source boundaries.
3. Adjust rules to match the selected strictness and architecture recipe.
4. Recommend code changes only when the user explicitly asked to refactor code.
5. Use `--max-violations=N` last, with exact current count.

Do not add `deply:ignore` comments to make analysis pass. Use suppressions only for reviewed exceptions that cannot be expressed cleanly in config.

## Collector Fixes

Typical fixes:

- Add tests, migrations, generated files, caches, build output, and vendored code to `exclude_files`.
- Narrow `directory` collectors to the actual package root.
- Replace a broad `file_regex` with `directory` when a module boundary exists.
- Split a mixed layer into explicit layers when one layer catches unrelated code.

## Rule Fixes

Typical fixes:

- Move from strict target rules to `light`/`medium` rules when user wants current-state adoption.
- Keep domain external import restrictions strict when the user wants framework-free domain.
- Do not add unsupported allow rules. Deply models restrictions with `disallow_layer_dependencies`.

## Final Report For Violations

Report unresolved violations as:

- Count.
- Classification.
- Recommended action.
- Whether CI blocks, does not block, or uses an exact ratchet.
- Any follow-up refactor needed outside config.
