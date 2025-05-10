---
layout: default
title: Configuration
---

# Configuration Guide

This guide explains how to configure Deply for your project.

## Configuration File Structure

The configuration file (`deply.yaml`) has the following structure:

```yaml
deply:
  paths:
    - /path/to/your/project

  exclude_files:
    - ".*\\.venv/.*"

  layers:
    - name: layer_name
      collectors:
        - type: collector_type
          # collector specific configuration

  ruleset:
    layer_name:
      disallow_layer_dependencies:
        - other_layer_name
```

## Layer Definitions

Layers are the core concept in Deply. They represent different parts of your application architecture. Each layer can have multiple collectors that define which code elements belong to that layer.

### Example Layer Configuration

```yaml
layers:
  - name: models
    collectors:
      - type: class_inherits
        base_class: "django.db.models.Model"

  - name: services
    collectors:
      - type: bool
        must:
          - type: class_name_regex
            class_name_regex: ".*Service$"
```

## Rules and Collectors

### Layer Rules

Rules define how layers can interact with each other:

```yaml
ruleset:
  views:
    disallow_layer_dependencies:
      - models
```

### Collectors

Collectors define how code elements are collected into layers. See the [Collectors Reference](collectors.html) for detailed information about each collector type.

## Advanced Configuration Examples

### Complex Layer Definition

```yaml
- name: services
  collectors:
    - type: bool
      must:
        - type: class_name_regex
          class_name_regex: ".*Service$"
      must_not:
        - type: file_regex
          regex: ".*/excluded_folder_name/.*"
        - type: decorator_usage
          decorator_name: "deprecated_service"
```

### Multiple Layer Rules

```yaml
ruleset:
  views:
    disallow_layer_dependencies:
      - models
  tasks:
    enforce_function_decorator_usage:
      - type: function_decorator_name_regex
        decorator_name_regex: "app.task"
```

## Best Practices

1. Start with a simple configuration and gradually add complexity
2. Use meaningful layer names that reflect your architecture
3. Keep collector rules as specific as possible
4. Document your layer dependencies and rules
5. Regularly review and update your configuration as your project evolves

For more detailed information about collectors and their configuration options, please refer to the [Collectors Reference](collectors.html).
