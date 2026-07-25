---
layout: default
title: Clean Architecture
parent: Architecture Styles
grand_parent: Configuration
nav_order: 3
---

# Clean Architecture

Clean Architecture organizes code into concentric policy levels. Dependencies
point toward entities and use cases; frameworks and delivery mechanisms remain
replaceable details.

```text
src/app/
├── entities/
├── use_cases/
├── interface_adapters/
└── frameworks/
```

## Complete Configuration

```yaml
deply:
  paths: ["."]
  exclude_files:
    - '.*/\.venv/.*'
    - '.*/tests?/.*'
  layers:
    - name: entities
      collectors:
        - type: directory
          directories: ["src/app/entities"]
    - name: use_cases
      collectors:
        - type: directory
          directories: ["src/app/use_cases"]
    - name: interface_adapters
      collectors:
        - type: directory
          directories: ["src/app/interface_adapters"]
    - name: frameworks
      collectors:
        - type: directory
          directories: ["src/app/frameworks"]
  ruleset:
    entities:
      disallow_layer_dependencies: [use_cases, interface_adapters, frameworks]
      disallow_external_imports: [django, fastapi, flask, sqlalchemy, requests, httpx]
    use_cases:
      disallow_layer_dependencies: [interface_adapters, frameworks]
    interface_adapters:
      disallow_layer_dependencies: [frameworks]
```

Use the project’s real vocabulary instead of renaming packages only to match
the diagram. Clean, Onion, and Hexagonal architectures share inward dependency
rules; choose one vocabulary and apply it consistently.

Deply can enforce the dependency rule, but it cannot verify runtime dependency
injection or whether abstractions represent useful application boundaries.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Robert C. Martin’s Clean Architecture](https://blog.cleancoder.com/uncle-bob/2011/11/22/Clean-Architecture.html).
