---
layout: default
title: Vertical Slice
parent: Architecture Styles
grand_parent: Configuration
nav_order: 10
---

# Vertical Slice

Vertical Slice Architecture groups all code needed for one request or use case
and minimizes coupling between slices. Each slice can use the simplest internal
design that fits its behavior.

```text
src/app/features/orders/
├── create/
├── get/
├── cancel/
└── shared/
```

## Complete Configuration

```yaml
deply:
  paths: ["."]
  exclude_files:
    - '.*/\.venv/.*'
    - '.*/tests?/.*'
  layers:
    - name: create_order
      collectors:
        - type: directory
          directories: ["src/app/features/orders/create"]
    - name: get_order
      collectors:
        - type: directory
          directories: ["src/app/features/orders/get"]
    - name: cancel_order
      collectors:
        - type: directory
          directories: ["src/app/features/orders/cancel"]
    - name: order_shared
      collectors:
        - type: directory
          directories: ["src/app/features/orders/shared"]
  ruleset:
    create_order:
      disallow_layer_dependencies: [get_order, cancel_order]
    get_order:
      disallow_layer_dependencies: [create_order, cancel_order]
    cancel_order:
      disallow_layer_dependencies: [create_order, get_order]
    order_shared:
      disallow_layer_dependencies: [create_order, get_order, cancel_order]
```

Only extract shared code after multiple slices need the same stable concept.
Deply can reject sibling imports; it cannot determine whether a slice is
cohesive or whether duplication should be refactored.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Jimmy Bogard’s Vertical Slice Architecture](https://www.jimmybogard.com/vertical-slice-architecture/).
