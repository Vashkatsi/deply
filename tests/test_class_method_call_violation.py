import json
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import yaml

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


class TestClassMethodCallViolation(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        self.test_project_dir = Path(self.test_dir) / 'test_project'
        self.test_project_dir.mkdir()

        # Create test files
        # Create base_model.py
        models_dir = self.test_project_dir / 'models'
        models_dir.mkdir()
        base_model_py = models_dir / 'base_model.py'
        base_model_py.write_text('class BaseModel:\n    pass\n')

        # Create my_model.py
        my_model_py = models_dir / 'my_model.py'
        my_model_py.write_text(
            'from .base_model import BaseModel\n'
            'class MyModel(BaseModel):\n'
            '    property = True\n'
            '    def get():\n'
            '        pass\n'
            'test_var = 1\n'
            'def test_func():\n'
            '   pass\n'
        )

        # Create views.py
        views_dir = self.test_project_dir / 'views'
        views_dir.mkdir()
        views_py = views_dir / 'views.py'
        views_py.write_text(
            'from models.my_model import MyModel\n'
            'from models.my_model import test_var\n'
            'from models.my_model import test_func\n'
            'def my_view():\n'
            '   MyModel().get()\n'
            '   model = MyModel()\n'
            '   model.get()\n'
            '   test_var\n'
            '   test_func()\n'
            'class View:\n'
            '   def view_function():\n'
            '       MyModel().get()\n'
            '       model = MyModel()\n'
            '       model.get()\n'
            '       test_var\n'
            '       test_func()\n'
        )

        # Write config.yaml
        self.config_yaml = Path(self.test_dir) / 'config.yaml'
        config_data = {
            'deply': {
                'paths': [str(self.test_project_dir)],
                'layers': [
                    {
                        'name': 'models',
                        'collectors': [
                            {
                                'type': 'file_regex',
                                'regex': '.*/my_model.py'
                            }
                        ]
                    },
                    {
                        'name': 'views',
                        'collectors': [
                            {
                                'type': 'file_regex',
                                'regex': '.*/views.py'
                            }
                        ]
                    }
                ],
                'ruleset': {
                    'views': {
                        'disallow_layer_dependencies': ['models']
                    }
                }
            }
        }
        with self.config_yaml.open('w') as f:
            yaml.dump(config_data, f)

    def tearDown(self):
        # Remove temporary directory
        shutil.rmtree(self.test_dir)

    def test_code_analyzer(self):
        # Capture the output
        with captured_output() as (out, err):
            try:
                # Run main with the test config
                sys.argv = ['main.py', 'analyze', '--config', str(self.config_yaml)]
                main()
            except SystemExit as e:
                exit_code = e.code
        output = out.getvalue()
        # Check that the exit code is 1 (violations found)
        self.assertEqual(exit_code, 1)
        # Check that the output contains the expected violation message
        self.assertIn("Layer 'views' is not allowed to depend on layer 'models'", output)
        self.assertIn("Total Violations               28", output)
        with captured_output() as (out, err), patch.object(sys, "argv", [
            "deply", "analyze", "--config", str(self.config_yaml), "--report-format", "json",
        ]):
            with self.assertRaises(SystemExit):
                main()
        payload = json.loads(out.getvalue())
        calls = [record for record in payload["violations"]
                 if record["line"] == 5 and record["dependency_type"] == "function_call"]
        self.assertEqual({(record["source"]["name"], record["target"]["name"]) for record in calls}, {
            ("my_view", "MyModel"), ("my_view", "MyModel.get"),
        })
        self.assertEqual(len({record["fingerprint"] for record in calls}), 2)


if __name__ == '__main__':
    unittest.main()
