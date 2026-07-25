---
layout: default
title: FastAPI
parent: Configuration
nav_order: 1
---

# FastAPI Configuration Recipe

This recipe is a starting point for a layered FastAPI project. It is regular
Deply configuration, not a built-in preset. Adapt the source directories and
rules to the architecture the project actually uses.

The example assumes this structure:

```text
src/app/
├── domain/
├── application/
├── infrastructure/
└── interface/
    └── routers/
```

## Complete Configuration

```yaml
deply:
  paths:
    - "."

  exclude_files:
    - '.*/\.venv/.*'
    - '.*/tests?/.*'
    - '.*/migrations/.*'

  layers:
    - name: domain
      collectors:
        - type: directory
          directories:
            - "src/app/domain"

    - name: application
      collectors:
        - type: directory
          directories:
            - "src/app/application"

    - name: infrastructure
      collectors:
        - type: directory
          directories:
            - "src/app/infrastructure"

    - name: interface
      collectors:
        - type: bool
          any_of:
            - type: file_regex
              regex: '.*/routers?/.*\.py$'
            - type: decorator_usage
              decorator_regex: '.*\.(get|post|put|patch|delete)'

  ruleset:
    domain:
      disallow_layer_dependencies:
        - application
        - infrastructure
        - interface
      disallow_external_imports:
        - fastapi
        - starlette
        - pydantic
        - sqlalchemy
        - requests

    application:
      disallow_layer_dependencies:
        - infrastructure
        - interface
```

Validate and run the configuration from the project root:

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

## Route Layout Variants

For projects that keep routes in modules such as `api/routes.py` or
`api/v1/users.py`, replace the interface file collector with a pattern that
matches the actual layout:

```yaml
- type: file_regex
  regex: '.*/api/.*\.py$|.*/routes?\.py$'
```

Decorator collection is useful when route handlers are not kept in dedicated
modules:

```yaml
- type: decorator_usage
  decorator_regex: '.*\.(get|post|put|patch|delete|options|head)'
```

## Pydantic Domain Models

The complete recipe blocks `pydantic` in `domain` to keep transport DTOs
outside business logic. If Pydantic models are an intentional part of the
domain model, remove only `pydantic` from `disallow_external_imports`.

Do not remove `fastapi` or `starlette` unless the domain intentionally owns HTTP
concerns.

## SQLAlchemy Persistence

When SQLAlchemy models live outside the generic infrastructure directory, add
a persistence collector:

```yaml
- name: infrastructure
  collectors:
    - type: bool
      any_of:
        - type: directory
          directories:
            - "src/app/infrastructure"
        - type: file_regex
          regex: '.*/models\.py$|.*/models/.*\.py$'
        - type: class_inherits
          base_class: "sqlalchemy.orm.DeclarativeBase"
```

If SQLAlchemy models are intentionally used as domain entities, remove
`sqlalchemy` from the domain import restriction instead of suppressing each
violation.
