from enum import Enum


class ViolationType(Enum):
    DISALLOWED_DEPENDENCY = ("disallowed_dependency", "Disallowed Dependency")
    DISALLOWED_EXTERNAL_IMPORT = ("disallowed_external_import", "Disallowed External Import")
    FUNCTION_DECORATOR_USAGE = ("function_decorator_usage", "Function Decorator Usage")
    CLASS_DECORATOR_USAGE = ("class_decorator_usage", "Class Decorator Usage")
    CLASS_NAMING = ("class_naming", "Class Naming")
    FUNCTION_NAMING = ("function_naming", "Function Naming")
    INHERITANCE = ("inheritance", "Inheritance")
    BOOL_RULE = ("bool_rule", "Bool Rule")

    def __init__(self, code: str, display_name: str):
        self._code = code
        self._display_name = display_name

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "display_name": self.display_name
        }

    @property
    def code(self) -> str:
        return self._code

    @property
    def display_name(self) -> str:
        return self._display_name
