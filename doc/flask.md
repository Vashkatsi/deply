---
layout: default
title: Flask
parent: Configuration
nav_order: 3
---

# Flask Configuration Recipe

This recipe treats routes, views, and blueprints as interface adapters. It is
regular Deply configuration, not a built-in preset. Adapt the directories and
collectors to the conventions used by the project.

The example assumes this structure:

```text
src/app/
├── domain/
├── application/
├── infrastructure/
└── interface/
    └── blueprints/
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
              regex: '.*/routes?\.py$|.*/views?\.py$|.*/blueprints?/.*\.py$'
            - type: decorator_usage
              decorator_regex: '.*\.route'

  ruleset:
    domain:
      disallow_layer_dependencies:
        - application
        - infrastructure
        - interface
      disallow_external_imports:
        - flask
        - werkzeug
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

## Route and Blueprint Layouts

For a project with a dedicated `api` package, replace the interface file
collector with:

```yaml
- type: file_regex
  regex: '.*/api/.*\.py$|.*/blueprints?/.*\.py$'
```

Decorator collection covers functions registered with `app.route` or
`blueprint.route`:

```yaml
- type: decorator_usage
  decorator_regex: '.*\.route'
```

Keep both collectors when route handlers are split between dedicated modules
and colocated decorators.

## Class-Based Views

Add the base classes used by the project:

```yaml
- name: interface
  collectors:
    - type: bool
      any_of:
        - type: file_regex
          regex: '.*/routes?\.py$|.*/views?\.py$|.*/blueprints?/.*\.py$'
        - type: decorator_usage
          decorator_regex: '.*\.route'
        - type: class_inherits
          base_class: "flask.views.MethodView"
```

## SQLAlchemy Persistence

When SQLAlchemy models are persistence adapters, extend the infrastructure
collector:

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

Keep `sqlalchemy` blocked in `domain` for persistence isolation. If ORM models
are intentionally used as domain entities, remove that package restriction
instead of suppressing each violation.
