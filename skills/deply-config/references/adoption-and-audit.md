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
- Prefer collector fixes, excludes for non-source files, or an explicitly reviewed baseline.
- Add a suppression only when the user accepts a specific exception that cannot be modeled cleanly in `deply.yaml`.
- Document why new suppressions are acceptable in the final response or project docs.

## Debt Adoption and Agent Changes

Baseline requires v1.2.2 or later. Inspect `deply analyze --help` and pin a supported
version before following this flow.

1. Validate the target config and inspect a complete analysis report.
2. If the user accepts existing debt, explicitly create a new baseline:

```bash
deply analyze --config=deply.yaml --write-baseline=deply-baseline.json
```

3. Review and track the file. Creation accepts current violations and returns zero;
   it refuses existing destinations and incomplete analyses.
4. Before editing code, run and inspect the comparison:

```bash
deply analyze --config=deply.yaml --baseline=deply-baseline.json --report-format=json
```

5. After editing, run the same command. Require `status: complete`, no errors, no
   `baseline.new`, and exit zero. Fix new violations within the authorized scope;
   report pre-existing unaccepted findings separately.
6. Report `new`, `existing`, and `resolved` counts. Do not treat disappearance after
   changed rules, excludes, or suppressions as proof of a code fix.

Never create or refresh baseline in CI. Never modify baseline, weaken rules, or add
ignores to make an agent's change pass. Refresh only when explicitly authorized:
write a separate candidate, review its diff, then replace the tracked file.
Resolved relationships remain accepted until that refresh; reintroducing one before
refresh remains accepted. Additional occurrences of accepted relationships are also
accepted. Line movement preserves identity; symbol/file/rule/layer changes may not.
Keep the configuration directory at the same relative position to source files.

For older CLIs, an explicitly accepted `--max-violations=N` threshold remains a
fallback. Set it to the measured count and only decrease it. Explain that fixing
one violation can mask adding another; it is not equivalent to baseline comparison.
