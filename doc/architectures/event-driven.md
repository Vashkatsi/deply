---
layout: default
title: Event-Driven
parent: Architecture Styles
grand_parent: Configuration
nav_order: 16
---

# Event-Driven Architecture

Event-driven code reacts to facts represented as events. Domain and application
logic should not depend on a concrete broker or transport client.

```text
src/app/
├── domain/
├── application/
├── event_handlers/
└── broker_adapters/
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
    - name: event_handlers
      collectors:
        - type: directory
          directories: ["src/app/event_handlers"]
    - name: broker_adapters
      collectors:
        - type: directory
          directories: ["src/app/broker_adapters"]
  ruleset:
    domain:
      disallow_layer_dependencies: [application, event_handlers, broker_adapters]
      disallow_external_imports: [celery, kafka, pika, redis]
    application:
      disallow_layer_dependencies: [event_handlers, broker_adapters]
    event_handlers:
      disallow_layer_dependencies: [broker_adapters]
```

Handlers translate incoming messages into application calls; broker adapters
own transport details. Deply cannot prove delivery guarantees, ordering,
deduplication, retries, schema compatibility, or idempotency.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Event-driven architecture style](https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/event-driven).
