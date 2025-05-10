# Deply

Deply is a static code analysis tool for Python that helps you communicate, visualize and enforce architectural decisions in your projects. You can freely define your architectural layers over classes and which rules should apply to them.

For example, you can use Deply to ensure that modules/packages in your project are truly independent of each other to make them easier to reuse.

Deply can be used in a CI pipeline to make sure a pull request does not violate any of the architectural rules you defined. With the optional Mermaid formatter you can visualize your layers, rules and violations.

![Static Badge](https://img.shields.io/badge/stable-v0.8.0-319cd2)
![Static Badge](https://img.shields.io/badge/downloads->2_k_month-2282c2)
![Static Badge](https://img.shields.io/badge/test-passing-98c525)
![Static Badge](https://img.shields.io/badge/coverage-85%25-98c525)
![Static Badge](https://img.shields.io/badge/python-3.8_|_3.9_|3.10_|_3.11_|_3.12-98c525)

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
deply analyze --config-file=deply.yaml
```

In order to run Deply you need at least Python 3.8.

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
```

### Command-Line Usage

```bash
# Basic usage
deply analyze

# With a specific config file
deply analyze --config=custom_config.yaml

# Generate a Mermaid diagram
deply analyze --mermaid

# Get help
deply --help
```

## Features

- **Layer-Based Analysis**: Define project layers and restrict their dependencies to enforce modularity.
- **Dynamic Layer Configuration**: Easily configure collectors for each layer using file patterns, class inheritance, and logical conditions.
- **Cross-Layer Dependency Rules**: Specify rules to disallow certain layers from accessing others.
- **Extensible and Configurable**: Customize layers and rules for any Python project setup.
- **Mermaid Diagrams**: Visualize your architecture and dependencies with Mermaid diagrams.
- **Error Suppression**: Suppress specific rule violations with inline comments.

## Error Suppression

Deply provides options to suppress rule violations using comments in your code:

```python
# Line-level suppression
user.get()  # deply:ignore:DISALLOW_LAYER_DEPENDENCIES

# File-level suppression (at the top of the file)
# deply:ignore-file:ENFORCE_INHERITANCE
```

## How to Contribute
Feel free to contribute to this project by opening an issue or submitting a pull request! Together, we can make Deply a powerful tool for the Python community.

## Running Tests

To test the tool, use `unittest`:

```bash
python -m unittest discover tests
```

## Roadmap 🚀

A plan to evolve Deply into a must-have architectural guardian for Python projects:

  🔲 Skip violations `skip_violations`  
  🔲 Interactive config setup (`deply init` wizard)  
  🔲 GitHub Actions/GitLab CI templates  
  ✅ `# deply:ignore` suppression comments  
  🔲 Config validation command (`deply validate`)  
  ✅ Parallel file analysis  
  ✅ Custom collectors system  
  🔲 Dependency graph caching  
  🔲 Custom rules system  
  🔲 FastAPI/Django/Flask presets  
  🔲 Third-party import restrictions (`disallow_external_imports`)  

## Further Documentation
- [Core Concepts](https://vashkatsi.github.io/deply/doc/features.md) - Explains layers, rules and violations in more details.
- [Configuration](https://vashkatsi.github.io/deply/doc/configuration.md) - Reference for all available settings in a depfile
- [Collectors](https://vashkatsi.github.io/deply/doc/collectors.md) - Reference for which collectors are available in Deply to define your layers.
- [Rules](https://vashkatsi.github.io/deply/doc/rules.md) - Lists the different rule types supported by Deply
- [Mermaid Diagrams](https://vashkatsi.github.io/deply/doc/mermaid.md) - Overview of the diagram generation capabilities
- [Command Line Interface](https://vashkatsi.github.io/deply/doc/cli.md) - Advice for using the CLI

## License

See the [LICENSE](LICENSE) file for details.
