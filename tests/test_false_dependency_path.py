import os
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from typing import Tuple

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


class TestFalseDependencyPath(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_project_dir = Path(self.test_dir) / 'test_project'
        self.test_project_dir.mkdir()

        # Original files for the existing test_path_not_flagged_as_false_dependency
        service_py = self.test_project_dir / 'service.py'
        service_py.write_text(
            'from dataclasses import dataclass, field\n'
            'class LinkParams:\n'
            '    path: str = field(default="")\n'
            '    query: dict[str, str] = field(default_factory=dict)\n'
        )

        urls_py = self.test_project_dir / 'urls.py'
        urls_py.write_text(
            'from django.urls import path\n'
            '\n'
            'def create_path():\n'
            '    return path("some/url", None)\n'
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def run_deply(self, config_data) -> Tuple[int, str]:
        config_path = Path(self.test_dir) / 'deply.yaml'
        with config_path.open('w') as f:
            yaml.dump(config_data, f)

        old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        try:
            with captured_output() as (out, err):
                exit_code = 0
                try:
                    sys.argv = ['main.py', 'analyze', '--config', str(config_path)]
                    main()
                except SystemExit as e:
                    exit_code = e.code
            output = out.getvalue()
        finally:
            os.chdir(old_cwd)

        return exit_code, output

    def test_path_not_flagged_as_false_dependency(self):
        config_data = {
            'deply': {
                'paths': ['./test_project'],
                'layers': [
                    {
                        'name': 'service',
                        'collectors': [
                            {
                                'type': 'file_regex',
                                'regex': '.*/service.py'
                            }
                        ]
                    },
                    {
                        'name': 'urls',
                        'collectors': [
                            {
                                'type': 'file_regex',
                                'regex': '.*/urls.py'
                            }
                        ]
                    }
                ],
                'ruleset': {
                    'urls': {
                        'disallow_layer_dependencies': ['service']
                    }
                }
            }
        }

        exit_code, output = self.run_deply(config_data)
        self.assertEqual(exit_code, 0, f"Expected no violations. Output:\n{output}")

    def test_directory_collector_no_false_dependency(self):
        """
        This new test uses DirectoryCollector on 'services' and 'urls' directories
        to ensure referencing django.urls.path doesn't conflict with a local 'path'
        field in the service layer.
        """
        services_dir = self.test_project_dir / 'services'
        services_dir.mkdir(exist_ok=True)
        (services_dir / '__init__.py').write_text('')  # optional if needed

        my_service_file = services_dir / 'my_service.py'
        my_service_file.write_text(
            'class MyService:\n'
            '    path: str = "/test-path"\n'
            '    def do_something(self):\n'
            '        return self.path\n'
        )

        urls_dir = self.test_project_dir / 'urls_collector'
        urls_dir.mkdir(exist_ok=True)
        (urls_dir / '__init__.py').write_text('')  # optional if needed

        my_urls_file = urls_dir / 'my_urls.py'
        my_urls_file.write_text(
            'from django.urls import path\n'
            'def create_path():\n'
            '    return path("some/url", None)\n'
        )

        config_data = {
            'deply': {
                'paths': ['./test_project'],
                'layers': [
                    {
                        'name': 'services_layer',
                        'collectors': [
                            {
                                'type': 'directory',
                                'directories': ['services']
                            }
                        ]
                    },
                    {
                        'name': 'urls_layer',
                        'collectors': [
                            {
                                'type': 'directory',
                                'directories': ['urls_collector']
                            }
                        ]
                    }
                ],
                # Disallow the 'urls_layer' from depending on 'services_layer'
                'ruleset': {
                    'urls_layer': {
                        'disallow_layer_dependencies': ['services_layer']
                    }
                }
            }
        }

        exit_code, output = self.run_deply(config_data)
        # We expect no violations, because referencing django.urls.path
        # must not be confused with MyService.path
        self.assertEqual(exit_code, 0, f"Expected no violations. Output:\n{output}")

    def test_directory_collector_with_dependent_variable_and_directory_collector(self):
        """
        This new test uses DirectoryCollector on 'services' and 'urls' directories
        to ensure referencing django.urls.path doesn't conflict with a local 'path'
        field in the service layer.
        """
        services_dir = self.test_project_dir / 'services'
        services_dir.mkdir(exist_ok=True)
        (services_dir / '__init__.py').write_text('')  # optional if needed

        my_service_file = services_dir / 'my_service.py'
        my_service_file.write_text(
            'class MyService:\n'
            '    path: str = "/test-path"\n'
            '    def do_something(self):\n'
            '        return self.path\n'
            'test_var = 1\n'
        )

        urls_dir = self.test_project_dir / 'urls_collector'
        urls_dir.mkdir(exist_ok=True)
        (urls_dir / '__init__.py').write_text('')  # optional if needed

        my_urls_file = urls_dir / 'my_urls.py'
        my_urls_file.write_text(
            'from django.urls import path\n'
            'from services import test_var\n'
            'def create_path():\n'
            '    return path("some/url", None)\n'
        )

        config_data = {
            'deply': {
                'paths': ['./test_project'],
                'layers': [
                    {
                        'name': 'services_layer',
                        'collectors': [
                            {
                                'type': 'directory',
                                'directories': ['services']
                            }
                        ]
                    },
                    {
                        'name': 'urls_layer',
                        'collectors': [
                            {
                                'type': 'directory',
                                'directories': ['urls_collector']
                            }
                        ]
                    }
                ],
                # Disallow the 'urls_layer' from depending on 'services_layer'
                'ruleset': {
                    'urls_layer': {
                        'disallow_layer_dependencies': ['services_layer']
                    }
                }
            }
        }

        exit_code, output = self.run_deply(config_data)
        # We expect no violations, because referencing django.urls.path
        # must not be confused with MyService.path
        self.assertEqual(exit_code, 1, f"Expected no violations. Output:\n{output}")
        self.assertTrue(
            "test_project/urls_collector/my_urls.py:2:0 - Layer 'urls_layer' is not allowed to depend on layer 'services_layer'. Dependency type: import_from." in output,
            f"Expected no violations. Output:\n{output}"
        )


if __name__ == '__main__':
    unittest.main()
