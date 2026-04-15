import unittest
from pathlib import Path

from deply.models.violation import Violation
from deply.models.violation_types import ViolationType


class TestModels(unittest.TestCase):
    def test_violation_to_dict(self):
        violation = Violation(
            file=Path("service.py"),
            element_name="ServiceClass",
            element_type="class",
            line=12,
            column=4,
            message="Violation message",
            violation_type=ViolationType.CLASS_NAMING,
        )

        self.assertEqual(
            violation.to_dict(),
            {
                "file": "service.py",
                "element_name": "ServiceClass",
                "element_type": "class",
                "line": 12,
                "column": 4,
                "message": "Violation message",
                "violation_type": "class_naming",
            },
        )

    def test_violation_type_to_dict(self):
        self.assertEqual(
            ViolationType.FUNCTION_NAMING.to_dict(),
            {
                "code": "function_naming",
                "display_name": "Function Naming",
            },
        )


if __name__ == "__main__":
    unittest.main()
