---
layout: default
title: Modular Monolith
parent: Architecture Styles
grand_parent: Configuration
nav_order: 7
---

# Modular Monolith

A modular monolith keeps one deployable application while giving business
modules explicit ownership and dependency boundaries. Modules should not reach
into another module’s infrastructure.

```text
src/app/
├── billing/{domain,application,infrastructure}/
└── identity/{domain,application,infrastructure}/
```

## Complete Configuration

```yaml
deply:
  paths: ["."]
  exclude_files:
    - '.*/\.venv/.*'
    - '.*/tests?/.*'
  layers:
    - name: billing_domain
      collectors:
        - type: directory
          directories: ["src/app/billing/domain"]
    - name: billing_application
      collectors:
        - type: directory
          directories: ["src/app/billing/application"]
    - name: billing_infrastructure
      collectors:
        - type: directory
          directories: ["src/app/billing/infrastructure"]
    - name: identity_domain
      collectors:
        - type: directory
          directories: ["src/app/identity/domain"]
    - name: identity_application
      collectors:
        - type: directory
          directories: ["src/app/identity/application"]
    - name: identity_infrastructure
      collectors:
        - type: directory
          directories: ["src/app/identity/infrastructure"]
  ruleset:
    billing_domain:
      disallow_layer_dependencies: [billing_application, billing_infrastructure, identity_domain, identity_application, identity_infrastructure]
    billing_application:
      disallow_layer_dependencies: [billing_infrastructure, identity_domain, identity_application, identity_infrastructure]
    billing_infrastructure:
      disallow_layer_dependencies: [identity_domain, identity_application, identity_infrastructure]
    identity_domain:
      disallow_layer_dependencies: [identity_application, identity_infrastructure, billing_domain, billing_application, billing_infrastructure]
    identity_application:
      disallow_layer_dependencies: [identity_infrastructure, billing_domain, billing_application, billing_infrastructure]
    identity_infrastructure:
      disallow_layer_dependencies: [billing_domain, billing_application, billing_infrastructure]
```

If modules collaborate through explicit application APIs, model those APIs as
separate layers rather than allowing imports into an entire sibling module.
Deply does not prove transactional or deployment boundaries.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Modular Monolith architecture](https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/common-web-application-architectures#monolithic-applications).
