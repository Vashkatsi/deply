---
layout: default
title: Django
parent: Configuration
nav_order: 2
---

# Django Configuration Recipe

This recipe treats Django models as persistence adapters and views as the
interface layer. It is regular Deply configuration, not a built-in preset.
Adapt the directories and boundaries when the project uses Django Active
Record models as its domain model.

The example assumes domain and application code are separated from Django
adapters:

```text
src/app/
├── domain/
├── application/
├── infrastructure/
└── web/
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
        - type: bool
          any_of:
            - type: directory
              directories:
                - "src/app/infrastructure"
            - type: class_inherits
              base_class: "django.db.models.Model"
            - type: class_inherits
              base_class: "django.contrib.auth.models.AbstractUser"

    - name: interface
      collectors:
        - type: file_regex
          regex: '.*/views\.py$|.*/views/.*\.py$'

  ruleset:
    domain:
      disallow_layer_dependencies:
        - application
        - infrastructure
        - interface
      disallow_external_imports:
        - django
        - rest_framework
        - celery
        - requests
        - sqlalchemy

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

## Django REST Framework

For class-based DRF views, combine file and inheritance collectors:

```yaml
- name: interface
  collectors:
    - type: bool
      any_of:
        - type: file_regex
          regex: '.*/views\.py$|.*/views/.*\.py$|.*/api/.*\.py$'
        - type: class_inherits
          base_class: "rest_framework.views.APIView"
        - type: class_inherits
          base_class: "rest_framework.generics.GenericAPIView"
```

Add the concrete base classes used by the project rather than trying to match
every DRF class.

## Active Record as the Domain Model

Some Django projects intentionally use ORM models as domain entities. In that
case, include Django model inheritance in the domain collector:

```yaml
- name: domain
  collectors:
    - type: bool
      any_of:
        - type: directory
          directories:
            - "src/app/domain"
        - type: class_inherits
          base_class: "django.db.models.Model"
        - type: class_inherits
          base_class: "django.contrib.auth.models.AbstractUser"
```

Remove `django` from the domain import restriction and remove the same model
collectors from `infrastructure`. Keep `rest_framework`, `celery`, and HTTP
clients restricted unless they are also intentional domain dependencies.

## Migrations

Generated migrations should normally stay outside architecture analysis:

```yaml
exclude_files:
  - '.*/migrations/.*'
```

Analyze migrations only when dependencies inside migration code are part of
the architecture contract.

## Celery Tasks

Add a task layer when task entrypoints are architecturally relevant:

```yaml
- name: tasks
  collectors:
    - type: bool
      any_of:
        - type: file_regex
          regex: '.*/tasks\.py$|.*/tasks/.*\.py$'
        - type: decorator_usage
          decorator_regex: '.*task|shared_task'
```

Do not enforce a task decorator on every function when task modules also
contain helper functions.
