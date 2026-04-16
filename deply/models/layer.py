from dataclasses import dataclass
from typing import Set

from .dependency import Dependency
from ..models.code_element import CodeElement


@dataclass()
class Layer:
    name: str
    code_elements: Set[CodeElement]
    dependencies: Set[Dependency]
