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
from deply.main import main


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


if __name__ == "__main__":
    unittest.main()
