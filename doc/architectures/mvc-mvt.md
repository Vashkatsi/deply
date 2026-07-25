---
layout: default
title: MVC / MVT
parent: Architecture Styles
grand_parent: Configuration
nav_order: 21
---

# MVC / MVT

MVC separates model, request/input coordination, and presentation. Django’s MVT
uses “view” for request handling and “template” for presentation. These are
presentation patterns and can coexist with layered or feature-oriented
application architecture.

```text
src/app/
├── models/
├── controllers/
└── presentation/
```

## Complete Configuration

```yaml
deply:
  paths: ["."]
  exclude_files:
    - '.*/\.venv/.*'
    - '.*/tests?/.*'
    - '.*/migrations/.*'
  layers:
    - name: models
      collectors:
        - type: directory
          directories: ["src/app/models"]
    - name: controllers
      collectors:
        - type: directory
          directories: ["src/app/controllers"]
    - name: presentation
      collectors:
        - type: directory
          directories: ["src/app/presentation"]
  ruleset:
    models:
      disallow_layer_dependencies: [controllers, presentation]
    presentation:
      disallow_layer_dependencies: [controllers]
```

Controllers may depend on models; models must not depend on delivery or
presentation code. Templates are not Python and therefore are outside Deply’s
AST analysis. For concrete collectors, see the [Django](../django.html),
[FastAPI](../fastapi.html), and [Flask](../flask.html) recipes.

Deply cannot verify template dependencies, request dispatch, rendered output,
or whether controller responsibilities remain cohesive.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

References: [Fowler’s MVC](https://martinfowler.com/eaaCatalog/modelViewController.html) and [Django’s design philosophies](https://docs.djangoproject.com/en/stable/misc/design-philosophies/).
