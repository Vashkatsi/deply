---
layout: default
title: Layered / N-tier
parent: Architecture Styles
grand_parent: Configuration
nav_order: 1
---

# Layered / N-tier

Layered architecture groups code by responsibility. A common direction is
presentation → application → domain, with infrastructure serving outer layers.
Use it when the responsibilities are stable and a feature-oriented structure
would not be clearer.

```text
src/app/
├── presentation/
├── application/
├── domain/
└── infrastructure/
```

## Complete Configuration

```yaml
deply:
  paths: ["."]
  exclude_files:
    - '.*/\.venv/.*'
    - '.*/tests?/.*'
    - '.*/migrations/.*'
  layers:
    - name: presentation
      collectors:
        - type: directory
          directories: ["src/app/presentation"]
    - name: application
      collectors:
        - type: directory
          directories: ["src/app/application"]
    - name: domain
      collectors:
        - type: directory
          directories: ["src/app/domain"]
    - name: infrastructure
      collectors:
        - type: directory
          directories: ["src/app/infrastructure"]
  ruleset:
    domain:
      disallow_layer_dependencies: [presentation, application, infrastructure]
      disallow_external_imports: [django, fastapi, flask, sqlalchemy, requests]
    application:
      disallow_layer_dependencies: [presentation, infrastructure]
    infrastructure:
      disallow_layer_dependencies: [presentation]
```

This enforces inward source dependencies. It does not require every request to
pass through every layer. If application code intentionally uses concrete
infrastructure, remove that one restriction rather than introducing empty
interfaces.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Patterns of Enterprise Application Architecture](https://martinfowler.com/books/eaa.html).
