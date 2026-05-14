# Deply Agent Instructions

## Project
- Deply is a Python static architecture analysis CLI.
- It analyzes Python code, maps code elements into configured layers, checks architecture rules, and reports violations.
- Keep changes small, explicit, and scoped to the task. Do not edit unrelated code.

## Stack
- Python package supporting Python 3.8 through 3.14.
- Packaging: `setuptools`, `setup.py`, `MANIFEST.in`.
- Runtime dependency: `PyYAML`.
- Tests: `unittest` under `tests/`.
- Quality tools: `ruff`, `mypy`, `pip-audit`, `pre-commit`, `mutmut`.

## Commands
- Setup: `python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt -r requirements-dev.txt`
- Full local check: `make check`
- Tests: `make test`
- Lint: `make lint`
- Typing: `make typing`
- Security: `make security`
- Mutation tests: `make mutation`
- Pre-commit hooks: `make pre-commit`
- Direct tests: `./.venv/bin/python -m unittest discover tests`

## Architecture Map
- CLI entrypoint: `deply/main.py`.
- Orchestration: `deply/deply_runner.py`.
- AST dependency analysis: `deply/code_analyzer.py` and `deply/utils/dependency_visitor.py`.
- Config parsing: `deply/config_parser.py`.
- Collectors: `deply/collectors/`, created through `CollectorFactory`.
- Rules: `deply/rules/`, created through `RuleFactory`.
- Reports: `deply/reports/` and `deply/reports/formats/`.
- Mermaid output: `deply/diagrams/marmaid_diagram_builder.py`.
- Value objects: `deply/models/`.
- Docs: `README.md` and `doc/`.

## Coding Rules
- Follow existing style unless it is clearly wrong for the task.
- Prefer simple functions, early returns, descriptive names, and low side effects.
- Keep business analysis logic independent from CLI parsing, report formatting, and persistence.
- Do not add dependencies unless the task truly needs them.
- Do not add logging, comments, abstractions, or broad refactors unless they remove real complexity.
- Treat generated or local artifacts as out of scope: `.venv/`, `.mypy_cache/`, `.ruff_cache/`, `dist/`, `build/`, `deply.egg-info/`, `mutants/`, and coverage output.
- Treat local `deply.yaml` as user/runtime config; update `deply.yaml.example` and docs for public config examples.

## Extension Rules
- New collector: add implementation in `deply/collectors/`, wire it through `CollectorFactory`, document config shape, and add focused tests.
- New rule: add implementation in `deply/rules/`, wire it through `RuleFactory`, update violation/report behavior if needed, and add focused tests.
- New report format: add formatter under `deply/reports/formats/`, wire it through `ReportGenerator`, update CLI choices/docs, and add tests.
- CLI/config behavior changes require matching updates in `README.md` and `doc/`.

## Testing
- Add or update `unittest` coverage for changed behavior.
- Prefer small tests that exercise public behavior through existing factories, runner paths, or CLI boundaries.
- For docs-only changes, `git diff --check` is enough unless code changes were also made.
- Before finishing code changes, run the narrow relevant test first, then `make check` when feasible.

## Git
- Do not work directly on a divergent `main`.
- Prefer a short-lived branch from `origin/main` for repo changes.
- Keep commits atomic and docs-only changes separate from behavior changes.
- Before final response, inspect `git status --short --branch` and verify the diff.
