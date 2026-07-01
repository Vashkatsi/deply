# Framework Presets

Apply only when imports, dependencies, or filenames show the framework is used.

## Django

Common collectors:

```yaml
- name: models
  collectors:
    - type: bool
      any_of:
        - type: class_inherits
          base_class: "django.db.models.Model"
        - type: class_inherits
          base_class: "django.contrib.auth.models.AbstractUser"
```

```yaml
- name: views
  collectors:
    - type: file_regex
      regex: '.*/views\.py$|.*/views/.*\.py$'
```

Strict domain imports to block:

```yaml
disallow_external_imports:
  - django
  - rest_framework
  - celery
  - requests
  - sqlalchemy
```

Usually exclude migrations:

```yaml
exclude_files:
  - '.*/migrations/.*'
```

## FastAPI

Common collectors:

```yaml
- name: interface
  collectors:
    - type: bool
      any_of:
        - type: file_regex
          regex: '.*/routers?/.*\.py$'
        - type: decorator_usage
          decorator_regex: '.*\.(get|post|put|patch|delete)'
```

Strict domain imports to block:

```yaml
disallow_external_imports:
  - fastapi
  - starlette
  - pydantic
  - sqlalchemy
  - requests
```

Block `pydantic` from domain only when the target architecture separates DTOs from domain objects.

## Flask

Common collectors:

```yaml
- name: interface
  collectors:
    - type: bool
      any_of:
        - type: file_regex
          regex: '.*/routes?\.py$|.*/views?\.py$|.*/blueprints?/.*\.py$'
        - type: decorator_usage
          decorator_regex: '.*\.route'
```

Strict domain imports to block:

```yaml
disallow_external_imports:
  - flask
  - werkzeug
  - sqlalchemy
  - requests
```

## Celery

Common collectors:

```yaml
- name: tasks
  collectors:
    - type: bool
      any_of:
        - type: file_regex
          regex: '.*/tasks\.py$|.*/tasks/.*\.py$'
        - type: decorator_usage
          decorator_regex: ".*task|shared_task"
```

Decorator rule:

```yaml
ruleset:
  tasks:
    enforce_function_decorator_usage:
      - type: function_decorator_name_regex
        decorator_name_regex: '.*task|shared_task'
```

Do not force this rule if the task layer contains helper functions.

## SQLAlchemy

Common collectors:

```yaml
- name: persistence
  collectors:
    - type: bool
      any_of:
        - type: file_regex
          regex: '.*/models\.py$|.*/models/.*\.py$'
        - type: class_inherits
          base_class: "sqlalchemy.orm.DeclarativeBase"
```

Strict domain imports to block:

```yaml
disallow_external_imports:
  - sqlalchemy
  - alembic
```

If the project uses SQLAlchemy models as domain entities, ask whether the target is current-state guardrails or persistence isolation before blocking `sqlalchemy` in domain.
