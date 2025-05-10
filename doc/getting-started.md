# Getting Started with Deply

This guide will help you get up and running with Deply quickly.

## Installation

To install Deply, use pip:

```bash
pip install deply
```

## Basic Usage

After installation, you can start using Deply by following these steps:

1. Create a configuration file named `deply.yaml` in your project root
2. Run the analysis command:

```bash
deply analyze
```

## Configuration

Before running the tool, you need to create a configuration file that specifies the rules and target files to enforce. The configuration file should be named `deply.yaml` by default, but you can specify a different name using the `--config` option.

### Basic Configuration Example

Here's a simple example of a `deply.yaml` configuration file:

```yaml
deply:
  paths:
    - /path/to/your/project

  exclude_files:
    - ".*\\.venv/.*"

  layers:
    - name: models
      collectors:
        - type: class_inherits
          base_class: "django.db.models.Model"

    - name: views
      collectors:
        - type: file_regex
          regex: ".*/views_api.py"

  ruleset:
    views:
      disallow_layer_dependencies:
        - models
```

For more detailed configuration options and examples, please refer to the [Configuration Guide](configuration.html).
