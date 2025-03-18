import ast
from abc import ABC, abstractmethod
from pathlib import Path

from ..models.code_element import CodeElement


class BaseCollector(ABC):
    @abstractmethod
    def __init__(self, config: dict):
        pass

    @abstractmethod
    def match_in_file(self, file_ast: ast.AST, file_path: Path) -> set[CodeElement]:
        pass
