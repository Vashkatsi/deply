---
layout: default
title: Package by Feature
parent: Architecture Styles
grand_parent: Configuration
nav_order: 9
---

# Package by Feature / Screaming Architecture

Package by Feature groups code by business capability instead of technical
layer. The directory tree should communicate what the application does.

```text
src/app/
├── orders/
├── billing/
├── users/
├── orchestration/
└── shared_kernel/
```

## Complete Configuration

```yaml
deply:
  paths: ["."]
  exclude_files:
    - '.*/\.venv/.*'
    - '.*/tests?/.*'
  layers:
    - name: orders
      collectors:
        - type: directory
          directories: ["src/app/orders"]
    - name: billing
      collectors:
        - type: directory
          directories: ["src/app/billing"]
    - name: users
      collectors:
        - type: directory
          directories: ["src/app/users"]
    - name: orchestration
      collectors:
        - type: directory
          directories: ["src/app/orchestration"]
    - name: shared_kernel
      collectors:
        - type: directory
          directories: ["src/app/shared_kernel"]
  ruleset:
    orders:
      disallow_layer_dependencies: [billing, users]
    billing:
      disallow_layer_dependencies: [orders, users]
    users:
      disallow_layer_dependencies: [orders, billing]
    shared_kernel:
      disallow_layer_dependencies: [orders, billing, users, orchestration]
```

Use orchestration or explicit feature APIs for legitimate collaboration.
Avoid a generic `shared` package that becomes an unowned dependency sink.
Internal layers may still exist inside a feature when its complexity requires
them.

Deply can prevent direct feature imports, but it cannot determine feature
ownership, cohesion, or whether an orchestration dependency is justified.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Screaming Architecture](https://blog.cleancoder.com/uncle-bob/2011/09/30/Screaming-Architecture.html).
