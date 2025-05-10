---
layout: default
title: Rules
nav_order: 6
---

# Rules in Deply

Rules in Deply define how different layers in your architecture can interact with each other. This document explains the different types of rules and how to use them effectively.

## Rule Types

### Layer Dependency Rules

Control which layers can depend on other layers:

```yaml
ruleset:
  views:
    disallow_layer_dependencies:
      - models
```

### Function Decorator Rules

Enforce the use of specific decorators on functions:

```yaml
ruleset:
  tasks:
    enforce_function_decorator_usage:
      - type: function_decorator_name_regex
        decorator_name_regex: "app.task"
```

### Class Inheritance Rules

Ensure classes inherit from specific base classes:

```yaml
ruleset:
  models:
    enforce_inheritance:
      - type: bool
        any_of:
          - type: class_inherits
            base_class: "django.db.models.Model"
          - type: class_inherits
            base_class: "django.contrib.auth.models.AbstractUser"
```

## Rule Configuration

Rules are defined in the `ruleset` section of your `deply.yaml` configuration file:

```yaml
deply:
  ruleset:
    layer_name:
      rule_type:
        - rule_configuration
```

## Common Rule Patterns

### Preventing Direct Model Access

```yaml
ruleset:
  views:
    disallow_layer_dependencies:
      - models
  controllers:
    disallow_layer_dependencies:
      - models
```

### Enforcing Service Layer Pattern

```yaml
ruleset:
  views:
    disallow_layer_dependencies:
      - models
      - repositories
    allow_layer_dependencies:
      - services
```

### Ensuring Task Decorators

```yaml
ruleset:
  tasks:
    enforce_function_decorator_usage:
      - type: function_decorator_name_regex
        decorator_name_regex: "app.task"
```

## Best Practices

1. Start with basic layer dependency rules
2. Add more specific rules as needed
3. Document the reasoning behind complex rules
4. Review and update rules regularly
5. Use rules to enforce team conventions

## Rule Violations

When rules are violated, Deply will report them in the following format:

```plaintext
/path/to/file.py:line_number - Layer 'layer_name' is not allowed to depend on layer 'other_layer'
```

For more information about configuring rules, please refer to the [Configuration Guide](configuration.html).
