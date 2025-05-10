# Collectors Reference

This document provides detailed information about the different types of collectors available in Deply.

## BoolCollector

The `BoolCollector` allows combining other collectors with logical operations.

### Configuration Options

- `type`: `"bool"`
- `must` (optional): A list of collectors where all must match
- `any_of` (optional): A list of collectors where at least one must match
- `must_not` (optional): A list of collectors where none must match

### Example

```yaml
- type: bool
  must:
    - type: class_name_regex
      class_name_regex: ".*Service$"
  any_of:
    - type: decorator_usage
      decorator_name: "transactional"
    - type: decorator_usage
      decorator_name: "cacheable"
  must_not:
    - type: file_name_regex
      regex: ".*test.*"
```

## ClassInheritsCollector

Collects classes that inherit from a specified base class.

### Configuration Options

- `type`: `"class_inherits"`
- `base_class`: The fully qualified name of the base class to match
- `exclude_files_regex` (optional): Regular expression to exclude certain files

### Example

```yaml
- type: class_inherits
  base_class: "django.db.models.Model"
  exclude_files_regex: ".*test.*"
```

## ClassNameRegexCollector

Collects classes whose names match a specified regular expression.

### Configuration Options

- `type`: `"class_name_regex"`
- `class_name_regex`: Regular expression to match class names
- `exclude_files_regex` (optional): Regular expression to exclude certain files

### Example

```yaml
- type: class_name_regex
  class_name_regex: ".*Service$"
  exclude_files_regex: ".*excluded_folder_name.*"
```

## FunctionNameRegexCollector

Collects functions whose names match a specified regular expression.

### Configuration Options

- `type`: `"function_name_regex"`
- `function_name_regex`: Regular expression to match function names
- `exclude_files_regex` (optional): Regular expression to exclude certain files

### Example

```yaml
- type: function_name_regex
  function_name_regex: "^helper_.*"
  exclude_files_regex: ".*test.*"
```

## Best Practices for Collectors

1. Use specific and meaningful regular expressions
2. Combine collectors using BoolCollector for complex conditions
3. Use exclude_files_regex to filter out test files and other unwanted matches
4. Keep collector configurations as simple as possible
5. Document complex collector configurations

For more information about using collectors in your configuration, please refer to the [Configuration Guide](configuration.md). 