---
layout: default
title: Service Layer
parent: Architecture Styles
grand_parent: Configuration
nav_order: 13
---

# Service Layer

A Service Layer defines the application boundary as business operations. It
coordinates domain behavior and keeps transport concerns out of use cases.

```text
src/app/
├── interface/
├── services/
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
  layers:
    - name: interface
      collectors:
        - type: directory
          directories: ["src/app/interface"]
    - name: services
      collectors:
        - type: directory
          directories: ["src/app/services"]
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
      disallow_layer_dependencies: [interface, services, infrastructure]
      disallow_external_imports: [django, fastapi, flask, sqlalchemy, requests]
    services:
      disallow_layer_dependencies: [interface, infrastructure]
    interface:
      disallow_layer_dependencies: [domain, infrastructure]
```

Keep services focused on application operations. Do not turn the layer into a
collection of unrelated helpers or move behavior out of domain objects merely
to satisfy a naming convention.

Deply can enforce transport and persistence isolation, but it cannot verify
service cohesion, transaction boundaries, or business invariants.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Fowler’s Service Layer](https://martinfowler.com/eaaCatalog/serviceLayer.html).
