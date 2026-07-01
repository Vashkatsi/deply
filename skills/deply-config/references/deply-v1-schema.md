# Deply v1.0.0 Schema Reference

Use this as the source of truth for generated `deply.yaml` files.

## File Shape

Always generate the public YAML shape:

```yaml
deply:
  paths:
    - "."

  exclude_files:
    - '.*/\.venv/.*'
    - '.*/tests?/.*'

  layers:
    - name: layer_name
      collectors:
        - type: directory
          directories:
            - "src/package/path"

  ruleset:
    layer_name:
      disallow_layer_dependencies:
        - other_layer
```

Run commands from the project root when using relative paths.

## Top-Level Keys

- `paths`: non-empty list of existing paths. Use `"."` for the project root unless a narrower source root is clearly better.
- `exclude_files`: list of regex strings.
- `layers`: non-empty list of layer objects.
- `ruleset`: mapping from layer name to rules.

## Collectors

- `directory`
  - `directories`: non-empty list of directory names.
  - Best default for package/module boundaries.
- `file_regex`
  - `regex`: regex matching source file path.
  - Use for framework entrypoints such as views, routes, commands, or adapters.
- `class_name_regex`
  - `class_name_regex`: regex matching class names.
  - Use sparingly for suffix conventions like `.*Service$`.
- `function_name_regex`
  - `function_name_regex`: regex matching function names.
- `class_inherits`
  - `base_class`: fully qualified base class.
  - Use for Django models, DRF views, SQLAlchemy declarative bases, etc.
- `decorator_usage`
  - `decorator_name` or `decorator_regex`.
  - Use for Celery tasks, FastAPI routes, auth-protected handlers, etc.
- `bool`
  - `must`, `any_of`, `must_not`: lists of nested collectors.
  - At least one group must be non-empty.
- `custom`
  - `class`: import path to a `BaseCollector` subclass.
  - Avoid in generated v1 configs unless the project already has one.

All collectors may use optional `exclude_files_regex`.

## Rule Keys

- `disallow_layer_dependencies`
  - List of layer names the source layer must not depend on.
- `disallow_external_imports`
  - List of package roots disallowed in the layer.
  - Use for blocking framework, persistence, HTTP, queue, or SDK imports from domain/application layers.
- `enforce_class_naming`
  - List of rule configs.
- `enforce_function_naming`
  - List of rule configs.
- `enforce_class_decorator_usage`
  - List of rule configs.
- `enforce_function_decorator_usage`
  - List of rule configs.
- `enforce_inheritance`
  - List of rule configs.

Unsupported: `allow_layer_dependencies`, wildcards, severity levels, inline comments inside `ruleset`, and custom rule names.

## Rule Config Types

```yaml
type: class_name_regex
class_name_regex: '.*Service$'
```

```yaml
type: function_name_regex
function_name_regex: '^handle_.*'
```

```yaml
type: class_decorator_name_regex
decorator_name_regex: 'dataclass|pydantic\.dataclasses\.dataclass'
```

```yaml
type: function_decorator_name_regex
decorator_name_regex: 'app\.task|shared_task'
```

```yaml
type: class_inherits
base_class: "django.db.models.Model"
```

```yaml
type: bool
any_of:
  - type: class_inherits
    base_class: "django.db.models.Model"
  - type: class_inherits
    base_class: "django.contrib.auth.models.AbstractUser"
```

## Validation Contract

Always run:

```bash
deply validate --config=deply.yaml
```

Then run:

```bash
deply analyze --parallel --config=deply.yaml
```

If validation fails, fix the config. If analysis fails with violations, decide whether to tighten collectors/excludes, change architecture, or adopt with a temporary ratchet.
