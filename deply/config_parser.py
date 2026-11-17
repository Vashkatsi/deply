import importlib
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Optional

import yaml

YAML_CONFIG_FILE = "deply.yaml"
PYPROJECT_FILE = "pyproject.toml"
TOML_UNSUPPORTED_MESSAGE = (
    "Reading pyproject.toml requires Python 3.11 or newer; "
    "create deply.yaml to configure Deply on older Python versions"
)


def discover_config_path(directory: Path) -> Path:
    yaml_path = directory / YAML_CONFIG_FILE
    if yaml_path.exists():
        return yaml_path
    pyproject_path = directory / PYPROJECT_FILE
    if pyproject_path.exists() and _may_configure_deply(pyproject_path):
        return pyproject_path
    return yaml_path


def _may_configure_deply(pyproject_path: Path) -> bool:
    toml_parser = _import_toml_parser()
    if toml_parser is None:
        return True
    try:
        return _read_tool_table(toml_parser, pyproject_path) is not None
    except (OSError, ValueError):
        return True


def _import_toml_parser() -> Optional[ModuleType]:
    try:
        return importlib.import_module("tomllib")
    except ModuleNotFoundError:
        return None


def _read_tool_table(toml_parser: ModuleType, pyproject_path: Path) -> Any:
    with pyproject_path.open("rb") as f:
        document = toml_parser.load(f)
    tool_table = document.get("tool")
    if not isinstance(tool_table, dict):
        return None
    return tool_table.get("deply")


def _require_mapping(config: Any) -> Dict[str, Any]:
    if not isinstance(config, dict):
        raise ValueError("Invalid deply configuration format")
    return config


class ConfigParser:
    def __init__(self, config_path: Path):
        self.config_path = config_path

    def parse(self) -> Dict[str, Any]:
        config = self._load_toml() if self.config_path.suffix == ".toml" else self._load_yaml()

        config.setdefault('paths', [])
        config.setdefault('exclude_files', [])
        config.setdefault('layers', [])
        config.setdefault('ruleset', {})

        if not config['paths']:
            config['paths'] = [str(self.config_path.parent)]

        return config

    def _load_yaml(self) -> Dict[str, Any]:
        with self.config_path.open("r") as f:
            loaded_config = yaml.safe_load(f)

        if loaded_config is None:
            return {}
        if not isinstance(loaded_config, dict):
            raise ValueError("Invalid YAML root type; expected mapping")
        return _require_mapping(loaded_config.get("deply", loaded_config))

    def _load_toml(self) -> Dict[str, Any]:
        toml_parser = _import_toml_parser()
        if toml_parser is None:
            raise ValueError(TOML_UNSUPPORTED_MESSAGE)
        deply_table = _read_tool_table(toml_parser, self.config_path)
        if deply_table is None:
            raise ValueError(f"{self.config_path} has no [tool.deply] table")
        return _require_mapping(deply_table)
