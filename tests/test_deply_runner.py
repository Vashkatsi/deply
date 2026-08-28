import argparse
import codecs
import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from deply.code_analyzer import CodeAnalyzer
from deply.deply_runner import DeplyRunner, process_file
from deply.models.code_element import CodeElement
from deply.models.dependency import Dependency
from deply.models.violation import Violation
from deply.models.violation_types import ViolationType
from deply.rules.dependency_rule import DependencyRule


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

    def _write_config(self, project_path: Path, collector_regex: str = r".*\.py$") -> Path:
        config_path = project_path.parent / "deply.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "deply": {
                        "paths": [str(project_path)],
                        "layers": [
                            {
                                "name": "application",
                                "collectors": [
                                    {
                                        "type": "file_regex",
                                        "regex": collector_regex,
                                    }
                                ],
                            }
                        ],
                        "ruleset": {},
                    }
                }
            )
        )
        return config_path

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

    def test_is_violation_not_suppressed_when_file_has_no_ignore_map(self):
        violation = self._build_violation(Path("/tmp/missing_ignore_map.py"), line=20)
        self.runner.ignore_maps = {}

        self.assertFalse(self.runner.is_violation_suppressed(violation))

    def test_analysis_is_complete_without_errors(self):
        self.assertTrue(self.runner.is_analysis_complete())

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

    def test_collect_all_files_applies_exclude_patterns_to_relative_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base_path = Path(temporary_directory)
            keep_file_path = base_path / "keep.py"
            ignored_file_path = base_path / "generated" / "ignored.py"
            ignored_file_path.parent.mkdir()
            keep_file_path.write_text("class Keep:\n    pass\n")
            ignored_file_path.write_text("class Ignored:\n    pass\n")
            self.runner.paths = [base_path]
            self.runner.exclude_files = [re.compile(r"generated/ignored\.py$")]

            self.runner.collect_all_files()

        self.assertEqual(set(self.runner.all_files), {keep_file_path})
        self.assertEqual(
            self.runner.metrics,
            {
                "files_discovered": 2,
                "files_excluded": 1,
                "files_included": 1,
                "files_parsed": 0,
                "files_parse_failed": 0,
                "files_mapped": 0,
                "files_unmapped": 0,
                "elements_mapped": 0,
                "elements_overlapping": 0,
                "dependencies_detected": 0,
            },
        )

    def test_collect_all_files_deduplicates_overlapping_paths_and_keeps_included_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base_path = Path(temporary_directory)
            nested_path = base_path / "nested"
            nested_path.mkdir()
            file_path = nested_path / "service.py"
            file_path.write_text("class Service:\n    pass\n")
            self.runner.paths = [base_path, nested_path]
            self.runner.exclude_files = [re.compile(r"^nested/service\.py$")]

            self.runner.collect_all_files()

        self.assertEqual(self.runner.all_files, [file_path])
        self.assertEqual(self.runner.metrics["files_discovered"], 1)
        self.assertEqual(self.runner.metrics["files_included"], 1)
        self.assertEqual(self.runner.metrics["files_excluded"], 0)

    def test_analyze_dependencies_updates_metrics_violations_and_mermaid_edges(self):
        source_element = CodeElement(
            file=Path("views.py"),
            name="view",
            element_type="function",
            line=1,
            column=0,
        )
        target_element = CodeElement(
            file=Path("models.py"),
            name="Model",
            element_type="class",
            line=1,
            column=0,
        )
        dependency = Dependency(
            code_element=source_element,
            depends_on_code_element=target_element,
            dependency_type="function_call",
            line=3,
            column=4,
        )
        self.runner.code_element_to_layers = {
            source_element: {"views"},
            target_element: {"models"},
        }
        self.runner.rules = [DependencyRule("views", ["models"])]

        def run_analyzer():
            analyzer_class.call_args.kwargs["dependency_handler"](dependency)
            return []

        with patch("deply.deply_runner.CodeAnalyzer") as analyzer_class:
            analyzer_class.return_value.analyze.side_effect = run_analyzer
            with patch.object(self.runner.mermaid_builder, "add_edge") as add_edge:
                self.runner.analyze_dependencies()

        self.assertEqual(self.runner.metrics["dependencies_detected"], 1)
        self.assertEqual(len(self.runner.violations), 1)
        violation = next(iter(self.runner.violations))
        self.assertEqual(violation.dependency, dependency)
        add_edge.assert_called_once_with("views", "models", True)

    def test_analyze_dependencies_checks_every_layer_membership_pair(self):
        source_element = CodeElement(
            file=Path("source.py"),
            name="source",
            element_type="function",
            line=1,
            column=0,
        )
        target_element = CodeElement(
            file=Path("target.py"),
            name="Target",
            element_type="class",
            line=1,
            column=0,
        )
        dependency = Dependency(
            code_element=source_element,
            depends_on_code_element=target_element,
            dependency_type="function_call",
            line=3,
            column=4,
        )
        self.runner.code_element_to_layers = {
            source_element: {"application", "feature"},
            target_element: {"domain", "feature"},
        }
        self.runner.rules = [DependencyRule("application", ["domain"])]

        def run_analyzer():
            analyzer_class.call_args.kwargs["dependency_handler"](dependency)
            return []

        with patch("deply.deply_runner.CodeAnalyzer") as analyzer_class:
            analyzer_class.return_value.analyze.side_effect = run_analyzer
            self.runner.analyze_dependencies()

        self.assertEqual(self.runner.metrics["dependencies_detected"], 1)
        self.assertEqual(len(self.runner.violations), 1)
        self.assertEqual(
            self.runner.mermaid_builder.edges_with_violation,
            {
                ("application", "domain"): True,
                ("application", "feature"): False,
                ("feature", "domain"): False,
            },
        )

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
            None,
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
        self.assertEqual(self.runner.code_element_to_layers[collected_element], {"services_layer"})
        self.assertIn("service.py", self.runner.ignore_maps)
        self.assertEqual(self.runner.metrics["files_parsed"], 1)
        self.assertEqual(self.runner.metrics["files_mapped"], 1)
        self.assertEqual(self.runner.metrics["elements_mapped"], 1)

    def test_collect_code_elements_preserves_overlapping_layer_memberships(self):
        collected_element = CodeElement(
            file=Path("service.py"),
            name="Service",
            element_type="class",
            line=1,
            column=0,
        )

        for collected_layers in (("context", "domain"), ("domain", "context")):
            with self.subTest(collected_layers=collected_layers):
                self.runner = DeplyRunner(self.args)
                self.runner.layers_config = [
                    {"name": "context"},
                    {"name": "domain"},
                ]
                self.runner.layer_collectors = []
                self.runner.all_files = [Path("service.py")]

                with patch(
                    "deply.deply_runner.process_file",
                    return_value=(
                        "service.py",
                        [(layer_name, collected_element) for layer_name in collected_layers],
                        {"file": set(), "lines": {}},
                        None,
                    ),
                ):
                    self.runner.collect_code_elements()

                self.assertEqual(
                    self.runner.code_element_to_layers[collected_element],
                    {"context", "domain"},
                )
                self.assertEqual(self.runner.metrics["elements_mapped"], 1)
                self.assertEqual(self.runner.metrics["elements_overlapping"], 1)

    def test_process_file_reports_syntax_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as temporary_file:
            temporary_file.write("def invalid(:\n")
            invalid_file_path = Path(temporary_file.name)

        try:
            processed_file_path, processed_results, processed_ignore_map, analysis_error = process_file(
                invalid_file_path,
                [],
            )
        finally:
            invalid_file_path.unlink(missing_ok=True)

        self.assertEqual(processed_file_path, str(invalid_file_path))
        self.assertEqual(processed_results, [])
        self.assertEqual(processed_ignore_map, {"file": set(), "lines": {}})
        self.assertIn(f"failed to analyze {invalid_file_path}:", analysis_error)

    def test_process_file_reports_ignore_tokenization_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as temporary_file:
            temporary_file.write("# coding: no-such-codec\ndef service():\n    pass\n")
            invalid_file_path = Path(temporary_file.name)

        try:
            _, _, _, analysis_error = process_file(invalid_file_path, [])
        finally:
            invalid_file_path.unlink(missing_ok=True)

        self.assertIn(f"failed to analyze {invalid_file_path}:", analysis_error)

    def test_run_fails_when_no_python_files_are_found(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory) / "project"
            project_path.mkdir()
            self.runner.args.config = str(self._write_config(project_path))

            with patch("sys.stderr", new=io.StringIO()) as error_stream:
                result = self.runner.run()

        self.assertFalse(result)
        self.assertIn("Incomplete analysis:\n- no Python files found", error_stream.getvalue())

    def test_run_fails_when_no_elements_map_to_a_layer(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory) / "project"
            project_path.mkdir()
            (project_path / "service.py").write_text("def service():\n    pass\n")
            self.runner.args.config = str(self._write_config(project_path, r"never-matches"))

            with patch("sys.stderr", new=io.StringIO()) as error_stream:
                result = self.runner.run()

        self.assertFalse(result)
        self.assertEqual(
            error_stream.getvalue(),
            "Incomplete analysis:\n- no code elements mapped to configured layers\n",
        )

    def test_run_fails_on_parse_error_in_sequential_and_parallel_modes(self):
        metrics_by_mode = []
        for parallel in (None, 2):
            with self.subTest(parallel=parallel), tempfile.TemporaryDirectory() as temporary_directory:
                project_path = Path(temporary_directory) / "project"
                project_path.mkdir()
                (project_path / "service.py").write_text("class Service:\n    pass\n")
                invalid_file_path = project_path / "invalid.py"
                invalid_file_path.write_text("def invalid(:\n")
                self.runner = DeplyRunner(
                    argparse.Namespace(
                        config=str(self._write_config(project_path)),
                        parallel=parallel,
                        report_format="text",
                        output=None,
                        mermaid=False,
                        max_violations=0,
                    )
                )

                with patch("os.cpu_count", return_value=2), patch(
                    "sys.stderr",
                    new=io.StringIO(),
                ) as error_stream:
                    result = self.runner.run()

            self.assertFalse(result)
            self.assertEqual(self.runner.workers_count, 1 if parallel is None else 2)
            self.assertIn(f"failed to analyze {invalid_file_path}:", error_stream.getvalue())
            metrics_by_mode.append(self.runner.metrics)

        self.assertEqual(metrics_by_mode[0], metrics_by_mode[1])
        self.assertEqual(
            metrics_by_mode[0],
            {
                "files_discovered": 2,
                "files_excluded": 0,
                "files_included": 2,
                "files_parsed": 1,
                "files_parse_failed": 1,
                "files_mapped": 1,
                "files_unmapped": 0,
                "elements_mapped": 1,
                "elements_overlapping": 0,
                "dependencies_detected": 0,
            },
        )

    def test_run_accepts_python_source_encodings_in_sequential_and_parallel_modes(self):
        source_files = {
            "pep263": "# coding: latin-1\nclass Café:\n    pass\n".encode("latin-1"),
            "utf8_bom": codecs.BOM_UTF8 + b"class Service:\n    pass\n",
        }
        for source_name, source_bytes in source_files.items():
            for parallel in (None, 2):
                with self.subTest(source=source_name, parallel=parallel), tempfile.TemporaryDirectory() as directory:
                    project_path = Path(directory) / "project"
                    project_path.mkdir()
                    (project_path / "service.py").write_bytes(source_bytes)
                    runner = DeplyRunner(
                        argparse.Namespace(
                            config=str(self._write_config(project_path)),
                            parallel=parallel,
                            report_format="text",
                            output=None,
                            mermaid=False,
                            max_violations=0,
                        )
                    )

                    with patch("os.cpu_count", return_value=2), patch("sys.stdout", new=io.StringIO()), patch(
                        "sys.stderr",
                        new=io.StringIO(),
                    ):
                        result = runner.run()

                self.assertTrue(result)
                self.assertEqual(runner.analysis_errors, [])

    def test_code_analyzer_reports_files_that_cannot_be_read(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_file = Path(temporary_directory) / "missing.py"
            code_element = CodeElement(
                file=missing_file,
                name="service",
                element_type="function",
                line=1,
                column=0,
            )

            errors = CodeAnalyzer({code_element}, lambda dependency: None).analyze()

        self.assertEqual(len(errors), 1)
        self.assertIn(f"failed to analyze {missing_file}:", errors[0])


if __name__ == "__main__":
    unittest.main()
