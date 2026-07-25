---
layout: default
title: Active Record
parent: Architecture Styles
grand_parent: Configuration
nav_order: 18
---

# Active Record

Active Record combines data, persistence operations, and some domain behavior
in model objects. It fits CRUD-oriented applications and frameworks where the
ORM model is an intentional application boundary.

```text
src/app/
├── interface/
├── services/
└── models/
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
    - name: interface
      collectors:
        - type: directory
          directories: ["src/app/interface"]
    - name: services
      collectors:
        - type: directory
          directories: ["src/app/services"]
    - name: models
      collectors:
        - type: directory
          directories: ["src/app/models"]
  ruleset:
    models:
      disallow_layer_dependencies: [interface, services]
    services:
      disallow_layer_dependencies: [interface]
```

Controllers may use models directly in a deliberately simple application. Use
the service layer only when workflows span multiple models or external
resources. Do not claim persistence independence while domain behavior depends
on ORM model APIs.

Deply can keep models independent from delivery code, but it cannot verify ORM
mapping correctness, transaction boundaries, or model cohesion.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Fowler’s Active Record](https://martinfowler.com/eaaCatalog/activeRecord.html).
