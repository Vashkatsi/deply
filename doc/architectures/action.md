---
layout: default
title: Use-case Action
parent: Architecture Styles
grand_parent: Configuration
nav_order: 14
---

# Use-case Action Pattern

The Use-case Action pattern represents each application operation with one
focused callable class or function. An action accepts input, coordinates one
use case, and returns a result. Here, “Action” does not mean
Action–Domain–Responder.

```text
src/app/
├── interface/
├── actions/
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
    - name: actions
      collectors:
        - type: directory
          directories: ["src/app/actions"]
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
      disallow_layer_dependencies: [interface, actions, infrastructure]
      disallow_external_imports: [django, fastapi, flask, sqlalchemy, requests]
    actions:
      disallow_layer_dependencies: [interface, infrastructure]
    interface:
      disallow_layer_dependencies: [domain, infrastructure]
```

Actions may define ports or receive dependencies implemented by
infrastructure. Keep one action per use case; do not split trivial operations
into command, handler, service, and action layers simultaneously.

Deply can enforce layer imports, but it cannot verify that an action represents
exactly one cohesive use case or that its transaction boundary is correct.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Related recipes: [Service Layer](service-layer.html) and [Vertical Slice](vertical-slice.html).

The name is a pragmatic class-per-use-case convention rather than a formally
standardized pattern. Its application-boundary role is closest to Fowler’s
[Service Layer](https://martinfowler.com/eaaCatalog/serviceLayer.html).
