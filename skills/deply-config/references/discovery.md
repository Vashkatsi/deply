# Discovery

Read this before asking the user questions. Prefer facts from the repository over guesses.

## Repository Shape

Find Python source roots and package boundaries:

```bash
find . -maxdepth 4 -type f \( -name pyproject.toml -o -name setup.py -o -name setup.cfg -o -name requirements.txt \)
find . -maxdepth 4 -type f -name "__init__.py" | sed 's#/__init__.py##' | sort
find . -maxdepth 3 -type d \( -name apps -o -name services -o -name packages -o -name src \)
```

Look for existing architecture signals:

```bash
find . -maxdepth 4 -type d \( -name domain -o -name application -o -name infrastructure -o -name adapters -o -name interface -o -name api \)
find . -maxdepth 4 -type f \( -name "*service*.py" -o -name "*repository*.py" -o -name "*handler*.py" -o -name "*router*.py" -o -name "*view*.py" \)
```

## Frameworks And Tooling

Detect dependencies:

```bash
rg -n "django|fastapi|flask|celery|sqlalchemy|pydantic|requests|httpx|boto3|ccxt" pyproject.toml setup.py setup.cfg requirements*.txt poetry.lock uv.lock Pipfile.lock 2>/dev/null
```

Detect imports when dependency files are incomplete:

```bash
rg -n "^(from|import) (django|fastapi|flask|celery|sqlalchemy|pydantic|requests|httpx|boto3|ccxt)\\b" .
```

## Existing Deply Adoption

Check config, suppressions, CI, and docs:

```bash
find . -maxdepth 4 -type f \( -name "deply.yaml" -o -name "deply.yml" \)
rg -n "deply:ignore|deply:ignore-file" .
find . -maxdepth 4 -type f \( -name Makefile -o -name ".gitlab-ci.yml" -o -path "*/.github/workflows/*" \)
rg -n "deply validate|deply analyze|architecture check|architecture boundary|layer" README* docs doc .github .gitlab-ci.yml Makefile 2>/dev/null
```

## Ask Only After Discovery

Ask the user only for choices not discoverable from files:

- Current-state guardrails or target architecture.
- Strictness: `light`, `medium`, or `strict`.
- Blocking CI or temporary ratchet.
- Whether ORM models are domain entities or persistence adapters.
- Whether monorepo services share one architecture policy.
