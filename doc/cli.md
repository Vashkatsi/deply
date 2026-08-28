---
layout: default
title: CLI
nav_order: 8
---

# Command Line Interface

This document describes the command-line interface of Deply.

## Available Commands

### Analyze Command

The main command for analyzing your project:

```bash
deply analyze
```

Analysis validates the configuration first and exits with status `1` without
scanning project files when validation fails. It also exits with status `1`
when files cannot be read or parsed, no Python files are found, or no code
elements map to configured layers. Completed reports include analysis
completeness metrics. Incomplete analysis writes the available metrics to
standard error and does not generate a report.

### Validate Command

Validate your configuration without analyzing project files:

```bash
deply validate
```

### Help Command

Display help information:

```bash
deply --help
```

## Command Line Arguments

### Analyze Command Options

- `--config`: Path to the configuration YAML file (default: `deply.yaml`)
- `--report-format`: Format of the output report (choices: `text`, `json`, `github-actions`, default: `text`)
- `--output`: Output file for the report (if not specified, prints to console)
- `--mermaid`: Generates a Mermaid diagram of layer dependencies
- `--max-violations`: Maximum number of allowed violations before failing (default: 0)
- `--parallel`: Enable parallel processing of code elements

### Validate Command Options

- `--config`: Path to the configuration YAML file (default: `deply.yaml`)

## Examples

### Basic Analysis

```bash
deply analyze
```

### Custom Configuration File

```bash
deply analyze --config=custom_config.yaml
```

### Validate Configuration

```bash
deply validate --config=custom_config.yaml
```

### Generate GitHub Actions Report

```bash
deply analyze --report-format=github-actions
```

### Generate Mermaid Diagram

```bash
deply analyze --mermaid
```

### Allow Some Violations

```bash
deply analyze --max-violations=5
```

### Enable Parallel Processing

```bash
deply analyze --parallel
```

## Output Formats

### Text Format

The default output format shows violations and a separate completeness section:

```plaintext
/path/to/your_project/your_project/app1/views_api.py:74:4 - Layer 'views' is not allowed to depend on layer 'models'. Dependency type: function_call.

Analysis completeness
files_discovered: 12
files_excluded: 2
files_included: 10
```

### JSON Format

The JSON format provides structured data that can be easily parsed by other tools:

```json
{
  "total_violations": 1,
  "by_type": {
    "disallowed_dependency": 1
  },
  "violations": [
    {
      "file": "/path/to/your_project/your_project/app1/views_api.py",
      "element_name": "list_users",
      "element_type": "function",
      "line": 74,
      "column": 4,
      "message": "Layer 'views' is not allowed to depend on layer 'models'. Dependency type: function_call.",
      "violation_type": "disallowed_dependency"
    }
  ],
  "metrics": {
    "files_discovered": 12,
    "files_excluded": 2,
    "files_included": 10,
    "files_parsed": 10,
    "files_parse_failed": 0,
    "files_mapped": 8,
    "files_unmapped": 2,
    "elements_mapped": 31,
    "elements_overlapping": 3,
    "dependencies_detected": 47
  }
}
```

File metrics count unique Python paths. `files_parsed` means the collection
pass parsed the file successfully. `files_mapped` and `files_unmapped`
partition parsed files. `dependencies_detected` counts raw dependency events
before layer-pair expansion, suppression, and violation checks. GitHub Actions
reports expose the same metrics as comment lines without changing annotations.

For more information about:
- Mermaid diagrams, see the [Mermaid Diagrams](mermaid.html) documentation
- Rules and violations, see the [Rules](rules.html) documentation
- Configuration and usage, see the [Configuration Guide](configuration.html) and [Getting Started](getting-started.html) guide
