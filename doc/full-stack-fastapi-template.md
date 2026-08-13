---
layout: default
title: Full Stack FastAPI Template
parent: FastAPI
grand_parent: Configuration
nav_order: 1
---

# Full Stack FastAPI Template Configuration Recipe

This is a verified baseline for the official
[FastAPI Full Stack template](https://github.com/fastapi/full-stack-fastapi-template)
at [commit `c350936d2888ef16ff4f5549684fd8db54935a89`](https://github.com/fastapi/full-stack-fastapi-template/tree/c350936d2888ef16ff4f5549684fd8db54935a89).
Run it from the generated project root.

## Complete Configuration

```yaml
deply:
  paths:
    - backend/app

  exclude_files:
    - '^alembic/.*'

  layers:
    - name: interface
      collectors:
        - type: bool
          any_of:
            - type: directory
              directories:
                - api
              element_type: function
            - type: directory
              directories:
                - api
              element_type: class
            - type: file_regex
              regex: '^api/main\.py$'
              element_type: variable
            - type: file_regex
              regex: '^main\.py$'
              element_type: function

    - name: data
      collectors:
        - type: file_regex
          regex: '^(crud|models)\.py$'
          element_type: function
        - type: file_regex
          regex: '^(crud|models)\.py$'
          element_type: class

    - name: infrastructure
      collectors:
        - type: bool
          any_of:
            - type: directory
              directories:
                - core
              element_type: function
            - type: directory
              directories:
                - core
              element_type: class
            - type: file_regex
              regex: '^utils\.py$'
              element_type: function
            - type: file_regex
              regex: '^utils\.py$'
              element_type: class

    - name: bootstrap
      collectors:
        - type: file_regex
          regex: '^(backend_pre_start|initial_data|tests_pre_start)\.py$'
          element_type: function

  ruleset:
    interface:
      disallow_layer_dependencies:
        - bootstrap

    data:
      disallow_layer_dependencies:
        - interface
        - bootstrap
      disallow_external_imports:
        - fastapi
        - starlette

    infrastructure:
      disallow_layer_dependencies:
        - interface
        - bootstrap
      disallow_external_imports:
        - fastapi
        - starlette
```

Validate and analyze from that root:

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

## Why This Baseline Is Deliberately Narrow

This configuration is a zero-violation baseline for the template's pragmatic
Active Record-style architecture, not Clean Architecture. It intentionally
allows routes to depend on data and infrastructure, and allows the template's
current data/infrastructure coupling.

The narrow path covers `backend/app`; frontend and tests are outside it.
Alembic is excluded because migration scripts are deployment history, not an
application layer. Deply analyzes static AST dependencies and name resolution,
so it cannot prove FastAPI runtime dependency injection behavior.

## Conditional Hardening Target

Apply this only after splitting SQLModel tables from HTTP schemas, moving direct
SQLModel access out of routes, and introducing transport-neutral `app/services`.
For that target, add the application layer and replace these rules:

```yaml
layers:
  - name: application
    collectors:
      - type: directory
        directories:
          - services
        element_type: function
      - type: directory
        directories:
          - services
        element_type: class

ruleset:
  interface:
    disallow_layer_dependencies:
      - bootstrap
      - data
    disallow_external_imports:
      - sqlmodel
      - sqlalchemy

  application:
    disallow_layer_dependencies:
      - interface
      - bootstrap
    disallow_external_imports:
      - fastapi
      - starlette
      - sqlmodel
      - sqlalchemy

  data:
    disallow_layer_dependencies:
      - interface
      - bootstrap
      - application
    disallow_external_imports:
      - fastapi
      - starlette

  infrastructure:
    disallow_layer_dependencies:
      - interface
      - bootstrap
      - application
    disallow_external_imports:
      - fastapi
      - starlette
```

For a stronger end state, use the [Clean Architecture](architectures/clean.html)
or [Hexagonal](architectures/hexagonal.html) recipes as the boundary model.
