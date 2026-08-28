import ast
import concurrent.futures
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from deply.code_analyzer import CodeAnalyzer
from deply.collectors.collector_factory import CollectorFactory
from deply.config_parser import ConfigParser
from deply.diagrams.marmaid_diagram_builder import MermaidDiagramBuilder
from deply.models.code_element import CodeElement
from deply.models.layer import Layer
from deply.models.violation import Violation
from deply.reports.report_generator import ReportGenerator
from deply.rules import RuleFactory
from deply.utils.ast_utils import parse_python_file
from deply.utils.ignore_parser import parse_ignore_comments, ALL_SUPPRESSION_RULES, IgnoreMap


class DeplyRunner:
    def __init__(self, args):
        self.args = args
        self.config = None
        self.paths = []
        self.exclude_files = []
        self.layers_config = []
        self.ruleset = {}
        self.layer_collectors = []
        self.all_files = []
        self.layers: Dict[str, Layer] = {}
        self.code_element_to_layers: Dict[CodeElement, Set[str]] = {}
        self.rules = []
        self.violations: Set[Violation] = set()
        self.metrics = {
            "files_discovered": 0,
            "files_excluded": 0,
            "files_included": 0,
            "files_parsed": 0,
            "files_parse_failed": 0,
            "files_mapped": 0,
            "files_unmapped": 0,
            "elements_mapped": 0,
            "elements_overlapping": 0,
            "dependencies_detected": 0,
        }
        self.mermaid_builder = MermaidDiagramBuilder()
        self.workers_count = 1
        self.ignore_maps = {}
        self.analysis_errors: List[str] = []

    def _get_workers_count(self) -> int:
        if self.args.parallel is None:
            return 1

        available_workers = os.cpu_count() or 1
        parallel_workers = int(self.args.parallel)

        if parallel_workers == 0:
            return available_workers
        return min(available_workers, parallel_workers)

    def load_configuration(self):
        config_path = Path(self.args.config)
        logging.info(f"Using configuration file: {config_path}")
        self.config = ConfigParser(config_path).parse()
        self.paths = [Path(p) for p in self.config["paths"]]
        self.exclude_files = [re.compile(pattern) for pattern in self.config["exclude_files"]]
        self.layers_config = self.config["layers"]
        self.ruleset = self.config["ruleset"]
        self.workers_count = self._get_workers_count()

    def map_layer_collectors(self):
        logging.info("Mapping layer collectors...")
        for layer_config in self.layers_config:
            layer_name = layer_config["name"]
            collector_configs = layer_config.get("collectors", [])
            for collector_config in collector_configs:
                collector = CollectorFactory.create(
                    config=collector_config,
                    paths=[str(p) for p in self.paths],
                    exclude_files=[p.pattern for p in self.exclude_files]
                )
                self.layer_collectors.append((layer_name, collector))

    def collect_all_files(self):
        logging.info("Collecting all files...")
        discovered_files: Set[Path] = set()
        included_files: Set[Path] = set()
        for base_path in self.paths:
            if not base_path.exists():
                continue
            all_python_files = [f for f in base_path.rglob("*.py") if f.is_file()]
            discovered_files.update(all_python_files)

            def is_excluded(file_path: Path) -> bool:
                try:
                    relative_path = str(file_path.relative_to(base_path))
                except ValueError:
                    return True
                return any(pattern.search(relative_path) for pattern in self.exclude_files)

            included_files.update(f for f in all_python_files if not is_excluded(f))

        self.all_files = sorted(included_files)
        self.metrics["files_discovered"] = len(discovered_files)
        self.metrics["files_included"] = len(included_files)
        self.metrics["files_excluded"] = len(discovered_files - included_files)

    def collect_code_elements(self):
        logging.info(
            f"Collecting code elements for each layer with {self.workers_count} workers..."
        )
        # Initialize layers
        for layer_config in self.layers_config:
            layer_name = layer_config["name"]
            self.layers[layer_name] = Layer(name=layer_name, code_elements=set(), dependencies=set())

        def collect_file_result(file_result):
            file_path_str, results, ignore_map, analysis_error = file_result
            self.ignore_maps[file_path_str] = ignore_map
            if analysis_error:
                self.analysis_errors.append(analysis_error)
                self.metrics["files_parse_failed"] += 1
            else:
                self.metrics["files_parsed"] += 1
                metric_name = "files_mapped" if results else "files_unmapped"
                self.metrics[metric_name] += 1
            for layer_name, element in results:
                self.layers[layer_name].code_elements.add(element)
                self.code_element_to_layers.setdefault(element, set()).add(layer_name)

        if self.workers_count > 1:
            with concurrent.futures.ProcessPoolExecutor(max_workers=self.workers_count) as executor:
                futures = [
                    executor.submit(process_file, file_path, self.layer_collectors)
                    for file_path in self.all_files
                ]
                for future in concurrent.futures.as_completed(futures):
                    collect_file_result(future.result())
        else:
            for file_path in self.all_files:
                collect_file_result(process_file(file_path, self.layer_collectors))

        for layer_name, layer in self.layers.items():
            logging.info(
                f"Layer '{layer_name}' collected {len(layer.code_elements)} code elements."
            )

        self.metrics["elements_mapped"] = len(self.code_element_to_layers)
        self.metrics["elements_overlapping"] = sum(
            len(layer_names) > 1 for layer_names in self.code_element_to_layers.values()
        )

    def prepare_rules(self):
        logging.info("Preparing rules...")
        self.rules = RuleFactory.create_rules(self.ruleset)

    def is_violation_suppressed(self, violation: Violation) -> bool:
        file_key = str(violation.file)
        ignore_map = self.ignore_maps.get(file_key, {"file": set(), "lines": {}})
        # Check file-level suppression
        if (
                ALL_SUPPRESSION_RULES in ignore_map.get("file", set())
                or violation.violation_type.code.upper() in ignore_map.get("file", set())
        ):
            return True

        # Check line-level suppression
        line_rules = ignore_map.get("lines", {}).get(violation.line, set())
        if ALL_SUPPRESSION_RULES in line_rules or violation.violation_type.code.upper() in line_rules:
            return True

        return False

    def analyze_dependencies(self):
        def dependency_handler(dependency):
            source = dependency.code_element
            target = dependency.depends_on_code_element
            source_layers = self.code_element_to_layers.get(source)
            target_layers = self.code_element_to_layers.get(target)
            self.metrics["dependencies_detected"] += 1
            if not source_layers or not target_layers:
                return
            for source_layer in sorted(source_layers):
                for target_layer in sorted(target_layers):
                    if source_layer == target_layer:
                        continue
                    has_violation = False
                    for rule in self.rules:
                        violation = rule.check(source_layer, target_layer, dependency)
                        if violation and not self.is_violation_suppressed(violation):
                            self.violations.add(violation)
                            has_violation = True
                    self.mermaid_builder.add_edge(source_layer, target_layer, has_violation)

        logging.info("Analyzing code and checking dependencies ...")
        analyzer = CodeAnalyzer(
            code_elements=set(self.code_element_to_layers.keys()),
            dependency_handler=dependency_handler
        )
        analysis_errors = analyzer.analyze()
        self.analysis_errors.extend(analysis_errors)
        if analysis_errors:
            return
        logging.info(
            f"Analysis complete. Found {self.metrics['dependencies_detected']} dependencies(s)."
        )

    def run_element_based_checks(self):
        logging.info("Running element-based checks ...")
        for layer_name, layer in self.layers.items():
            for element in layer.code_elements:
                for rule in self.rules:
                    violation_candidate = rule.check_element(layer_name, element)
                    if violation_candidate and not self.is_violation_suppressed(violation_candidate):
                        self.violations.add(violation_candidate)

    def run_external_import_checks(self):
        external_import_rules = [
            rule for rule in self.rules if getattr(rule, "checks_external_imports", False)
        ]
        if not external_import_rules:
            return

        file_layer_elements: Dict[Tuple[Path, str], CodeElement] = {}
        for element, layer_names in self.code_element_to_layers.items():
            for layer_name in layer_names:
                key = (element.file, layer_name)
                current_element = file_layer_elements.get(key)
                if current_element is None or (
                        element.line,
                        element.column,
                        element.name,
                ) < (
                        current_element.line,
                        current_element.column,
                        current_element.name,
                ):
                    file_layer_elements[key] = element

        imports_by_file: Dict[Path, List[Tuple[str, int, int]]] = {}
        for (file_path, layer_name), element in file_layer_elements.items():
            if file_path not in imports_by_file:
                imports_by_file[file_path] = extract_absolute_imports(file_path, self.analysis_errors)
            imports = imports_by_file[file_path]
            for module_name, line, column in imports:
                for rule in external_import_rules:
                    violation_candidate = rule.check_external_import(
                        layer_name,
                        element,
                        module_name,
                        line,
                        column,
                    )
                    if violation_candidate and not self.is_violation_suppressed(violation_candidate):
                        self.violations.add(violation_candidate)

    def generate_report(self):
        logging.info("Generating report...")
        return ReportGenerator(list(self.violations), self.metrics).generate(self.args.report_format)

    def output_report(self, report):
        if self.args.output:
            output_path = Path(self.args.output)
            output_path.write_text(report)
            logging.info(f"Report written to {output_path}")
        else:
            print("\n")
            print(report)
        if self.args.mermaid:
            mermaid_diagram = self.mermaid_builder.build_diagram()
            print("\n[Mermaid Diagram of Layer Dependencies]\n")
            print(mermaid_diagram)

    def is_analysis_complete(self) -> bool:
        if not self.analysis_errors:
            return True

        print("Incomplete analysis:", file=sys.stderr)
        for analysis_error in sorted(self.analysis_errors):
            print(f"- {analysis_error}", file=sys.stderr)
        metrics_summary = ", ".join(
            f"{name}={value}" for name, value in self.metrics.items()
        )
        print(f"Analysis completeness: {metrics_summary}", file=sys.stderr)
        return False

    def run(self):
        self.load_configuration()
        self.map_layer_collectors()
        self.collect_all_files()
        if not self.all_files:
            self.analysis_errors.append("no Python files found")
            return self.is_analysis_complete()

        self.collect_code_elements()
        if not self.code_element_to_layers:
            self.analysis_errors.append("no code elements mapped to configured layers")
        if not self.is_analysis_complete():
            return False

        self.prepare_rules()
        self.analyze_dependencies()
        if not self.is_analysis_complete():
            return False

        self.run_element_based_checks()
        self.run_external_import_checks()
        if not self.is_analysis_complete():
            return False

        report = self.generate_report()
        self.output_report(report)

        return len(self.violations) <= self.args.max_violations


