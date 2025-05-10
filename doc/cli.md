# Command Line Interface

This document describes the command-line interface of Deply.

## Available Commands

### Analyze Command

The main command for analyzing your project:

```bash
deply analyze
```

### Help Command

Display help information:

```bash
deply --help
```

## Command Line Arguments

### Analyze Command Options

- `--config`: Path to the configuration YAML file (default: `deply.yaml`)
- `--report-format`: Format of the output report (choices: `text`, `json`, `html`, default: `text`)
- `--output`: Output file for the report (if not specified, prints to console)
- `--mermaid`: Generates a Mermaid diagram of layer dependencies
- `--max-violations`: Maximum number of allowed violations before failing (default: 0)
- `--parallel`: Enable parallel processing of code elements

## Examples

### Basic Analysis

```bash
deply analyze
```

### Custom Configuration File

```bash
deply analyze --config=custom_config.yaml
```

### Generate HTML Report

```bash
deply analyze --report-format=html --output=report.html
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

The default output format shows violations in a human-readable text format:

```plaintext
/path/to/your_project/your_project/app1/views_api.py:74 - Layer 'views' is not allowed to depend on layer 'models'
```

### JSON Format

The JSON format provides structured data that can be easily parsed by other tools:

```json
{
  "violations": [
    {
      "file": "/path/to/your_project/your_project/app1/views_api.py",
      "line": 74,
      "message": "Layer 'views' is not allowed to depend on layer 'models'"
    }
  ]
}
```

### HTML Format

The HTML format provides a formatted report that can be viewed in a web browser, with syntax highlighting and better readability.

For more information about:
- Mermaid diagrams, see the [Mermaid Diagrams](mermaid.html) documentation
- Rules and violations, see the [Rules](rules.html) documentation
- Configuration and usage, see the [Configuration Guide](configuration.html) and [Getting Started](getting-started.html) guide
