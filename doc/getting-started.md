---
layout: default
title: Getting Started
nav_order: 2
---

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
2. Validate the configuration:

```bash
deply validate --config=deply.yaml
```

3. Run the analysis command:

```bash
deply analyze
```

`python -m deply` is equivalent to the `deply` command, which helps when the console script is not on `PATH`:

```bash
deply analyze
python -m deply analyze
```

You can also use the [Deply Config Agent Skill](skills.html) with Codex, Claude Code, or another Agent Skills-compatible assistant to generate the configuration interactively.

## Configuration

Before running the tool, you need to create a configuration file that specifies the rules and target files to enforce. The configuration file should be named `deply.yaml` by default, but you can specify a different name using the `--config` option. Starting with Deply v1.3.2 on Python 3.11+, the same configuration can live in a `[tool.deply]` table in `pyproject.toml`; see [Using pyproject.toml](configuration.html#using-pyprojecttoml).

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
