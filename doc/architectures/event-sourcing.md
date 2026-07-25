---
layout: default
title: Event Sourcing
parent: Architecture Styles
grand_parent: Configuration
nav_order: 17
---

# Event Sourcing

Event Sourcing stores state changes as an append-only sequence of events and
rebuilds current state or projections from that history. Use it selectively
when auditability, temporal reconstruction, or domain history justifies its
operational cost.

```text
src/app/
├── domain/
├── application/
├── event_store/
├── projections/
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
    - name: domain
      collectors:
        - type: directory
          directories: ["src/app/domain"]
    - name: application
      collectors:
        - type: directory
          directories: ["src/app/application"]
    - name: event_store
      collectors:
        - type: directory
          directories: ["src/app/event_store"]
    - name: projections
      collectors:
        - type: directory
          directories: ["src/app/projections"]
    - name: interface
      collectors:
        - type: directory
          directories: ["src/app/interface"]
  ruleset:
    domain:
      disallow_layer_dependencies: [application, event_store, projections, interface]
      disallow_external_imports: [sqlalchemy, redis, kafka, requests]
    application:
      disallow_layer_dependencies: [event_store, projections, interface]
    event_store:
      disallow_layer_dependencies: [projections, interface]
    projections:
      disallow_layer_dependencies: [application, event_store, interface]
    interface:
      disallow_layer_dependencies: [event_store]
```

Deply can isolate domain events, storage adapters, and projections. It cannot
verify append-only persistence, optimistic concurrency, replay correctness,
event versioning, snapshots, or projection consistency.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

References: [Fowler’s Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html) and [Event Sourcing pattern guidance](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing).
