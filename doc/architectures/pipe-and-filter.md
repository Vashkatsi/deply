---
layout: default
title: Pipe-and-Filter
parent: Architecture Styles
grand_parent: Configuration
nav_order: 6
---

# Pipe-and-Filter

Pipe-and-Filter decomposes processing into independent stages connected by
stable data contracts. Stages should not import sibling implementations.

```text
src/pipeline/
├── contracts/
├── parse/
├── validate/
├── enrich/
└── adapters/
```

## Complete Configuration

```yaml
deply:
  paths: ["."]
  exclude_files:
    - '.*/\.venv/.*'
    - '.*/tests?/.*'
  layers:
    - name: contracts
      collectors:
        - type: directory
          directories: ["src/pipeline/contracts"]
    - name: parse_filter
      collectors:
        - type: directory
          directories: ["src/pipeline/parse"]
    - name: validate_filter
      collectors:
        - type: directory
          directories: ["src/pipeline/validate"]
    - name: enrich_filter
      collectors:
        - type: directory
          directories: ["src/pipeline/enrich"]
    - name: adapters
      collectors:
        - type: directory
          directories: ["src/pipeline/adapters"]
  ruleset:
    contracts:
      disallow_layer_dependencies: [parse_filter, validate_filter, enrich_filter, adapters]
    parse_filter:
      disallow_layer_dependencies: [validate_filter, enrich_filter, adapters]
    validate_filter:
      disallow_layer_dependencies: [parse_filter, enrich_filter, adapters]
    enrich_filter:
      disallow_layer_dependencies: [parse_filter, validate_filter, adapters]
```

Deply can enforce independent stage implementations and stable shared
contracts. It cannot prove ordering, backpressure, retries, streaming behavior,
or message compatibility.

## Validate

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

Reference: [Pipes and Filters pattern](https://www.enterpriseintegrationpatterns.com/patterns/messaging/PipesAndFilters.html).
