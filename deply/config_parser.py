from pathlib import Path
from typing import Any, Dict

import yaml


class ConfigParser:
    def __init__(self, config_path: Path):
        self.config_path = config_path

    def parse(self) -> Dict[str, Any]:
        with self.config_path.open("r") as f:
            loaded_config = yaml.safe_load(f)

        if loaded_config is None:
            config: Dict[str, Any] = {}
        elif isinstance(loaded_config, dict):
            config = loaded_config.get("deply", loaded_config)
            if not isinstance(config, dict):
                raise ValueError("Invalid deply configuration format")
        else:
            raise ValueError("Invalid YAML root type; expected mapping")

        config.setdefault('paths', [])
        config.setdefault('exclude_files', [])
        config.setdefault('layers', [])
        config.setdefault('ruleset', {})

        if not config['paths']:
            config['paths'] = [str(self.config_path.parent)]

        return config
