import ast
import concurrent.futures
import logging
import os
import re
from pathlib import Path

from deply.code_analyzer import CodeAnalyzer
from deply.collectors.collector_factory import CollectorFactory
from deply.config_parser import ConfigParser
from deply.diagrams.marmaid_diagram_builder import MermaidDiagramBuilder
from deply.models.code_element import CodeElement
from deply.models.layer import Layer
from deply.models.violation import Violation
from deply.reports.report_generator import ReportGenerator
from deply.rules import RuleFactory
from deply.utils.ignore_parser import parse_ignore_comments, ALL_SUPPRESSION_RULES


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
        self.layers: dict[str, Layer] = {}
        self.code_element_to_layer: dict[CodeElement, str] = {}
        self.rules = []
        self.violations: set[Violation] = set()
        self.metrics = {'total_dependencies': 0}
        self.mermaid_builder = MermaidDiagramBuilder()
        self.workers_count = 1
        self.ignore_maps = {}

    def _get_workers_count(self) -> int:
        if self.args.parallel is None:
            return 1

        available_workers = os.cpu_count()

        if self.args.parallel == 0:
            return available_workers
        return min(available_workers, self.args.parallel)

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
        for base_path in self.paths:
            if not base_path.exists():
                continue
            all_python_files = [f for f in base_path.rglob("*.py") if f.is_file()]

            def is_excluded(file_path: Path) -> bool:
                try:
                    relative_path = str(file_path.relative_to(base_path))
                except ValueError:
                    return True
                return any(pattern.search(relative_path) for pattern in self.exclude_files)

            filtered_files = [f for f in all_python_files if not is_excluded(f)]
            self.all_files.extend(filtered_files)

    def collect_code_elements(self):
        logging.info(
            f"Collecting code elements for each layer with {self.workers_count} workers..."
        )
        # Initialize layers
        for layer_config in self.layers_config:
            layer_name = layer_config["name"]
            self.layers[layer_name] = Layer(name=layer_name, code_elements=set(), dependencies=set())

        if self.workers_count > 1:
            with concurrent.futures.ProcessPoolExecutor(max_workers=self.workers_count) as executor:
                futures = [
                    executor.submit(process_file, file_path, self.layer_collectors)
                    for file_path in self.all_files
                ]
                for future in concurrent.futures.as_completed(futures):
                    file_path_str, file_results, ignore_map = future.result()
                    self.ignore_maps[file_path_str] = ignore_map
                    for layer_name, element in file_results:
                        self.layers[layer_name].code_elements.add(element)
                        self.code_element_to_layer[element] = layer_name
        else:
            for file_path in self.all_files:
                file_path_str, file_results, ignore_map = process_file(file_path, self.layer_collectors)
                self.ignore_maps[file_path_str] = ignore_map
                for layer_name, element in file_results:
                    self.layers[layer_name].code_elements.add(element)
                    self.code_element_to_layer[element] = layer_name

        for layer_name, layer in self.layers.items():
            logging.info(
                f"Layer '{layer_name}' collected {len(layer.code_elements)} code elements."
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
            source_layer = self.code_element_to_layer.get(source)
            target_layer = self.code_element_to_layer.get(target)
            self.metrics['total_dependencies'] += 1
            if not source_layer or not target_layer:
                return
            if source_layer == target_layer:
                return
            has_violation = False
            for rule in self.rules:
                violation = rule.check(source_layer, target_layer, dependency)
                if violation and not self.is_violation_suppressed(violation):
                    self.violations.add(violation)
                    has_violation = True
            self.mermaid_builder.add_edge(source_layer, target_layer, has_violation)

        logging.info("Analyzing code and checking dependencies ...")
        analyzer = CodeAnalyzer(
            code_elements=set(self.code_element_to_layer.keys()),
            dependency_handler=dependency_handler
        )
        analyzer.analyze()
        logging.info(
            f"Analysis complete. Found {self.metrics['total_dependencies']} dependencies(s)."
        )

    def run_element_based_checks(self):
        logging.info("Running element-based checks ...")
        for layer_name, layer in self.layers.items():
            for element in layer.code_elements:
                for rule in self.rules:
                    violation_candidate = rule.check_element(layer_name, element)
                    if violation_candidate and not self.is_violation_suppressed(violation_candidate):
                        self.violations.add(violation_candidate)

    def generate_report(self):
        logging.info("Generating report...")
        return ReportGenerator(list(self.violations)).generate(self.args.report_format)

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

    def run(self):
        self.load_configuration()
        self.map_layer_collectors()
        self.collect_all_files()
        self.collect_code_elements()
        self.prepare_rules()
        self.analyze_dependencies()
        self.run_element_based_checks()
        report = self.generate_report()
        self.output_report(report)

        return len(self.violations) <= self.args.max_violations


def process_file(file_path: Path, layer_collectors):
    results = []
    ignore_map = {"file": set(), "lines": {}}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        file_bytes = file_content.encode("utf-8")
        file_ast = ast.parse(file_content, filename=str(file_path))
    except Exception as ex:
        logging.debug(f"Skipping file {file_path} due to parse error: {ex}")
        return (str(file_path), results, ignore_map)

    # Parse ignore directives from the already-read file content
    ignore_map = parse_ignore_comments(file_path, file_bytes=file_bytes)

    for layer_name, collector in layer_collectors:
        matched_elements = collector.match_in_file(file_ast, file_path)
        for element in matched_elements:
            results.append((layer_name, element))
    return (str(file_path), results, ignore_map)
