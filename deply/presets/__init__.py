from pathlib import Path
from typing import List

PRESETS_DIRECTORY = Path(__file__).parent


def available_presets() -> List[str]:
    return sorted(preset_file.stem for preset_file in PRESETS_DIRECTORY.glob("*.yaml"))


def preset_text(name: str) -> str:
    return (PRESETS_DIRECTORY / f"{name}.yaml").read_text()
