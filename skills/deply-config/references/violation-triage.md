# Violation Triage

Use this after `deply analyze` reports violations.

## Before Editing Code

Check `deply context --help` once per installed CLI. Context requires v1.3.0
or later; on older versions inspect the existing config and relevant
source files alongside `deply analyze --report-format=json`. Do not invent a
context response, silently upgrade dependencies, or treat unsupported CLI options
as a clean analysis.

On a supporting CLI, run from the project root:

```bash
deply context --file src/orders/service.py --config=deply.yaml --report-format=json
```

- Require `status: complete` and `file_status: mapped` before relying on the result.
  Invalid configuration uses the analysis error envelope without context fields.
  Incomplete analysis may return elements but no edges; that is not proof of isolation.
- Inspect every element's `layers`, effective `rules` with existing `rule_id` values,
  direct `incoming`/`outgoing` edges and related unsuppressed `violations`.
- Rules include restrictions owned by selected layers and restrictions that forbid
  other layers from depending on them. These are constraints, not recommendations
  to weaken config.
- `excluded`, `outside_scope`, `unmapped`, `not_found`, `not_python`, and `parse_failed`
  mean the selected file has no usable complete context. Report the gap and inspect
  its cause; do not broaden scan scope or relax rules just to obtain a green result.
- The entire configured project is analyzed. Only direct statically resolved edges
  between collected elements are returned; no transitive or runtime impact guarantee.
  Same-file edges can appear in both directions. External imports are represented
  in restrictions/findings, not as graph endpoints.
- Exit `0` confirms usable context, even with violations. After editing, run
  `deply analyze --report-format=json` with the existing reviewed `--baseline`
  when applicable. Never rewrite accepted debt merely to pass checks.

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
5. For explicitly accepted legacy debt, use a reviewed baseline on a supporting CLI; see `adoption-and-audit.md`. Use a numeric threshold only as an explicitly accepted older-CLI fallback.

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
