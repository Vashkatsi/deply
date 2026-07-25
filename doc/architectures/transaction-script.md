---
layout: default
title: Transaction Script
parent: Architecture Styles
grand_parent: Configuration
nav_order: 12
---

# Transaction Script

Transaction Script organizes business logic as procedures, each handling one
request or business transaction. It is a good default for simple domains where
a rich object model would add ceremony without reducing complexity.

```text
src/app/
├── interface/
├── transactions/
└── data_access/
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
    - name: transactions
      collectors:
        - type: directory
          directories: ["src/app/transactions"]
    - name: data_access
      collectors:
        - type: directory
          directories: ["src/app/data_access"]
  ruleset:
    interface:
      disallow_layer_dependencies: [data_access]
    transactions:
      disallow_layer_dependencies: [interface]
    data_access:
      disallow_layer_dependencies: [interface, transactions]
```

Transaction scripts may call data access directly. Move behavior into a domain
model or service layer only when duplication and business invariants make the
procedural model difficult to maintain.

Deply can enforce the package direction, but it cannot determine whether a
transaction script has become too complex or whether its transaction is atomic.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Fowler’s Transaction Script](https://martinfowler.com/eaaCatalog/transactionScript.html).
