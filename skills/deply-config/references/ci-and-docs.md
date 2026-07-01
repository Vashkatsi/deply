# CI and Documentation Snippets

Use these snippets after `deply.yaml` validates.

## Install Commands

Use a pinned Deply version in CI for reproducibility.

`pip`:

```bash
python -m pip install "deply==1.0.0"
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

`pipx`:

```bash
pipx run --spec "deply==1.0.0" deply validate --config=deply.yaml
pipx run --spec "deply==1.0.0" deply analyze --parallel --config=deply.yaml
```

`uv`:

```bash
uvx --from "deply==1.0.0" deply validate --config=deply.yaml
uvx --from "deply==1.0.0" deply analyze --parallel --config=deply.yaml
```

`poetry`:

```bash
poetry add --group dev "deply==1.0.0"
poetry run deply validate --config=deply.yaml
poetry run deply analyze --parallel --config=deply.yaml
```

## Makefile

Add a target that validates the config and runs analysis:

```make
.PHONY: architecture-check

architecture-check:
	deply validate --config=deply.yaml
	deply analyze --parallel --config=deply.yaml
```

For legacy adoption with accepted current debt:

```make
architecture-check:
	deply validate --config=deply.yaml
	deply analyze --parallel --config=deply.yaml --max-violations=$(DEPLY_MAX_VIOLATIONS)
```

Use an exact numeric value in CI, not an untracked environment default.

## GitHub Actions

`pip` install:

```yaml
- name: Install Deply
  run: |
    python -m pip install --upgrade pip
    python -m pip install "deply==1.0.0"

- name: Validate Deply config
  run: deply validate --config=deply.yaml

- name: Check architecture
  run: deply analyze --parallel --report-format=github-actions --config=deply.yaml
```

`uv` install:

```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v5

- name: Validate Deply config
  run: uvx --from "deply==1.0.0" deply validate --config=deply.yaml

- name: Check architecture
  run: uvx --from "deply==1.0.0" deply analyze --parallel --report-format=github-actions --config=deply.yaml
```

Legacy ratchet:

```yaml
- name: Check architecture
  run: deply analyze --parallel --report-format=github-actions --config=deply.yaml --max-violations=12
```

## GitLab CI

```yaml
architecture:
  image: python:3.12
  script:
    - python -m pip install --upgrade pip
    - python -m pip install "deply==1.0.0"
    - deply validate --config=deply.yaml
    - deply analyze --parallel --config=deply.yaml
```

## Documentation

Add a short architecture section to `README.md` or `docs/architecture.md`:

````markdown
## Architecture Checks

This project uses Deply to enforce Python architecture boundaries.

Local check:

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Configured layers:

- `domain`: business rules and entities. No framework or persistence imports.
- `application`: use cases and orchestration.
- `infrastructure`: database, HTTP, queue, SDK, and framework adapters.
- `interface`: CLI, web, API, worker entrypoints.

Suppression policy:

- Existing `deply:ignore` and `deply:ignore-file` comments are reviewed during adoption.
- New suppressions require a specific architectural reason in review.
- Prefer config fixes or a temporary `--max-violations=N` ratchet over hiding violations.

CI behavior:

- New projects should fail on any violation.
- Legacy projects may temporarily use an exact `--max-violations=N` value equal to the current violation count.
- Ratchet values should only decrease.
````

Keep documentation factual. Do not describe rules that are not present in `deply.yaml`.
