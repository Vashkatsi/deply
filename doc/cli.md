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
- `--report-format`: Format of the output report (choices: `text`, `json`, `github-actions`, `sarif`, default: `text`)
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

### SARIF Report

```bash
deply analyze --report-format=sarif --output=deply.sarif
```

SARIF 2.1.0 output contains rule IDs, messages, file locations, and metrics in
`runs[0].properties.metrics`. Results use `warning` severity and line-level
locations. Columns are omitted because Python AST offsets count UTF-8 bytes.
Files inside the analysis working directory use relative URIs with an explicit
source root; files outside it use absolute file URIs. Run from the repository
root for GitHub uploads. Existing dependency-inference limitations still apply.

An empty successful report has no results. Violations above `--max-violations`
still produce a report and exit with status `1`. Invalid configuration or
incomplete analysis exits `1` without writing a new report; an existing output
file is not deleted. With `--mermaid`, use `--output` to keep diagram text out
of the SARIF document.

For an existing GitHub Actions job that checks out the sources and installs
Deply, add these steps. The job needs `security-events: write` permission;
private repositories also need `actions: read` and `contents: read`.

{% raw %}
```yaml
- name: Analyze architecture
  run: |
    rm -f deply.sarif
    deply analyze --report-format=sarif --output=deply.sarif

- name: Upload architecture findings
  if: ${{ !cancelled() && hashFiles('deply.sarif') != '' }}
  uses: github/codeql-action/upload-sarif@v4
  with:
    sarif_file: deply.sarif
    category: deply
```
{% endraw %}

The upload runs even when findings fail the analysis step; the job retains
that failure. Removing the previous file prevents stale uploads after an
incomplete analysis. See [GitHub's upload documentation](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/integrate-with-existing-tools/upload-sarif-file)
for repository availability and permissions. Deply does not emit baseline
fingerprints; the upload action can derive fingerprints from checked-out source.

For more information about:
- Mermaid diagrams, see the [Mermaid Diagrams](mermaid.html) documentation
- Rules and violations, see the [Rules](rules.html) documentation
- Configuration and usage, see the [Configuration Guide](configuration.html) and [Getting Started](getting-started.html) guide
