---
layout: default
title: Microkernel / Plugin
parent: Architecture Styles
grand_parent: Configuration
nav_order: 5
---

# Microkernel / Plugin

A microkernel keeps stable behavior in a small core and adds optional
capabilities through plugins. Use it when extensions have independent
lifecycles and communicate through a deliberately small core contract.

```text
src/app/
├── core/
├── plugins/
│   ├── payments/
│   └── reporting/
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
    - name: core
      collectors:
        - type: directory
          directories: ["src/app/core"]
    - name: payments_plugin
      collectors:
        - type: directory
          directories: ["src/app/plugins/payments"]
    - name: reporting_plugin
      collectors:
        - type: directory
          directories: ["src/app/plugins/reporting"]
    - name: interface
      collectors:
        - type: directory
          directories: ["src/app/interface"]
  ruleset:
    core:
      disallow_layer_dependencies: [payments_plugin, reporting_plugin, interface]
    payments_plugin:
      disallow_layer_dependencies: [reporting_plugin, interface]
    reporting_plugin:
      disallow_layer_dependencies: [payments_plugin, interface]
```

Add one layer per plugin whose isolation matters. Deply can reject source
imports between plugins; it cannot verify discovery, version compatibility,
sandboxing, or plugin lifecycle behavior.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Fowler’s Plugin pattern](https://martinfowler.com/eaaCatalog/plugin.html).
