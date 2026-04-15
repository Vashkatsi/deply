import argparse
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from deply.deply_runner import DeplyRunner, process_file
from deply.models.code_element import CodeElement
from deply.models.violation import Violation
from deply.models.violation_types import ViolationType


class TestDeplyRunnerArguments(unittest.TestCase):
    def setUp(self):
        self.mock_args = MagicMock()
        self.runner = DeplyRunner(self.mock_args)

    @patch("os.cpu_count", return_value=8)
    def test_workers_count_no_parallel(self, _mock_cpu_count):
        self.mock_args.parallel = None
        self.assertEqual(self.runner._get_workers_count(), 1)

    @patch("os.cpu_count", return_value=8)
    def test_workers_count_parallel_zero(self, _mock_cpu_count):
        self.mock_args.parallel = 0
        self.assertEqual(self.runner._get_workers_count(), 8)

    @patch("os.cpu_count", return_value=8)
    def test_workers_count_parallel_less_than_cpu(self, _mock_cpu_count):
        self.mock_args.parallel = 2
        self.assertEqual(self.runner._get_workers_count(), 2)

    @patch("os.cpu_count", return_value=8)
    def test_workers_count_parallel_more_than_cpu(self, _mock_cpu_count):
        self.mock_args.parallel = 100
        self.assertEqual(self.runner._get_workers_count(), 8)


class TestDeplyRunnerBehavior(unittest.TestCase):
    def setUp(self):
        self.args = argparse.Namespace(
            config="deply.yaml",
            parallel=None,
            report_format="text",
            output=None,
            mermaid=False,
            max_violations=0,
        )
        self.runner = DeplyRunner(self.args)

    def _build_violation(self, file_path: Path, line: int = 1) -> Violation:
        return Violation(
            file=file_path,
            element_name="Element",
            element_type="class",
            line=line,
            column=0,
            message="message",
            violation_type=ViolationType.DISALLOWED_DEPENDENCY,
        )

    def test_is_violation_suppressed_by_file_level_all_rules(self):
        file_path = Path("/tmp/file_level_all.py")
        violation = self._build_violation(file_path)
        self.runner.ignore_maps = {
            str(file_path): {
                "file": {"*"},
                "lines": {},
            }
        }

        self.assertTrue(self.runner.is_violation_suppressed(violation))

    def test_is_violation_suppressed_by_file_level_rule_code(self):
        file_path = Path("/tmp/file_level_specific.py")
        violation = self._build_violation(file_path)
        self.runner.ignore_maps = {
            str(file_path): {
                "file": {"DISALLOWED_DEPENDENCY"},
                "lines": {},
            }
        }

        self.assertTrue(self.runner.is_violation_suppressed(violation))

    def test_is_violation_suppressed_by_line_level_rule_code(self):
        file_path = Path("/tmp/line_level_specific.py")
        violation = self._build_violation(file_path, line=12)
        self.runner.ignore_maps = {
            str(file_path): {
                "file": set(),
                "lines": {
                    12: {"DISALLOWED_DEPENDENCY"},
                },
            }
        }

        self.assertTrue(self.runner.is_violation_suppressed(violation))

    def test_is_violation_not_suppressed_when_no_matching_rule(self):
        file_path = Path("/tmp/not_suppressed.py")
        violation = self._build_violation(file_path, line=20)
        self.runner.ignore_maps = {
            str(file_path): {
                "file": set(),
                "lines": {
                    20: {"FUNCTION_NAMING"},
                },
            }
        }

        self.assertFalse(self.runner.is_violation_suppressed(violation))

    def test_output_report_writes_to_file_when_output_path_is_provided(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "report.txt"
            self.runner.args.output = str(output_path)
            self.runner.args.mermaid = False

            self.runner.output_report("report content")

            self.assertEqual(output_path.read_text(), "report content")

    def test_output_report_prints_report_and_mermaid_when_requested(self):
        self.runner.args.output = None
        self.runner.args.mermaid = True

        with patch.object(self.runner.mermaid_builder, "build_diagram", return_value="graph LR"):
            with patch("sys.stdout", new=io.StringIO()) as output_stream:
                self.runner.output_report("report content")

        output = output_stream.getvalue()
        self.assertIn("report content", output)
        self.assertIn("[Mermaid Diagram of Layer Dependencies]", output)
        self.assertIn("graph LR", output)

    def test_collect_all_files_skips_non_existent_paths(self):
        self.runner.paths = [Path("/tmp/deply_non_existent_path")]
        self.runner.exclude_files = []

        self.runner.collect_all_files()

        self.assertEqual(self.runner.all_files, [])

    def test_collect_all_files_handles_relative_to_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base_path = Path(temporary_directory)
            self.runner.paths = [base_path]
            self.runner.exclude_files = []
            external_file_path = Path(temporary_directory).parent / "external.py"

            with patch("pathlib.Path.rglob", return_value=[external_file_path]):
                self.runner.collect_all_files()

        self.assertEqual(self.runner.all_files, [])

    def test_collect_code_elements_parallel_branch(self):
        self.runner.layers_config = [{"name": "services_layer"}]
        self.runner.layer_collectors = []
        self.runner.all_files = [Path("service.py")]
        self.runner.workers_count = 2

        collected_element = CodeElement(
            file=Path("service.py"),
            name="Service",
            element_type="class",
            line=1,
            column=0,
        )

        future_mock = MagicMock()
        future_mock.result.return_value = (
            "service.py",
            [("services_layer", collected_element)],
            {"file": set(), "lines": {}},
        )

        executor_mock = MagicMock()
        executor_mock.__enter__.return_value = executor_mock
        executor_mock.submit.return_value = future_mock

        with patch(
            "deply.deply_runner.concurrent.futures.ProcessPoolExecutor",
            return_value=executor_mock,
        ), patch(
            "deply.deply_runner.concurrent.futures.as_completed",
            return_value=[future_mock],
        ):
            self.runner.collect_code_elements()

        self.assertIn(collected_element, self.runner.layers["services_layer"].code_elements)
        self.assertEqual(self.runner.code_element_to_layer[collected_element], "services_layer")
        self.assertIn("service.py", self.runner.ignore_maps)

    def test_process_file_returns_empty_results_on_syntax_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as temporary_file:
            temporary_file.write("def invalid(:\n")
            invalid_file_path = Path(temporary_file.name)

        try:
            processed_file_path, processed_results, processed_ignore_map = process_file(invalid_file_path, [])
        finally:
            invalid_file_path.unlink(missing_ok=True)

        self.assertEqual(processed_file_path, str(invalid_file_path))
        self.assertEqual(processed_results, [])
        self.assertEqual(processed_ignore_map, {"file": set(), "lines": {}})


if __name__ == "__main__":
    unittest.main()
