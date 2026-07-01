---
name: deply-config
description: Create, audit, validate, and integrate Deply v1.0.0 architecture configuration files for Python projects. Use when the user asks to generate, improve, or review deply.yaml, set light/medium/strict architecture rules, support monorepos, add Deply validation or analysis to CI/Makefile, document Deply architecture boundaries, or adopt Deply in an existing Python repository.
license: MIT
metadata:
  version: "1.0.0"
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
   - CI rollout: fail immediately or adopt with a temporary `--max-violations=N` ratchet.
3. Read the needed references:
   - `references/discovery.md` first for deterministic repository inspection before asking questions.
   - `references/deply-v1-schema.md` for exact Deply v1.0.0 YAML, collectors, rules, and validation constraints.
   - `references/architecture-recipes.md` when choosing a target architecture style.
   - `references/presets.md` for `light`, `medium`, and `strict` rule sets.
   - `references/framework-presets.md` when the repo uses Django, FastAPI, Flask, Celery, or SQLAlchemy.
   - `references/adoption-and-audit.md` when auditing an existing config or adopting Deply in a legacy project.
   - `references/monorepo.md` when the repo has multiple apps, packages, or services.
   - `references/violation-triage.md` when `deply analyze` reports violations.
   - `references/ci-and-docs.md` when adding Makefile, CI, or documentation changes.
4. Choose the mode:
   - Create/update mode: generate or improve `deply.yaml` with public root key `deply:`.
   - Audit mode: review existing config, CI, docs, and suppressions before proposing changes.
5. Run `deply validate --config=deply.yaml` from the project root.
6. Run `deply analyze --parallel --config=deply.yaml` from the project root.
7. If violations exist, triage them before editing. Fix collectors/excludes first. Only use `--max-violations=N` when the user chooses non-blocking adoption.
8. Add local command, CI step, and short architecture docs when requested.
9. Finish with the output contract below.

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
- Current violation count.
- Existing suppression count and any new suppressions added.
- CI behavior: blocking, non-blocking, ratchet with exact `--max-violations=N`, or not changed.
- Follow-up work, only if required to finish adoption safely.
