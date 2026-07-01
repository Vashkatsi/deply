# Deply Rule Presets

Use these presets as starting points, then adapt to the discovered project structure.

## Light

Goal: document obvious boundaries and catch accidental direct dependencies.

Use when:
- First Deply adoption.
- Legacy code has unknown coupling.
- User wants low false positives.

Pattern:
- Create layers from existing top-level packages or obvious directories.
- Prefer `directory` collectors.
- Add only high-confidence `disallow_layer_dependencies`.
- Exclude tests, migrations, generated files, virtualenvs, build output, and vendored code.
- CI can start as validate-only plus optional non-blocking analysis.

Example:

```yaml
deply:
  paths:
    - "."
  exclude_files:
    - '.*/\.venv/.*'
    - '.*/tests?/.*'
    - '.*/migrations/.*'
  layers:
    - name: domain
      collectors:
        - type: directory
          directories:
            - "src/app/domain"
    - name: infrastructure
      collectors:
        - type: directory
          directories:
            - "src/app/infrastructure"
  ruleset:
    domain:
      disallow_layer_dependencies:
        - infrastructure
```

## Medium

Goal: enforce normal layered or hexagonal architecture boundaries.

Use when:
- Project has recognizable domain/application/infrastructure/interface layers.
- Team wants CI to block new architecture regressions.

Pattern:
- Layers: `domain`, `application`, `infrastructure`, `interface` or equivalent project names.
- `domain` must not depend on application, infrastructure, or interface.
- `application` must not depend on interface, and usually not directly on infrastructure unless project uses pragmatic service wiring.
- `domain` disallows framework, ORM, HTTP, queue, cloud SDK, and exchange/client imports.
- `application` disallows interface frameworks and low-level transport packages unless it owns ports.

Example:

```yaml
deply:
  paths:
    - "."
  exclude_files:
    - '.*/\.venv/.*'
    - '.*/tests?/.*'
    - '.*/migrations/.*'
  layers:
    - name: domain
      collectors:
        - type: directory
          directories:
            - "src/app/domain"
    - name: application
      collectors:
        - type: directory
          directories:
            - "src/app/application"
    - name: infrastructure
      collectors:
        - type: directory
          directories:
            - "src/app/infrastructure"
    - name: interface
      collectors:
        - type: directory
          directories:
            - "src/app/api"
  ruleset:
    domain:
      disallow_layer_dependencies:
        - application
        - infrastructure
        - interface
      disallow_external_imports:
        - django
        - fastapi
        - flask
        - sqlalchemy
        - requests
    application:
      disallow_layer_dependencies:
        - interface
```

## Strict

Goal: enforce target architecture, not just current layout.

Use when:
- New project.
- Architecture boundaries are already intentional.
- User accepts initial cleanup or ratchet adoption.

Pattern:
- Use explicit architecture layers and framework adapter layers.
- Domain has no framework, persistence, HTTP, queue, cloud, SDK, exchange, or CLI imports.
- Application has no web framework imports and only depends inward.
- Interface/adapters depend inward but not sideways.
- Add naming/decorator/inheritance rules only where the project already follows the convention or user explicitly wants it.
- CI should run validate and analyze.

Strict adoption in legacy repos:
- Do not weaken the rules silently.
- If current violations are accepted temporarily, set `--max-violations=N` to the exact current count and document that it must only decrease.

Example CI command:

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml --max-violations=0
```
