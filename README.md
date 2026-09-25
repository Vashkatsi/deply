# Deply

Deply is a static code analysis tool for Python that helps you communicate, visualize and enforce architectural decisions in your projects. You can freely define your architectural layers over classes and which rules should apply to them.

For example, you can use Deply to ensure that modules/packages in your project are truly independent of each other to make them easier to reuse.

Deply can be used in a CI pipeline to make sure a pull request does not violate any of the architectural rules you defined. With the optional Mermaid formatter you can visualize your layers, rules and violations.

[![PyPI version](https://img.shields.io/pypi/v/deply)](https://pypi.org/project/deply/)
[![PyPI Stats](https://pypistats.com/api/badges/deply?period=month)](https://pypistats.com/packages/deply)
[![CI](https://github.com/Vashkatsi/deply/actions/workflows/ci.yml/badge.svg)](https://github.com/Vashkatsi/deply/actions/workflows/ci.yml)
[![Python versions](https://img.shields.io/pypi/pyversions/deply)](https://pypi.org/project/deply/)

## Documentation
You can find the documentation in the /doc directory or visit the doc page: https://vashkatsi.github.io/deply

## Getting Started
You can install Deply via pip:

```bash
pip install deply
```

Once you have installed Deply, you will need to create a configuration file, where you define your layers and communication ruleset. This configuration file is written in YAML and, by default, is stored with the name deply.yaml in your project's root directory.

When you have this file, you can analyse your code by running the analyze command:

```bash
deply analyze

# which is equivalent to
deply analyze --config=deply.yaml
```

In order to run Deply you need at least Python 3.8.
Supported and tested versions: Python 3.8 to 3.14.

### Example Configuration

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

    - name: services
      collectors:
        - type: class_name_regex
          class_name_regex: ".*Service$"

  ruleset:
    views:
      disallow_layer_dependencies:
        - models

    services:
      disallow_external_imports:
        - django
        - requests
```

Code elements may belong to multiple layers. Deply checks every unique source
and target layer pair, so layer and collector order does not change dependency
or external-import results.

### Command-Line Usage

```bash
# Basic usage
deply analyze

# With a specific config file
deply analyze --config=custom_config.yaml

# Validate configuration only
deply validate --config=custom_config.yaml

# Generate a Mermaid diagram
deply analyze --mermaid

# Get help
deply --help
```

`deply analyze` validates the configuration before scanning project files and
exits with status `1` when the configuration is invalid or analysis is
incomplete because files cannot be read or parsed, no Python files are found,
or no code elements map to configured layers.

Every completed analysis report includes completeness metrics for discovered,
excluded, parsed, mapped, and unmapped files; mapped and overlapping elements;
and detected dependencies. Incomplete analysis prints the available metrics to
standard error before exiting.

## Agent Skill

Deply v1.1.3 includes a portable Agent Skill at `skills/deply-config/` for Codex, Claude Code, and other Agent Skills-compatible assistants. It helps an assistant inspect a Python project, generate `deply.yaml` using `light`, `medium`, or `strict` guidance, validate it with `deply validate`, run analysis, and add Makefile/CI/docs integration. These profiles belong to the Agent Skill; they are not built-in Deply CLI presets.

Use it with:

```text
Use $deply-config to create and validate a Deply architecture config for this Python project.
```

See [Agent Skill](https://vashkatsi.github.io/deply/doc/skills.html) for installation instructions.

## Features

- **Layer-Based Analysis**: Define project layers and restrict their dependencies to enforce modularity.
- **Dynamic Layer Configuration**: Easily configure collectors for each layer using file patterns, class inheritance, and logical conditions.
- **Cross-Layer Dependency Rules**: Specify rules to disallow certain layers from accessing others. Internal dependency inference currently matches unqualified names globally, so imported aliases may be missed and equal names may overmatch.
- **External Import Restrictions**: Prevent selected layers from importing framework, persistence, or SDK package roots through absolute imports. Relative imports are ignored.
- **Extensible and Configurable**: Customize layers with built-in or custom collectors and supported rules.
- **Mermaid Diagrams**: Visualize your architecture and dependencies with Mermaid diagrams.
- **Error Suppression**: Suppress specific rule violations with inline comments.
- **Config Validation**: Validate `deply.yaml` explicitly or automatically before analysis.
- **SARIF Reports**: Export findings for GitHub Code Scanning with `deply analyze --report-format=sarif --output=deply.sarif`. See the [CLI guide](doc/cli.md#sarif-report) for upload instructions and limitations.
- **Architecture Recipes**: Copy and adapt documented configurations for 21 architecture and application patterns; they are not built-in presets.

## Error Suppression

Deply provides options to suppress rule violations using comments in your code:

```python
# Line-level suppression
user.get()  # deply:ignore:DISALLOW_LAYER_DEPENDENCIES
import requests  # deply:ignore:DISALLOWED_EXTERNAL_IMPORT

# File-level suppression (at the top of the file)
# deply:ignore-file:ENFORCE_INHERITANCE
```

## How to Contribute
Feel free to contribute to this project by opening an issue or submitting a pull request! Together, we can make Deply a powerful tool for the Python community.

## Running Tests

Use the following commands for local quality checks:

```bash
make check
make test
make mutation
make lint
make typing
make security
make pre-commit
```

Or run `unittest` directly:

```bash
python -m unittest discover tests
```

## Roadmap

See the [verified technical roadmap](doc/technical-roadmap.md) for current priorities,
evidence, and implementation conditions.

## Further Documentation
- [Core Concepts](https://vashkatsi.github.io/deply/doc/features.html) - Explains layers, rules and violations in more details.
- [Configuration](https://vashkatsi.github.io/deply/doc/configuration.html) - Reference for all available settings in a depfile
- [Collectors](https://vashkatsi.github.io/deply/doc/collectors.html) - Reference for which collectors are available in Deply to define your layers.
- [Rules](https://vashkatsi.github.io/deply/doc/rules.html) - Lists the different rule types supported by Deply
- [Mermaid Diagrams](https://vashkatsi.github.io/deply/doc/mermaid.html) - Overview of the diagram generation capabilities
- [Command Line Interface](https://vashkatsi.github.io/deply/doc/cli.html) - Advice for using the CLI
- [Agent Skill](https://vashkatsi.github.io/deply/doc/skills.html) - Install and use the Deply Config Agent Skill
- [Architecture Styles](https://vashkatsi.github.io/deply/doc/architectures.html) - Compare 21 architecture and application pattern recipes
- [FastAPI](https://vashkatsi.github.io/deply/doc/fastapi.html) - Configure layered FastAPI boundaries
- [Full Stack FastAPI Template](https://vashkatsi.github.io/deply/doc/full-stack-fastapi-template.html) - Verified baseline for FastAPI's official template
- [Django](https://vashkatsi.github.io/deply/doc/django.html) - Configure Django model, view, and domain boundaries
- [Flask](https://vashkatsi.github.io/deply/doc/flask.html) - Configure Flask route, blueprint, and persistence boundaries

## Author

[Archil Abuladze](https://www.linkedin.com/in/vashkatsi/)

## License

See the [LICENSE](LICENSE) file for details.
