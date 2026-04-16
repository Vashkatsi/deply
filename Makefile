PYTHON := ./.venv/bin/python
RUFF := ./.venv/bin/ruff
MYPY := ./.venv/bin/mypy
PIP_AUDIT := ./.venv/bin/pip-audit
PRE_COMMIT := ./.venv/bin/pre-commit
MUTMUT := ./.venv/bin/mutmut

.PHONY: help venv-check lint typing security test mutation pre-commit check

help:
	@echo "Available targets:"
	@echo "  make check       - Run lint, typing, security, test"
	@echo "  make test        - Run unit tests"
	@echo "  make mutation    - Run mutation tests"
	@echo "  make lint        - Run ruff"
	@echo "  make typing      - Run mypy"
	@echo "  make security    - Run pip-audit"
	@echo "  make pre-commit  - Run all pre-commit hooks"

venv-check:
	@if [ ! -x "$(PYTHON)" ]; then \
		echo "Error: .venv is missing or not executable at $(PYTHON)."; \
		echo "Create it first, then install dependencies:"; \
		echo "  python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt -r requirements-dev.txt"; \
		exit 1; \
	fi

lint: venv-check
	$(RUFF) check deply tests

typing: venv-check
	$(MYPY) deply

security: venv-check
	$(PIP_AUDIT) -r requirements.txt

test: venv-check
	$(PYTHON) -m unittest discover tests

mutation: venv-check
	$(MUTMUT) run
	$(MUTMUT) export-cicd-stats
	$(PYTHON) -c "import json; report=json.load(open('mutants/mutmut-cicd-stats.json')); print(f\"mutation total={report.get('total', 0)} killed={report.get('killed', 0)} survived={report.get('survived', 0)} no_tests={report.get('no_tests', 0)} timeout={report.get('timeout', 0)} suspicious={report.get('suspicious', 0)} segfault={report.get('segfault', 0)}\")"

pre-commit: venv-check
	$(PRE_COMMIT) run --all-files

check: lint typing security test
