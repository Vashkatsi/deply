---
layout: default
title: Data Mapper
parent: Architecture Styles
grand_parent: Configuration
nav_order: 19
---

# Data Mapper

Data Mapper keeps in-memory domain objects independent from database schemas
and persistence APIs. Mapper implementations translate between the two.

```text
src/app/
├── domain/
├── application/
├── mappers/
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
    - name: mappers
      collectors:
        - type: directory
          directories: ["src/app/mappers"]
    - name: interface
      collectors:
        - type: directory
          directories: ["src/app/interface"]
  ruleset:
    domain:
      disallow_layer_dependencies: [application, mappers, interface]
      disallow_external_imports: [django, sqlalchemy, peewee]
    application:
      disallow_layer_dependencies: [mappers, interface]
    interface:
      disallow_layer_dependencies: [domain, mappers]
```

Mapper interfaces can live in application code, with concrete implementations
in `mappers`. Deply can detect ORM imports in the domain; it cannot verify
mapping completeness, identity handling, or transaction behavior.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Fowler’s Data Mapper](https://martinfowler.com/eaaCatalog/dataMapper.html).