def extract_absolute_imports(
        file_path: Path,
        analysis_errors: Optional[List[str]] = None,
) -> List[Tuple[str, int, int]]:
    imports: List[Tuple[str, int, int]] = []
    try:
        file_ast, _ = parse_python_file(file_path)
    except (OSError, SyntaxError, UnicodeError) as exception:
        if analysis_errors is not None:
            analysis_errors.append(f"failed to analyze {file_path}: {exception}")
        return imports

    for node in ast.walk(file_ast):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno, node.col_offset))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                imports.append((node.module, node.lineno, node.col_offset))

    return imports


def process_file(
        file_path: Path,
        layer_collectors: List[Tuple[str, Any]],
) -> Tuple[str, List[Tuple[str, CodeElement]], IgnoreMap, Optional[str]]:
    results: List[Tuple[str, CodeElement]] = []
    ignore_map: IgnoreMap = {"file": set(), "lines": {}}
    try:
        file_ast, file_bytes = parse_python_file(file_path)
        ignore_map = parse_ignore_comments(file_path, file_bytes=file_bytes)
    except Exception as exception:
        return str(file_path), results, ignore_map, f"failed to analyze {file_path}: {exception}"

    for layer_name, collector in layer_collectors:
        matched_elements = collector.match_in_file(file_ast, file_path)
        for element in matched_elements:
            results.append((layer_name, element))
    return str(file_path), results, ignore_map, None
