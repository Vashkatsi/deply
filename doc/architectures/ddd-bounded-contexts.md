---
layout: default
title: DDD / Bounded Contexts
parent: Architecture Styles
grand_parent: Configuration
nav_order: 8
---

# DDD / Bounded Contexts

Domain-Driven Design uses bounded contexts to keep models and language valid
inside explicit business boundaries. Deply can enforce package ownership, not
the quality of the domain model or aggregate invariants.

```text
src/app/
├── ordering/{domain,application,infrastructure}/
├── payments/{domain,application,infrastructure}/
└── shared_kernel/
```

## Complete Configuration

```yaml
deply:
  paths: ["."]
  exclude_files:
    - '.*/\.venv/.*'
    - '.*/tests?/.*'
  layers:
    - name: ordering
      collectors:
        - type: directory
          directories: ["src/app/ordering"]
    - name: payments
      collectors:
        - type: directory
          directories: ["src/app/payments"]
    - name: ordering_domain
      collectors:
        - type: directory
          directories: ["src/app/ordering/domain"]
    - name: payments_domain
      collectors:
        - type: directory
          directories: ["src/app/payments/domain"]
    - name: shared_kernel
      collectors:
        - type: directory
          directories: ["src/app/shared_kernel"]
  ruleset:
    ordering:
      disallow_layer_dependencies: [payments]
    payments:
      disallow_layer_dependencies: [ordering]
    ordering_domain:
      disallow_external_imports: [django, fastapi, flask, sqlalchemy, requests]
    payments_domain:
      disallow_external_imports: [django, fastapi, flask, sqlalchemy, requests]
    shared_kernel:
      disallow_layer_dependencies: [ordering, payments]
```

An element under `ordering/domain` belongs to both `ordering` and
`ordering_domain`; the same applies to payments. Deply checks every membership
pair regardless of layer order. Context rules prevent cross-context
dependencies, while domain rules isolate business logic from external packages.
Create a shared kernel only for stable concepts genuinely shared by both
contexts.

Deply cannot verify ubiquitous language, aggregate invariants, context maps, or
the organizational ownership implied by a bounded context.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Domain analysis and bounded contexts](https://learn.microsoft.com/en-us/azure/architecture/microservices/model/domain-analysis).
