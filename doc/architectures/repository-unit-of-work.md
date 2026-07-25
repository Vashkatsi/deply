---
layout: default
title: Repository + Unit of Work
parent: Architecture Styles
grand_parent: Configuration
nav_order: 20
---

# Repository + Unit of Work

Repositories provide collection-like access to domain objects. A Unit of Work
tracks changes and coordinates persistence for one business transaction.
Application code owns the contracts; infrastructure owns implementations.

```text
src/app/
├── domain/
├── application/
├── persistence/
└── interface/
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
    - name: domain
      collectors:
        - type: directory
          directories: ["src/app/domain"]
    - name: application
      collectors:
        - type: directory
          directories: ["src/app/application"]
    - name: persistence
      collectors:
        - type: directory
          directories: ["src/app/persistence"]
    - name: interface
      collectors:
        - type: directory
          directories: ["src/app/interface"]
  ruleset:
    domain:
      disallow_layer_dependencies: [application, persistence, interface]
      disallow_external_imports: [django, sqlalchemy, peewee]
    application:
      disallow_layer_dependencies: [persistence, interface]
    interface:
      disallow_layer_dependencies: [domain, persistence]
```

Use these patterns when aggregate loading and transaction coordination are real
application concerns. A thin wrapper around every ORM method adds indirection
without providing a domain boundary.

Deply can isolate persistence implementations, but it cannot verify atomic
commits, change tracking, concurrency control, or aggregate consistency.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

References: [Repository](https://martinfowler.com/eaaCatalog/repository.html) and [Unit of Work](https://martinfowler.com/eaaCatalog/unitOfWork.html).
