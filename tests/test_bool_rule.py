import unittest
from pathlib import Path

from deply.models.code_element import CodeElement
from deply.rules.bool_rule import BoolRule


class TestBoolRule(unittest.TestCase):
    def test_any_of_passes_when_later_rule_matches(self):
        element = CodeElement(
            file=Path("service.py"),
            name="allowed_function",
            element_type="function",
            line=3,
            column=0,
        )
        rule = BoolRule(
            "service",
            {
                "any_of": [
                    {
                        "type": "function_name_regex",
                        "function_name_regex": "^missing_.*$",
                    },
                    {
                        "type": "function_name_regex",
                        "function_name_regex": "^allowed_.*$",
                    },
                ],
            },
        )

        self.assertIsNone(rule.check_element("service", element))


if __name__ == "__main__":
    unittest.main()
