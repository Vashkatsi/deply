import argparse
import ast
import concurrent.futures
import logging
import re
import sys
from pathlib import Path

from deply import __version__
from deply.diagrams.marmaid_diagram_builder import MermaidDiagramBuilder
from deply.reports.report_generator import ReportGenerator
from deply.rules.rule_factory import RuleFactory
from .code_analyzer import CodeAnalyzer
from .collectors.collector_factory import CollectorFactory
from .config_parser import ConfigParser
from .models.code_element import CodeElement
from .models.layer import Layer
from .models.violation import Violation


def process_file(file_path: Path, layer_collectors):
    results = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        file_ast = ast.parse(file_content, filename=str(file_path))
    except Exception as ex:
        logging.debug(f"Skipping file {file_path} due to parse error: {ex}")
        return results
    for layer_name, collector in layer_collectors:
        matched_elements = collector.match_in_file(file_ast, file_path)
        for element in matched_elements:
            results.append((layer_name, element))
    return results


def main():
    parser = argparse.ArgumentParser(prog="deply", description='Deply - An architecture analysis tool')
    parser.add_argument('-V', '--version', action='store_true', help='Show the version number and exit')
    parser.add_argument('-v', '--verbose', action='count', default=1, help='Increase output verbosity')

    subparsers = parser.add_subparsers(dest='command', help='Sub-commands')
    parser_analyze = subparsers.add_parser('analyze', help='Analyze the project')
    parser_analyze.add_argument('--config', type=str, default="deply.yaml", help="Path to the configuration YAML file")
    parser_analyze.add_argument(
        '--report-format',
        type=str,
        choices=["text", "json", "github-actions"],
        default="text",
        help="Format of the output report"
    )
    parser_analyze.add_argument('--output', type=str, help="Output file for the report")
    parser_analyze.add_argument('--mermaid', action='store_true',
                                help="Generate a Mermaid diagram for layer dependencies (red = violation)")
    parser_analyze.add_argument(
        '--max-violations',
        type=int,
        default=0,
        help="Maximum number of allowed violations before failing"
    )

    args = parser.parse_args()

    if args.version:
        version = __version__
        print(f"deply {version}")
        sys.exit(0)

    # Set up logging
    log_level = logging.WARNING
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose >= 2:
        log_level = logging.DEBUG

    logging.basicConfig(
        level=log_level,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    if args.command is None:
        args = parser.parse_args(['analyze'] + sys.argv[1:])

    logging.info("Starting Deply analysis...")

    config_path = Path(args.config)
    logging.info(f"Using configuration file: {config_path}")
    config = ConfigParser(config_path).parse()

    paths = [Path(p) for p in config["paths"]]
    exclude_files = [re.compile(pattern) for pattern in config["exclude_files"]]
    layers_config = config["layers"]
    ruleset = config["ruleset"]

    logging.info("Mapping layer collectors...")
    layer_collectors = []
    for layer_config in layers_config:
        layer_name = layer_config["name"]
        collector_configs = layer_config.get("collectors", [])
        for collector_config in collector_configs:
            collector = CollectorFactory.create(
                config=collector_config,
                paths=[str(p) for p in paths],
                exclude_files=[p.pattern for p in exclude_files]
            )
            layer_collectors.append((layer_name, collector))

    logging.info("Collecting all files...")
    all_files = []
    for base_path in paths:
        if not base_path.exists():
            continue
        all_python_files = [f for f in base_path.rglob("*.py") if f.is_file()]

        def is_excluded(file_path: Path) -> bool:
            try:
                relative_path = str(file_path.relative_to(base_path))
            except ValueError:
                return True
            return any(pattern.search(relative_path) for pattern in exclude_files)

        filtered_files = [f for f in all_python_files if not is_excluded(f)]
        all_files.extend(filtered_files)

    layers: dict[str, Layer] = {}
    for layer_config in layers_config:
        layer_name = layer_config["name"]
        layers[layer_name] = Layer(name=layer_name, code_elements=set(), dependencies=set())

    code_element_to_layer: dict[CodeElement, str] = {}
    logging.info("Collecting code elements for each layer (parallel)...")

    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(process_file, file_path, layer_collectors) for file_path in all_files]
        for future in concurrent.futures.as_completed(futures):
            file_results = future.result()
            for layer_name, element in file_results:
                layers[layer_name].code_elements.add(element)
                code_element_to_layer[element] = layer_name

    for layer_name, layer in layers.items():
        logging.info(f"Layer '{layer_name}' collected {len(layer.code_elements)} code elements.")

    logging.info("Preparing rules...")
    rules = RuleFactory.create_rules(ruleset)

    violations: set[Violation] = set()
    metrics = {'total_dependencies': 0}

    mermaid_builder = MermaidDiagramBuilder()

    def dependency_handler(dependency):
        source = dependency.code_element
        target = dependency.depends_on_code_element
        source_layer = code_element_to_layer.get(source)
        target_layer = code_element_to_layer.get(target)
        metrics['total_dependencies'] += 1

        if not source_layer or not target_layer:
            return
        if source_layer == target_layer:
            # Intra-layer dependency, not relevant for cross-layer analysis
            return

        # Check if there's a violation for this dependency
        has_violation = False
        for rule in rules:
            violation = rule.check(source_layer, target_layer, dependency)
            if violation:
                violations.add(violation)
                has_violation = True

        # Pass edge info to mermaid builder
        mermaid_builder.add_edge(source_layer, target_layer, has_violation)

    logging.info("Analyzing code and checking dependencies ...")
    analyzer = CodeAnalyzer(
        code_elements=set(code_element_to_layer.keys()),
        dependency_handler=dependency_handler
    )
    analyzer.analyze()

    logging.info(f"Analysis complete. Found {metrics['total_dependencies']} dependencies(s).")

    logging.info("Running element-based checks ...")
    for layer_name, layer in layers.items():
        for element in layer.code_elements:
            for rule in rules:
                v = rule.check_element(layer_name, element)
                if v:
                    violations.add(v)

    logging.info("Generating report...")
    report = ReportGenerator(list(violations)).generate(args.report_format)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(report)
        logging.info(f"Report written to {output_path}")
    else:
        print("\n")
        print(report)

    if args.mermaid:
        mermaid_diagram = mermaid_builder.build_diagram()
        print("\n[Mermaid Diagram of Layer Dependencies]\n")
        print(mermaid_diagram)

    if len(violations) <= args.max_violations:
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    main()