---
layout: default
title: Onion Architecture
parent: Architecture Styles
grand_parent: Configuration
nav_order: 4
---

# Onion Architecture

Onion Architecture places an independent domain model at the center, followed
by domain services and application services. Infrastructure stays at the edge
and implements interfaces owned by inner layers.

```text
src/app/
├── domain_model/
├── domain_services/
├── application/
└── infrastructure/
```

## Complete Configuration

```yaml
deply:
  paths: ["."]
  exclude_files:
    - '.*/\.venv/.*'
    - '.*/tests?/.*'
  layers:
    - name: domain_model
      collectors:
        - type: directory
          directories: ["src/app/domain_model"]
    - name: domain_services
      collectors:
        - type: directory
          directories: ["src/app/domain_services"]
    - name: application
      collectors:
        - type: directory
          directories: ["src/app/application"]
    - name: infrastructure
      collectors:
        - type: directory
          directories: ["src/app/infrastructure"]
  ruleset:
    domain_model:
      disallow_layer_dependencies: [domain_services, application, infrastructure]
      disallow_external_imports: [django, fastapi, flask, sqlalchemy, requests]
    domain_services:
      disallow_layer_dependencies: [application, infrastructure]
    application:
      disallow_layer_dependencies: [infrastructure]
```

Do not create domain services only to mirror the diagram. Keep behavior on
domain objects until a real operation spans multiple domain concepts.

Deply can enforce inward source dependencies, but it cannot verify runtime
dependency inversion or the quality of domain-service boundaries.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Jeffrey Palermo’s Onion Architecture series](https://jeffreypalermo.com/2008/07/).
