PYTHON := ./.venv/bin/python
RUFF := ./.venv/bin/ruff
MYPY := ./.venv/bin/mypy
PIP_AUDIT := ./.venv/bin/pip-audit
PRE_COMMIT := ./.venv/bin/pre-commit

.PHONY: help venv-check lint typing security test pre-commit check

help:
	@echo "Available targets:"
	@echo "  make check       - Run lint, typing, security, test"
	@echo "  make test        - Run unit tests"
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

pre-commit: venv-check
	$(PRE_COMMIT) run --all-files

check: lint typing security test
