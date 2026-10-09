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
standard error. JSON also generates a report on invalid configuration or
incomplete analysis; other formats do not generate a report in these cases.

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

JSON schema v1 preserves the existing `total_violations`, `by_type`,
`violations`, and optional `metrics` fields and adds machine-readable context:

```bash
deply analyze --report-format=json --output=deply-report.json
```

```json
{
  "schema_version": 1,
  "status": "complete",
  "errors": [],
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
      "violation_type": "disallowed_dependency",
      "rule_id": "views:disallow_layer_dependencies:bf4644a7ec41e8bcaf3dbdc1d0e47b5ee5bb0183c5c44fa4edcdc02ed31cd252",
      "source": {
        "file": "your_project/app1/views_api.py",
        "name": "list_users",
        "type": "function"
      },
      "target": {
        "file": "your_project/app2/models.py",
        "name": "User",
        "type": "class"
      },
      "source_layer": "views",
      "target_layer": "models",
      "dependency_type": "function_call",
      "fingerprint": "122cf66fef3a27215b032b6181347ddb9643c8b43c41d29f9a161531b396e117"
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

#### Analysis status and errors

- `schema_version`: integer `1`. Consumers should check it and tolerate unknown
  additive fields.
- `status`: `complete`, `incomplete`, or `invalid_configuration`. `complete`
  means the supported analysis passes finished; it does not mean no violations
  or complete understanding of dynamic Python behavior.
- `errors`: an array of `{ "code": string, "message": string }`. Codes are
  `incomplete_analysis` or `invalid_configuration`; messages are diagnostics,
  not identifiers to parse. A complete report has an empty array.
- `metrics`: existing counters, including partial counters for incomplete
  analysis. Invalid configuration has no metrics because scanning never started.

All three statuses produce JSON on stdout or overwrite `--output`. Errors still
print to stderr. Invalid configuration and incomplete analysis exit `1`, even
with a permissive `--max-violations`. Complete analysis retains the existing
threshold exit behavior. Partial violations in an incomplete report are not
an exhaustive result. With JSON and `--mermaid`, the diagram goes to stderr,
keeping stdout parseable. `deply validate` retains its text-only behavior.

Deduplication now preserves different source/target relationships and configured
rules even when their location and message match. This applies to every report
format: counts may increase for previously collapsed violations. Re-evaluate
existing `--max-violations` thresholds against the corrected totals.

#### Violation identity

- Legacy `file`, `element_name`, `element_type`, `line`, `column`, `message`,
  and `violation_type` fields retain their meanings. Columns are zero-based
  UTF-8 byte offsets from Python AST, not character offsets.
- `source` and internal `target` contain `file`, `name`, and `type`. Names
  preserve collected qualified names, including enclosing scopes where available.
  Paths use forward slashes and are relative to the configuration directory;
  files outside it use `../` segments. On Windows, files on a different drive
  use absolute `file:` URIs, whose fingerprints depend on that drive/path.
  Run with a configuration in the same relative location across checkouts to
  retain identity.
- `source_layer` and `target_layer` identify the particular checked membership
  pair. Overlapping memberships remain separate violations.
- `dependency_type` identifies an internal dependency, such as `function_call`.
  Element checks have a null `target`, `target_layer`, and `dependency_type`.
- External import checks identify the source as the file's `<module>` with type
  `module`; the target is `{ "module": "requests.sessions", "type":
  "external_module" }`. Their `target_layer` and `dependency_type` are null.
  The legacy element fields still identify the collected representative element.
- `rule_id` is `layer:configuration_key:sha256`, where the digest covers compact,
  sorted-key, ASCII-escaped JSON of the effective configured rule (type, supported
  parameters, and defaults).
  Ignored metadata does not affect identity. Dependency target lists and external
  import roots are normalized as sorted sets; other rule configurations retain
  list order. Identical configured constraints share an ID. Changed constraints
  change the ID. Bool rules identify the full configured expression, including
  when a subrule produces the diagnostic.
- `fingerprint` is the SHA-256 of compact, sorted-key, ASCII-escaped JSON containing `rule_id`,
  `source`, `target`, `source_layer`, `target_layer`, and `dependency_type`.
  JSON uses `separators=(",", ":")` and UTF-8 encoding for both digests.
  It excludes locations and messages; same-drive paths exclude the absolute
  checkout root. Different call sites for the same relationship share a fingerprint but keep separate locations.
  Renaming or moving a symbol/file, changing a rule, or changing a membership pair
  changes the fingerprint. It is not an occurrence ID or proof of semantic equivalence.

Direct `JsonReport`/`ReportGenerator` callers default the identity root to the
working directory; pass `root=Path(...)` for a different root. Manually constructed
violations without configured context use `violation_type` as their `rule_id`
and null layers; use the analysis CLI for full configured identities.

Fingerprints prepare exact baseline support; this release does not add baseline
suppression. Existing wildcard-import, dynamic-type, and control-flow limitations
remain. A complete report is not a complete call graph.

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
