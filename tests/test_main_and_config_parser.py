import logging
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import yaml

from deply import __version__
from deply.config_parser import ConfigParser
from deply.main import main, validate_configuration


class TestMainAndConfigParser(unittest.TestCase):
    def test_main_version_flag_exits_with_zero_and_prints_version(self):
        with patch.object(sys, "argv", ["main.py", "--version"]), patch("sys.stdout", new=StringIO()) as output_stream:
            with self.assertRaises(SystemExit) as exit_context:
                main()

        self.assertEqual(exit_context.exception.code, 0)
        self.assertIn(f"deply {__version__}", output_stream.getvalue())

    def test_main_uses_analyze_as_default_command(self):
        with patch.object(sys, "argv", ["main.py"]), patch("deply.main.DeplyRunner") as runner_class:
            runner_class.return_value.run.return_value = True

            with self.assertRaises(SystemExit) as exit_context:
                main()

        self.assertEqual(exit_context.exception.code, 0)
        args_object = runner_class.call_args.args[0]
        self.assertEqual(args_object.command, "analyze")

    def test_main_sets_debug_log_level_when_verbose_is_two_or_more(self):
        with patch.object(sys, "argv", ["main.py", "-vv", "analyze"]), patch(
            "deply.main.DeplyRunner"
        ) as runner_class, patch("deply.main.logging.basicConfig") as basic_config_function:
            runner_class.return_value.run.return_value = True

            with self.assertRaises(SystemExit):
                main()

        self.assertEqual(basic_config_function.call_args.kwargs["level"], logging.DEBUG)

    def test_main_sets_info_log_level_by_default(self):
        with patch.object(sys, "argv", ["main.py", "analyze"]), patch(
            "deply.main.DeplyRunner"
        ) as runner_class, patch("deply.main.logging.basicConfig") as basic_config_function:
            runner_class.return_value.run.return_value = True

            with self.assertRaises(SystemExit):
                main()

        self.assertEqual(basic_config_function.call_args.kwargs["level"], logging.INFO)

    def test_config_parser_sets_default_path_when_paths_not_provided(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            configuration_path = Path(temporary_directory) / "deply.yaml"
            configuration_path.write_text(
                yaml.dump(
                    {
                        "deply": {
                            "exclude_files": [],
                            "layers": [],
                            "ruleset": {},
                        }
                    }
                )
            )

            parsed_configuration = ConfigParser(configuration_path).parse()

        self.assertEqual(parsed_configuration["paths"], [str(configuration_path.parent)])
        self.assertEqual(parsed_configuration["exclude_files"], [])
        self.assertEqual(parsed_configuration["layers"], [])
        self.assertEqual(parsed_configuration["ruleset"], {})

    def test_config_parser_rejects_invalid_deply_root(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            configuration_path = Path(temporary_directory) / "deply.yaml"
            configuration_path.write_text(yaml.dump({"deply": []}))

            with self.assertRaises(ValueError) as context:
                ConfigParser(configuration_path).parse()

        self.assertIn("Invalid deply configuration format", str(context.exception))

    def test_main_validate_exits_zero_for_valid_configuration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory) / "project"
            project_path.mkdir()
            configuration_path = Path(temporary_directory) / "deply.yaml"
            configuration_path.write_text(
                yaml.dump(
                    {
                        "deply": {
                            "paths": [str(project_path)],
                            "exclude_files": [],
                            "layers": [
                                {
                                    "name": "domain",
                                    "collectors": [
                                        {
                                            "type": "class_inherits",
                                            "base_class": "Entity",
                                        }
                                    ],
                                }
                            ],
                            "ruleset": {},
                        }
                    }
                )
            )

            with patch.object(sys, "argv", ["main.py", "validate", "--config", str(configuration_path)]), patch(
                "deply.main.DeplyRunner"
            ) as runner_class, patch("sys.stdout", new=StringIO()) as output_stream:
                with self.assertRaises(SystemExit) as exit_context:
                    main()

        self.assertEqual(exit_context.exception.code, 0)
        runner_class.assert_not_called()
        self.assertIn(f"Configuration is valid: {configuration_path}", output_stream.getvalue())

    def test_main_validate_exits_one_for_invalid_configuration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            configuration_path = Path(temporary_directory) / "deply.yaml"
            configuration_path.write_text(
                yaml.dump(
                    {
                        "deply": {
                            "paths": ["/path/that/does/not/exist"],
                            "exclude_files": ["["],
                            "layers": [],
                            "ruleset": {},
                        }
                    }
                )
            )

            with patch.object(sys, "argv", ["main.py", "validate", "--config", str(configuration_path)]), patch(
                "sys.stderr", new=StringIO()
            ) as error_stream:
                with self.assertRaises(SystemExit) as exit_context:
                    main()

        self.assertEqual(exit_context.exception.code, 1)
        error_output = error_stream.getvalue()
        self.assertEqual(error_output.splitlines()[0], "Invalid deply configuration:")
        self.assertIn("paths[0]: path does not exist: /path/that/does/not/exist", error_output)
        self.assertIn("layers: must contain at least one layer", error_output)

    def test_main_validate_exits_one_for_parser_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            configuration_path = Path(temporary_directory) / "deply.yaml"
            configuration_path.write_text(yaml.dump({"deply": []}))

            with patch.object(sys, "argv", ["main.py", "validate", "--config", str(configuration_path)]), patch(
                "sys.stderr", new=StringIO()
            ) as error_stream:
                with self.assertRaises(SystemExit) as exit_context:
                    main()

        self.assertEqual(exit_context.exception.code, 1)
        self.assertEqual(error_stream.getvalue().splitlines()[0], "Invalid deply configuration:")
        self.assertIn("Invalid deply configuration format", error_stream.getvalue())

    def test_main_validate_exits_one_for_invalid_yaml(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            configuration_path = Path(temporary_directory) / "deply.yaml"
            configuration_path.write_text("deply: [")

            with patch.object(sys, "argv", ["main.py", "validate", "--config", str(configuration_path)]), patch(
                "sys.stderr", new=StringIO()
            ) as error_stream:
                with self.assertRaises(SystemExit) as exit_context:
                    main()

        self.assertEqual(exit_context.exception.code, 1)
        self.assertEqual(error_stream.getvalue().splitlines()[0], "Invalid deply configuration:")

    def test_validate_configuration_passes_config_path_to_validator(self):
        with patch("deply.main.ConfigParser") as parser_class, patch(
            "deply.main.ConfigValidator"
        ) as validator_class, patch("sys.stdout", new=StringIO()):
            parser_class.return_value.parse.return_value = {"paths": []}
            validator_class.return_value.validate.return_value = []

            result = validate_configuration("custom.yaml")

        self.assertTrue(result)
        validator_class.assert_called_once_with(Path("custom.yaml"))
        validator_class.return_value.validate.assert_called_once_with({"paths": []})

    def test_validate_configuration_prints_invalid_header(self):
        with patch("deply.main.ConfigParser") as parser_class, patch("deply.main.ConfigValidator") as validator_class:
            parser_class.return_value.parse.return_value = {}
            validator_class.return_value.validate.return_value = ["paths: required"]

            with patch("sys.stderr", new=StringIO()) as error_stream:
                result = validate_configuration("custom.yaml")

        self.assertFalse(result)
        self.assertEqual(error_stream.getvalue().splitlines()[0], "Invalid deply configuration:")
        self.assertIn("- paths: required", error_stream.getvalue())


if __name__ == "__main__":
    unittest.main()
