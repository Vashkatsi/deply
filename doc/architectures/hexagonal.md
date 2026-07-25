---
layout: default
title: Hexagonal
parent: Architecture Styles
grand_parent: Configuration
nav_order: 2
---

# Hexagonal / Ports and Adapters

Hexagonal architecture keeps application behavior independent from databases,
web frameworks, queues, and other runtime devices. The core defines ports;
outer adapters implement or invoke them.

```text
src/app/
├── domain/
├── application/
│   └── ports/
├── adapters/
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
    - name: ports
      collectors:
        - type: directory
          directories: ["src/app/application/ports"]
    - name: adapters
      collectors:
        - type: directory
          directories: ["src/app/adapters"]
    - name: interface
      collectors:
        - type: directory
          directories: ["src/app/interface"]
  ruleset:
    domain:
      disallow_layer_dependencies: [application, ports, adapters, interface]
      disallow_external_imports: [django, fastapi, flask, sqlalchemy, requests, httpx]
    application:
      disallow_layer_dependencies: [adapters, interface]
    ports:
      disallow_layer_dependencies: [adapters, interface]
    adapters:
      disallow_layer_dependencies: [interface]
```

Deply can verify dependency direction and framework isolation. It cannot prove
that runtime dependency injection connects every port to the correct adapter.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Alistair Cockburn’s original Hexagonal Architecture article](https://alistaircockburn.com/hexagonal-architecture).
