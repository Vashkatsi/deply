---
name: deply-config
description: Use when creating, auditing, validating, or integrating Deply architecture configuration for Python projects, or inspecting file architecture context before code edits, including deply.yaml, light/medium/strict guidance, monorepos, CI, Makefiles, and architecture documentation.
license: MIT
metadata:
  version: "1.3.1"
---

# Deply Config

Use this skill to create or audit a production-ready `deply.yaml` for a Python project and wire it into local checks, CI, and documentation.

## Workflow

1. Inspect the repository before asking questions:
   - Package tree and Python source roots.
   - `pyproject.toml`, `setup.py`, `setup.cfg`, requirements files, lockfiles.
   - `Makefile`, `.github/workflows/`, `.gitlab-ci.yml`, tox/nox/pre-commit config.
   - Existing docs, architecture notes, and framework imports.
   - Existing `deply.yaml` files and `deply:ignore` / `deply:ignore-file` suppressions.
2. Ask only for intent that cannot be discovered:
   - Preserve current architecture or enforce a target architecture.
   - Strictness: `light`, `medium`, or `strict`.
   - CI rollout: fail immediately or explicitly accept reviewed debt in a baseline; check CLI support first.
3. Read the needed references:
   - `references/discovery.md` first for deterministic repository inspection before asking questions.
   - `references/deply-v1-schema.md` for exact Deply v1.3.1 YAML, collectors, rules, and validation constraints.
   - `references/architecture-recipes.md` when choosing a target architecture style.
   - `references/presets.md` for `light`, `medium`, and `strict` Agent Skill profiles.
   - `references/framework-presets.md` for Agent Skill guidance when the repo uses Django, FastAPI, Flask, Celery, or SQLAlchemy.
   - `references/adoption-and-audit.md` when auditing an existing config or adopting Deply in a legacy project.
   - `references/monorepo.md` when the repo has multiple apps, packages, or services.
   - `references/violation-triage.md` when `deply analyze` reports violations.
   - `references/ci-and-docs.md` when adding Makefile, CI, or documentation changes.
4. Choose the mode:
   - Create/update mode: generate or improve `deply.yaml` with public root key `deply:`.
   - Audit mode: review existing config, CI, docs, and suppressions before proposing changes.
5. Run `deply validate --config=deply.yaml` from the project root.
6. Run `deply analyze --parallel --config=deply.yaml` from the project root.
7. If violations exist, triage them before editing. Fix incorrect collectors/excludes first, without weakening intended boundaries. For accepted legacy debt, follow `references/adoption-and-audit.md`: check `deply analyze --help`, create a baseline explicitly, then compare before and after code changes. Never refresh the baseline to hide new violations. Published v1.2.1 lacks baseline options; use its numeric threshold only when the user explicitly accepts that weaker check.
8. Before authorized code edits, check `deply context --help`. If supported, run `deply context --file path/to/file.py --config=deply.yaml --report-format=json` for each file being edited. Read analysis status and file status first, then memberships, rules, direct callers/dependencies and related violations. See `references/violation-triage.md` for the contract and older-CLI fallback. Context does not authorize edits by itself.
9. After code edits, run `deply analyze --config=deply.yaml --report-format=json`, adding `--baseline=path/to/reviewed-baseline.json` when the project uses one. Do not refresh it to hide new violations.
10. Add local command, CI step, and short architecture docs when requested.
11. Finish with the output contract below.

## Rules

- Prefer the smallest config that enforces the intended boundaries.
- Do not invent unsupported keys such as `allow_layer_dependencies`.
- Do not add generated files, tests, migrations, virtualenvs, build output, or vendored code to analysis scope.
- Keep domain/business layers independent from frameworks, persistence, transport, and SDKs when using `medium` or `strict`.
- Do not add new Deply suppressions unless the user accepts a specific architectural reason.
- Report existing suppressions separately from new violations.
- Validate every config with the installed Deply CLI before presenting it as complete.

## Final Output Contract

End every run with:

- Changed files.
- Mode: create/update or audit.
- Strictness: `light`, `medium`, `strict`, or `not changed`.
- Validation command and result.
- Analyze command and result.
- Context command/status for edited files when supported, or the older-CLI fallback used.
- Current violation count; with baseline, counts of `new`, `existing`, and `resolved` diagnostics.
- Existing suppression count and any new suppressions added.
- CI behavior: blocking, baseline with its path, legacy numeric threshold, or not changed. Include baseline creation/changes explicitly.
- Follow-up work, only if required to finish adoption safely.
