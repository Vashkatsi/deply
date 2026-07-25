---
layout: default
title: CQRS
parent: Architecture Styles
grand_parent: Configuration
nav_order: 15
---

# CQRS

Command Query Responsibility Segregation uses different models for changing
state and reading state. Apply it where read and write behavior genuinely
diverge; simple CRUD systems rarely need the extra coordination.

```text
src/app/
├── commands/
├── queries/
├── domain/
├── write_infrastructure/
├── read_infrastructure/
└── interface/
```

## Complete Configuration

```yaml
deply:
  paths: ["."]
  exclude_files:
    - '.*/\.venv/.*'
    - '.*/tests?/.*'
  layers:
    - name: commands
      collectors:
        - type: directory
          directories: ["src/app/commands"]
    - name: queries
      collectors:
        - type: directory
          directories: ["src/app/queries"]
    - name: domain
      collectors:
        - type: directory
          directories: ["src/app/domain"]
    - name: write_infrastructure
      collectors:
        - type: directory
          directories: ["src/app/write_infrastructure"]
    - name: read_infrastructure
      collectors:
        - type: directory
          directories: ["src/app/read_infrastructure"]
    - name: interface
      collectors:
        - type: directory
          directories: ["src/app/interface"]
  ruleset:
    domain:
      disallow_layer_dependencies: [commands, queries, write_infrastructure, read_infrastructure, interface]
    commands:
      disallow_layer_dependencies: [queries, write_infrastructure, read_infrastructure, interface]
    queries:
      disallow_layer_dependencies: [commands, domain, write_infrastructure, interface]
    write_infrastructure:
      disallow_layer_dependencies: [queries, read_infrastructure, interface]
    read_infrastructure:
      disallow_layer_dependencies: [commands, domain, write_infrastructure, interface]
```

This example lets queries use read infrastructure while command handlers own
ports implemented by write infrastructure. Deply cannot verify synchronization,
eventual consistency, idempotency, or command semantics.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

References: [CQRS](https://martinfowler.com/bliki/CQRS.html) and the [CQRS pattern guidance](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs).
