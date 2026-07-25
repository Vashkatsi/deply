---
layout: default
title: Microservices Monorepo
parent: Architecture Styles
grand_parent: Configuration
nav_order: 11
---

# Microservices Monorepo

In a microservices monorepo, each service owns its implementation and can share
only deliberate contracts or libraries. Source imports must not turn separate
services into a distributed monolith.

```text
services/
├── orders/
├── billing/
└── identity/
packages/
└── contracts/
```

## Complete Configuration

```yaml
deply:
  paths: ["."]
  exclude_files:
    - '.*/\.venv/.*'
    - '.*/tests?/.*'
    - '.*/generated/.*'
  layers:
    - name: orders_service
      collectors:
        - type: directory
          directories: ["services/orders"]
    - name: billing_service
      collectors:
        - type: directory
          directories: ["services/billing"]
    - name: identity_service
      collectors:
        - type: directory
          directories: ["services/identity"]
    - name: shared_contracts
      collectors:
        - type: directory
          directories: ["packages/contracts"]
  ruleset:
    orders_service:
      disallow_layer_dependencies: [billing_service, identity_service]
    billing_service:
      disallow_layer_dependencies: [orders_service, identity_service]
    identity_service:
      disallow_layer_dependencies: [orders_service, billing_service]
    shared_contracts:
      disallow_layer_dependencies: [orders_service, billing_service, identity_service]
```

Deply can prevent source-level service coupling. It cannot prove independent
deployment, database ownership, API compatibility, network resilience, or
team autonomy.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Microservices](https://martinfowler.com/articles/microservices.html).
