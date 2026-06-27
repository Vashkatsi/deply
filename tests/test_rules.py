import unittest
import tempfile
import shutil
from pathlib import Path
import sys
import yaml
from contextlib import contextmanager
from io import StringIO

from deply.main import main


@contextmanager
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err


class TestRules(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        self.test_project_dir = Path(self.test_dir) / 'test_project'
        self.test_project_dir.mkdir()

    def tearDown(self):
        # Remove temporary directory
        shutil.rmtree(self.test_dir)

    def run_deply(self, config_data):
        # Write config
        config_yaml = Path(self.test_dir) / 'deply.yaml'
        config_for_run = {
            **config_data,
            "deply": {
                **config_data["deply"],
                "paths": [str(self.test_project_dir)],
            },
        }
        with config_yaml.open('w') as f:
            yaml.dump(config_for_run, f)

        with captured_output() as (out, err):
            exit_code = 0
            try:
                sys.argv = ['main.py', 'analyze', '--config', str(config_yaml)]
                main()
            except SystemExit as e:
                exit_code = e.code
        output = out.getvalue()

        return exit_code, output

    def test_bool_rule_any_of_pass(self):
        # Create necessary files
        models_dir = self.test_project_dir / 'models'
        models_dir.mkdir()
        (models_dir / 'base_model.py').write_text('class BaseModel:\n    pass\n')
        (models_dir / 'my_model.py').write_text(
            'from .base_model import BaseModel\nclass MyModel(BaseModel):\n    pass\n')

        config_data = {
            'deply': {
                'paths': ['./test_project'],
                'layers': [
                    {
                        'name': 'models',
                        # Use file_regex to only pick up my_model.py, excluding base_model.py
                        'collectors': [
                            {
                                'type': 'file_regex',
                                'regex': '.*/my_model.py$'
                            }
                        ]
                    }
                ],
                'ruleset': {
                    'models': {
                        'enforce_inheritance': [
                            {
                                'type': 'bool',
                                'any_of': [
                                    {
                                        'type': 'class_inherits',
                                        'base_class': 'BaseModel'
                                    },
                                    {
                                        'type': 'class_inherits',
                                        'base_class': 'AnotherModel'
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }

        exit_code, output = self.run_deply(config_data)
        # Now only MyModel is considered. It inherits from BaseModel, so any_of should pass.
        self.assertEqual(exit_code, 0, f"Expected no violations, but got exit code {exit_code}\nOutput:\n{output}")

    def test_bool_rule_any_of_fail(self):
        # This test checks a bool rule with any_of that should fail if none of the conditions are met.
        # We define classes that do not inherit from any required base class, expecting a violation.
        models_dir = self.test_project_dir / 'models'
        models_dir.mkdir()
        (models_dir / 'base_model.py').write_text('class BaseModel:\n    pass\n')
        (models_dir / 'my_model.py').write_text('class MyModel:\n    pass\n')

        config_data = {
            'deply': {
                'paths': ['./test_project'],
                'layers': [
                    {
                        'name': 'models',
                        'collectors': [
                            {
                                'type': 'directory',
                                'directories': ['models']
                            }
                        ]
                    }
                ],
                'ruleset': {
                    'models': {
                        'enforce_inheritance': [
                            {
                                'type': 'bool',
                                'any_of': [
                                    {
                                        'type': 'class_inherits',
                                        'base_class': 'BaseModel'
                                    },
                                    {
                                        'type': 'class_inherits',
                                        'base_class': 'AnotherModel'
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }

        exit_code, output = self.run_deply(config_data)
        # MyModel does not inherit from BaseModel or AnotherModel, so any_of fails
        self.assertEqual(exit_code, 1, f"Expected violations, but got exit code {exit_code}\nOutput:\n{output}")
        self.assertIn("Class 'MyModel' must inherit from", output)

    def test_bool_rule_must_pass(self):
        # must means all conditions must pass (no violations on sub-rules).
        # Here we will check if class_name_regex passes.
        models_dir = self.test_project_dir / 'models'
        models_dir.mkdir()
        (models_dir / 'model_a.py').write_text('class GoodModel:\n    pass\n')

        config_data = {
            'deply': {
                'paths': ['./test_project'],
                'layers': [
                    {
                        'name': 'models',
                        'collectors': [
                            {
                                'type': 'directory',
                                'directories': ['models']
                            }
                        ]
                    }
                ],
                'ruleset': {
                    'models': {
                        'enforce_class_naming': [
                            {
                                'type': 'bool',
                                'must': [
                                    {
                                        'type': 'class_name_regex',
                                        'class_name_regex': '^Good.*'
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }

        exit_code, output = self.run_deply(config_data)
        # GoodModel matches ^Good.* regex, so must passes with no violations
        self.assertEqual(exit_code, 0, f"Expected no violations, but got exit code {exit_code}\nOutput:\n{output}")

    def test_bool_rule_must_fail(self):
        # must means all conditions must pass. If one fails, we should get a violation.
        # Let's break the rule by having a class that doesn't match the regex.
        models_dir = self.test_project_dir / 'models'
        models_dir.mkdir()
        (models_dir / 'model_a.py').write_text('class BadModel:\n    pass\n')

        config_data = {
            'deply': {
                'paths': ['./test_project'],
                'layers': [
                    {
                        'name': 'models',
                        'collectors': [
                            {
                                'type': 'directory',
                                'directories': ['models']
                            }
                        ]
                    }
                ],
                'ruleset': {
                    'models': {
                        'enforce_class_naming': [
                            {
                                'type': 'bool',
                                'must': [
                                    {
                                        'type': 'class_name_regex',
                                        'class_name_regex': '^Good.*'
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }

        exit_code, output = self.run_deply(config_data)
        self.assertEqual(exit_code, 1, f"Expected violations, but got exit code {exit_code}\nOutput:\n{output}")
        self.assertIn("Class 'BadModel' does not match naming pattern", output)

    def test_bool_rule_must_not_pass(self):
        # must_not means all must fail (all must produce violations).
        # We'll introduce a scenario where a function should not match a regex.
        # If it matches (no violation), then must_not fails.
        models_dir = self.test_project_dir / 'models'
        models_dir.mkdir()
        (models_dir / 'model_a.py').write_text('def helper_function():\n    pass\n')

        # We want must_not = function_name_regex '^helper_.*' meaning this rule must produce violation.
        # But since 'helper_function' matches, the function_name_regex rule by itself wouldn't produce violation.
        # Actually, the function_name_regex rule produces no violation if it matches. To force a violation,
        # we need to think carefully: If a sub-rule does not produce a violation, that means it "passed".
        # must_not wants all to fail. Let's pick a rule that always fails if matched:
        # Actually, we might pick a class_inherits rule that fails since no class inherits from something.
        # Let's use a class_inherits with a base_class that doesn't exist:
        # This will produce violation on a function element because it doesn't apply. 
        # Actually, class_inherits probably returns no violation if doesn't match?
        # Let's do a simpler approach: We'll pick a sub-rule that always fails. 
        # Suppose function_name_regex means that if a function doesn't match the regex, it's a violation:
        # Actually function_name_regex rule expects the function name to match to avoid violation. If it doesn't match, violation.
        # We need a scenario that ensures a violation. Let's pick a naming rule that does not match:
        # We'll have must_not: a rule that always fails (like class_name_regex that doesn't match on a function?). 
        # Wait, we must remember the BoolRule logic: For must_not rules, we actually want violations from sub-rules. 
        # If sub-rule is function_name_regex '^helper_.*' and we do have helper_function, that sub-rule doesn't produce violation, it passes. We need it to fail.
        # Let's rename the function to break the regex:
        (models_dir / 'model_a.py').write_text('def another_func():\n    pass\n')

        # Now function_name_regex '^helper_.*' will produce a violation because 'another_func' does not match 'helper_.*'
        # So must_not rule expects a violation. We get violation from the sub-rule, meaning the sub-rule fails as intended, no violation from BoolRule itself.
        # Actually, if must_not expects all to fail (all to produce violation), and our sub-rule function_name_regex 'helper_.*' doesn't match 'another_func',
        # that means sub-rule produce a violation = good for must_not (no BoolRule violation).

        config_data = {
            'deply': {
                'paths': ['./test_project'],
                'layers': [
                    {
                        'name': 'models',
                        'collectors': [
                            {
                                'type': 'directory',
                                'directories': ['models']
                            }
                        ]
                    }
                ],
                'ruleset': {
                    'models': {
                        'enforce_function_naming': [
                            {
                                'type': 'bool',
                                'must_not': [
                                    {
                                        'type': 'function_name_regex',
                                        'function_name_regex': '^helper_.*'
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }

        # 'another_func' does not match '^helper_.*', so function_name_regex rule will produce a violation.
        # must_not wants violations, so this is good. The BoolRule should return no violation overall.
        exit_code, output = self.run_deply(config_data)
        self.assertEqual(exit_code, 0, f"Expected no violations, but got exit code {exit_code}\nOutput:\n{output}")

    def test_bool_rule_must_not_fail(self):
        # must_not means all must fail (produce violation).
        # If sub-rule does not produce violation, must_not fails.
        # If we have a function_name_regex '^helper_.*' and 'helper_function' matches it,
        # then function_name_regex won't produce violation, so must_not fails.

        models_dir = self.test_project_dir / 'models'
        models_dir.mkdir()
        (models_dir / 'model_a.py').write_text('def helper_function():\n    pass\n')

        config_data = {
            'deply': {
                'paths': ['./test_project'],
                'layers': [
                    {
                        'name': 'models',
                        'collectors': [
                            {
                                'type': 'directory',
                                'directories': ['models']
                            }
                        ]
                    }
                ],
                'ruleset': {
                    'models': {
                        'enforce_function_naming': [
                            {
                                'type': 'bool',
                                'must_not': [
                                    {
                                        'type': 'function_name_regex',
                                        'function_name_regex': '^helper_.*'
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }

        # 'helper_function' matches '^helper_.*', so function_name_regex produces no violation (it passes).
        # must_not wants a violation, not a pass. So BoolRule should produce a violation.
        exit_code, output = self.run_deply(config_data)
        self.assertEqual(exit_code, 1, f"Expected violations, but got exit code {exit_code}\nOutput:\n{output}")
        self.assertIn("BoolRule failed: must_not rule", output)


if __name__ == '__main__':
    unittest.main()
