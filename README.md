# Deply - <em>keep your python architecture clean</em>

![Static Badge](https://img.shields.io/badge/stable-v0.8.0-319cd2)
![Static Badge](https://img.shields.io/badge/downloads->2_k_month-2282c2)
![Static Badge](https://img.shields.io/badge/test-passing-98c525)
![Static Badge](https://img.shields.io/badge/coverage-85%25-98c525)
![Static Badge](https://img.shields.io/badge/python-3.8_|_3.9_|3.10_|_3.11_|_3.12-98c525)

---

**Deply** is a standalone Python tool for enforcing architectural patterns and dependencies in large Python projects. By
analyzing code structure and dependencies, this tool ensures that architectural rules are followed, promoting cleaner,
more maintainable, and modular codebases.

## Features

- **Layer-Based Analysis**: Define project layers and restrict their dependencies to enforce modularity.
- **Dynamic Layer Configuration**: Easily configure collectors for each layer using file patterns, class inheritance,
  and logical conditions.
- **Cross-Layer Dependency Rules**: Specify rules to disallow certain layers from accessing others.
- **Extensible and Configurable**: Customize layers and rules for any Python project setup.

## Installation

To install **Deply**, use `pip`:

```bash
pip install deply
```

## Configuration

Before running the tool, create a configuration file (`deply.yaml` or similar) that specifies the rules and target files
to enforce.

### Example Configuration (`deply.yaml`)

```yaml
deply:
  paths:
    - /path/to/your/project

  exclude_files:
    - ".*\\.venv/.*"

  layers:
    - name: models
      collectors:
        - type: bool
          any_of:
            - type: class_inherits
              base_class: "django.db.models.Model"
            - type: class_inherits
              base_class: "django.contrib.auth.models.AbstractUser"

    - name: views
      collectors:
        - type: file_regex
          regex: ".*/views_api.py"

    - name: app1
      collectors:
        - type: directory
          directories:
            - "app1"

    - name: services
      collectors:
        - type: bool
          must:
            - type: class_name_regex
              class_name_regex: ".*Service$"
          must_not:
            - type: file_regex
              regex: ".*/excluded_folder_name/.*"
            - type: decorator_usage
              decorator_name: "deprecated_service"

    - name: auth_protected
      collectors:
        - type: decorator_usage
          decorator_name: "login_required"

  ruleset:
    views:
      disallow_layer_dependencies:
        - models

    tasks:
      enforce_function_decorator_usage:
        - type: function_decorator_name_regex
          decorator_name_regex: "app.task"

    models:
      enforce_inheritance:
        - type: bool
          any_of:
            - type: class_inherits
              base_class: "django.db.models.Model"
            - type: class_inherits
              base_class: "django.contrib.auth.models.AbstractUser"
```

### Commands and Usage

Deply uses a command-line interface to analyze your project.

#### Basic Usage

Run Deply by executing the following command in your terminal:

```bash
deply analyze
```

By default, Deply looks for a configuration file named `deply.yaml` in the current directory.

#### Command-Line Arguments

- `deply analyze`: Analyzes the project dependencies based on the configuration.
    - `--config`: Path to the configuration YAML file. Default is `deply.yaml`.
    - `--report-format`: Format of the output report. Choices are `text`, `json`, `html`. Default is `text`.
    - `--output`: Output file for the report. If not specified, the report is printed to the console.
    - `--mermaid`: Generates a Mermaid diagram of your layer dependencies, printing it to the console at the end of the analysis. Any edges that represent a violation are shown in red.
    - `--max-violations`: Maximum number of allowed violations before failing the analysis. Default is 0 (no violations allowed).
    - `--parallel`: Enable parallel processing of code elements. If no number is provided, all available CPU cores will be used.
- `-h`, `--help`: Displays help information about Deply and its commands.

#### Examples

- Analyze the project using the default configuration file:

  ```bash
  deply analyze
  ```

- Analyze the project with a specific configuration file:

  ```bash
  deply analyze --config=custom_config.yaml
  ```

- Display help information:

  ```bash
  deply --help
  ```

### Default Behavior

- **Configuration File**: If no `--config` argument is provided, Deply looks for `deply.yaml` in the current directory.
- **Paths**: If the `paths` option is not specified in the configuration file, Deply uses the directory where the
  configuration file resides.

## Sample Output

If violations are found, the tool will output a summary of architectural violations grouped by layer, along with details
of each violation, such as the file, line number, and violation message.

```plaintext
/path/to/your_project/your_project/app1/views_api.py:74 - Layer 'views' is not allowed to depend on layer 'models'
```

### Collectors

Collectors define how code elements are collected into layers. **Deply** supports several types of collectors:

#### **BoolCollector**

The `BoolCollector` allows combining other collectors with logical operations such as `must`, `any_of`, and `must_not`.
This enables you to define complex conditions for collecting code elements without deep nesting.

- **Configuration Options**:
    - `type`: `"bool"`
    - `must` (optional): A list of collectors where all must match.
    - `any_of` (optional): A list of collectors where at least one must match.
    - `must_not` (optional): A list of collectors where none must match.

**Example using `must`, `any_of`, and `must_not`**:

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

**Explanation**:

- Collects classes whose names end with `Service`.
- Additionally, the class must either use the `@transactional` decorator or the `@cacheable` decorator.
- Excludes any classes from files with names matching `.*test.*`.

#### **ClassInheritsCollector**

Collects classes that inherit from a specified base class.

- **Configuration Options**:
    - `type`: `"class_inherits"`
    - `base_class`: The fully qualified name of the base class to match.
    - `exclude_files_regex` (optional): Regular expression to exclude certain files.

**Example**:

```yaml
- type: class_inherits
  base_class: "django.db.models.Model"
```

#### **ClassNameRegexCollector**

Collects classes whose names match a specified regular expression.

- **Configuration Options**:
    - `type`: `"class_name_regex"`
    - `class_name_regex`: Regular expression to match class names.
    - `exclude_files_regex` (optional): Regular expression to exclude certain files.

**Example**:

```yaml
- type: class_name_regex
  class_name_regex: ".*Service$"
  exclude_files_regex: ".*excluded_folder_name.*"
```

### FunctionNameRegexCollector

Collects functions whose names match a specified regular expression.

**Configuration Options**:

- `type`: `"function_name_regex"`
- `function_name_regex`: Regular expression to match function names.
- `exclude_files_regex` (optional): Regular expression to exclude certain files.

**Example**:

```yaml
- type: function_name_regex
  function_name_regex: "^helper_.*"
```

#### **DecoratorUsageCollector**

Collects functions or classes that use a specific decorator.

- **Configuration Options**:
    - `type`: `"decorator_usage"`
    - `decorator_name` (optional): The name of the decorator to match exactly.
    - `decorator_regex` (optional): Regular expression to match decorator names.
    - `exclude_files_regex` (optional): Regular expression to exclude certain files.

**Example using `decorator_name`**:

```yaml
- type: decorator_usage
  decorator_name: "login_required"
```

**Example using `decorator_regex`**:

```yaml
- type: decorator_usage
  decorator_regex: "^auth_.*"
```

#### **DirectoryCollector**

Collects code elements from specified directories.

- **Configuration Options**:
    - `type`: `"directory"`
    - `directories`: List of directories (relative to the project root) to include.
    - `recursive` (optional): Whether to search directories recursively (`true` by default).
    - `element_type` (optional): Type of code elements to collect (`"class"`, `"function"`, `"variable"`).
    - `exclude_files_regex` (optional): Regular expression to exclude certain files.

**Example**:

```yaml
- type: directory
  directories:
    - "app1"
    - "utils"
  recursive: true
  element_type: "function"
```

#### **FileRegexCollector**

Collects code elements from files matching a specified regular expression.

- **Configuration Options**:
    - `type`: `"file_regex"`
    - `regex`: Regular expression to match file paths.
    - `element_type` (optional): Type of code elements to collect (`"class"`, `"function"`, `"variable"`).
    - `exclude_files_regex` (optional): Regular expression to exclude certain files.

**Example**:

```yaml
- type: file_regex
  regex: ".*/views_api.py$"
  element_type: "class"
```

#### **CustomCollector**

Extend Deply's capabilities with domain-specific collection logic:

- **Configuration Options**:
    - `type`: `"file_regex"`
    - `regex`: Regular expression to match file paths.
    - `element_type` (optional): Type of code elements to collect (`"class"`, `"function"`, `"variable"`).
    - `exclude_files_regex` (optional): Regular expression to exclude certain files.

**Example**:

```yaml
- type: custom
  class: "security_plugins.RiskyFunctionsCollector"
  params:
    risky_patterns: ["^handle_password", "_auth$"]
```

##### Implementation Example:
```python
import re
from pathlib import Path
import ast
from typing import Set
from deply.collectors import BaseCollector
from deply.models.code_element import CodeElement

class RiskyFunctionsCollector(BaseCollector):
    def __init__(self, config: dict):
        self.patterns = [re.compile(p) for p in config["params"]["risky_patterns"]]
        self.excluded_files = config["exclude_files"]

    def match_in_file(self, file_ast: ast.AST, file_path: Path) -> Set[CodeElement]:
        elements = set()
        if any(p.search(str(file_path)) for p in self.excluded_files):
            return elements

        for node in ast.walk(file_ast):
            if isinstance(node, ast.FunctionDef):
                if any(p.search(node.name) for p in self.patterns):
                    elements.add(CodeElement(
                        file=file_path,
                        name=node.name,
                        element_type="function",
                        line=node.lineno
                    ))
        return elements
```

**Requirements**:
1. Inherit from `BaseCollector`
2. Implement `__init__` (receives config dict) and `match_in_file` methods
3. Access configuration through:
    - `config["params"]`: Your custom parameters
    - `config["paths"]`: Project paths analyzed
    - `config["exclude_files"]`: Exclusion patterns


### Rules

Rules define the architectural constraints and standards that your layers must adhere to. By default, Deply supports a
set of rules that you can apply to layers to ensure clean, modular, and maintainable architectures.

Rules are defined under the `ruleset` section in `deply.yaml`, mapping layer names to rules that apply to those layers.
Each rule can restrict dependencies, enforce naming conventions, decorator usage, inheritance patterns, and more.

## Disallow Layer Dependencies

Prevent certain layers from depending on others:

```yaml
views:
  disallow_layer_dependencies:
    - models
```

This ensures the views layer cannot depend on the models layer. If views references models directly, a violation will be
reported.

## Class Naming Rules

Use rules to enforce class naming patterns:

```yaml
models:
  enforce_class_naming:
    - type: class_name_regex
      class_name_regex: ".*View$"
```

This ensures that classes in models must end with View. Violations occur if a class name doesn't match.

## Function Naming Rules

Enforce function naming conventions:

```yaml
views:
  enforce_function_naming:
    - type: function_name_regex
      function_name_regex: ".*view$"
```

All functions in views must end with view. Non-matching functions trigger violations.

## Class and Function Decorator Usage Rules

Ensure that classes or functions have specific decorators:

```yaml
auth_protected:
  enforce_class_decorator_usage:
    - type: decorator_name_regex
      decorator_name_regex: "@dataclass"
```

This ensures that classes in auth_protected have a decorator matching @dataclass.

For functions, a similar rule can be applied:

```yaml
tasks:
  enforce_function_decorator_usage:
    - type: function_decorator_name_regex
      decorator_name_regex: "app.task"
```

Functions in tasks must have at least one decorator whose name matches "app.task".

## Inheritance Rules

Require classes to inherit from certain base classes:

```yaml
models:
  enforce_inheritance:
    - type: class_inherits
      base_class: "django.db.models.Model"
```

All classes in models must inherit from django.db.models.Model. If a class does not, a violation is reported.

## Boolean Logic (BoolRule)

Use a bool rule type to combine multiple conditions with logical operations `must`, `any_of`, and `must_not`:

```yaml
models:
  enforce_inheritance:
    - type: bool
      any_of:
        - type: class_inherits
          base_class: "django.db.models.Model"
        - type: class_inherits
          base_class: "django.contrib.auth.models.AbstractUser"
```

In this example, classes in models must inherit from either django.db.models.Model or
django.contrib.auth.models.AbstractUser. If none of these conditions are met, a violation occurs.

- `must`: All specified sub-rules must pass.
- `any_of`: At least one sub-rule must pass.
- `must_not`: No sub-rule should pass (they should fail to avoid violation).

This logical flexibility allows complex rule scenarios without deep nesting or duplication.

By mixing and matching these rules, you can enforce your architectural guidelines effectively, ensuring that every layer
and component adheres to the desired standards. As your project evolves, you can refine or add rules to maintain
architectural integrity and prevent unwanted dependencies and naming patterns.

## Error Suppression

Deply provides flexible options to suppress architectural rule violations, giving you granular control over which checks to ignore. Use descriptive rule names (like `DISALLOW_LAYER_DEPENDENCIES` or `ENFORCE_INHERITANCE`) that align with your `deply.yaml` configuration keys.

### 1. Line-Level Suppression

Ignore violations for **specific rules** or **all rules** on a single line.

#### Examples:

- **Ignore a single rule:**
  ```python
  user.get()  # deply:ignore:DISALLOW_LAYER_DEPENDENCIES
  ```

- **Ignore multiple rules (comma-separated):**
  ```python
  user.get()  # deply:ignore:DISALLOW_LAYER_DEPENDENCIES,ENFORCE_INHERITANCE
  ```

- **Ignore all rules on the line:**
  ```python
  user.get()  # deply:ignore
  ```

### 2. File-Level Suppression

Suppress rules **globally for an entire file**. Place these directives at the top of your file.

#### Examples:

- **Ignore a specific rule for the entire file:**
  ```python
  # deply:ignore-file:ENFORCE_INHERITANCE
  ```

- **Ignore all Deply rules for the entire file:**
  ```python
  # deply:ignore-file
  ```

## Running Tests

To test the tool, use `unittest`:

```bash
 python -m unittest discover tests
```


Here's a polished roadmap for your README:

---

# Deply Roadmap 🚀

A plan to evolve Deply into a must-have architectural guardian for Python projects.  
*Contributions and suggestions are welcome!*

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

---
    
Feel free to contribute to this roadmap or suggest features by opening an issue or submitting a pull request! Together,
we can make Deply a powerful tool for the Python community. 😊

---

## License

See the [LICENSE](LICENSE) file for details.