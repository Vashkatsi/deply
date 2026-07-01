# Adoption and Audit

Use this when the project already has `deply.yaml`, CI wiring, documentation, or Deply suppressions.

## Existing Config Audit

Check:

- Config uses public `deply:` root or parser-compatible top-level shape.
- No unsupported keys such as `allow_layer_dependencies`, severities, wildcards, or custom rule names.
- `paths` exist and do not point at generated or dependency directories.
- `exclude_files` excludes tests, migrations, generated files, build output, virtualenvs, caches, and vendored code without hiding real source layers.
- Every layer has at least one specific collector.
- `directory` collectors point at real package/module boundaries.
- Regex collectors use single-quoted YAML strings when they contain backslashes.
- Rule layer names match declared layer names.
- `disallow_external_imports` protects domain/application layers from framework, persistence, HTTP, queue, cloud, SDK, and exchange/client packages where appropriate.
- Makefile/CI runs both `deply validate` and `deply analyze`.
- Docs describe actual configured layers and commands.

## Weak Config Signals

Prefer fixing these before adding more rules:

- One layer catches most files.
- Collectors match tests or migrations by accident.
- Rules only document architecture but cannot fail in CI.
- `exclude_files` hides source directories to make analysis pass.
- Strict rules are configured but CI uses a high permanent `--max-violations`.
- Suppressions exist without a reviewed architectural reason.

## Suppression Policy

Scan before changing config:

```bash
rg -n "deply:ignore|deply:ignore-file" .
```

Rules:

- Count existing suppressions and report them.
- Do not add suppressions to make a new config pass.
- Prefer collector fixes, excludes for non-source files, or a temporary ratchet.
- Add a suppression only when the user accepts a specific exception that cannot be modeled cleanly in `deply.yaml`.
- Document why new suppressions are acceptable in the final response or project docs.

## Debt Adoption

Use this flow for legacy projects:

1. Generate the target config.
2. Run `deply validate --config=deply.yaml`.
3. Run `deply analyze --parallel --config=deply.yaml`.
4. If violations are real and accepted temporarily, rerun with exact current count:

```bash
deply analyze --parallel --config=deply.yaml --max-violations=12
```

5. Put the same exact count in CI.
6. Document that the number must only decrease.

Do not choose the ratchet count by guessing. Use the actual current violation count from Deply output.
