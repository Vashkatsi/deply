from pathlib import Path
from typing import Any, Dict, List

import yaml

PRESETS_DIRECTORY = Path(__file__).parent


class _IndentedDumper(yaml.SafeDumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        return super().increase_indent(flow, False)


def available_presets() -> List[str]:
    return sorted(preset_file.stem for preset_file in PRESETS_DIRECTORY.glob("*.yaml"))


def render_preset(name: str, paths: List[str]) -> Dict[str, Any]:
    with (PRESETS_DIRECTORY / f"{name}.yaml").open("r") as preset_file:
        preset = yaml.safe_load(preset_file)
    return {"deply": {**preset["deply"], "paths": list(paths)}}


def dump_configuration(config: Dict[str, Any]) -> str:
    return str(yaml.dump(config, Dumper=_IndentedDumper, sort_keys=False, default_flow_style=False))
