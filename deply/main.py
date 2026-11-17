import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

import yaml
from deply import __version__
from deply.config_parser import ConfigParser, discover_config_path
from deply.config_validator import ConfigValidator
from deply.deply_runner import DeplyRunner
from deply.presets import available_presets, dump_configuration, render_preset
from deply.reports.report_generator import ReportGenerator

CONFIG_HELP = "Path to the configuration file; defaults to deply.yaml, then pyproject.toml [tool.deply]"


def validate_configuration(
        config_path: str, report_success: bool = True,
        report_format: str = "text", output: Optional[str] = None,
) -> bool:
    configuration_path = Path(config_path)
    try:
        config = ConfigParser(configuration_path).parse()
        errors = ConfigValidator(configuration_path).validate(config)
    except (OSError, ValueError, yaml.YAMLError) as exception:
        errors = [str(exception)]

    if not errors:
        if report_success:
            print(f"Configuration is valid: {configuration_path}")
        return True

    if report_format == "json":
        report = ReportGenerator(
            [], status="invalid_configuration",
            errors=[{"code": "invalid_configuration", "message": error} for error in errors],
        ).generate("json")
        if output:
            Path(output).write_text(report)
        else:
            print(report)
    print("Invalid deply configuration:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    return False


def initialize_configuration(preset: str, output: str, paths: List[str], force: bool) -> bool:
    output_path = Path(output)
    config = render_preset(preset, paths)
    errors = ConfigValidator(output_path).validate(config["deply"])
    if errors:
        print("Invalid deply configuration:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return False

    content = dump_configuration(config)
    try:
        with output_path.open("w" if force else "x") as output_file:
            output_file.write(content)
    except FileExistsError:
        print(f"{output_path} already exists; use --force to overwrite it", file=sys.stderr)
        return False
    except OSError as exception:
        print(f"Cannot write {output_path}: {exception}", file=sys.stderr)
        return False

    print(f"Created {output_path} from preset '{preset}'")
    return True


def main():
    # pragma: no mutate start
    parser = argparse.ArgumentParser(prog="deply", description='Deply - An architecture analysis tool')
    parser.add_argument('-V', '--version', action='store_true', help='Show the version number and exit')
    parser.add_argument('-v', '--verbose', action='count', default=1, help='Increase output verbosity')
    subparsers = parser.add_subparsers(dest='command', help='Sub-commands')
    parser_analyze = subparsers.add_parser('analyze', help='Analyze the project')
    parser_analyze.add_argument('--config', type=str, default=None, help=CONFIG_HELP)
    parser_analyze.add_argument(
        '--report-format',
        type=str,
        choices=["text", "json", "github-actions", "sarif"],
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

    baseline_options = parser_analyze.add_mutually_exclusive_group()
    baseline_options.add_argument("--baseline", type=Path, help="Compare against an accepted violation baseline")
    baseline_options.add_argument("--write-baseline", type=Path, help="Create a new baseline after complete analysis")

    parser_analyze.add_argument(
        '--parallel',
        type=int,
        nargs='?',
        default=None,
        const=0,
        help="Enable parallel processing of code elements. "
             "Optionally specify the number of processes to use. "
             "If no number is provided, all available CPU cores will be used."
    )
    parser_validate = subparsers.add_parser('validate', help='Validate the configuration file')
    parser_validate.add_argument('--config', type=str, default=None, help=CONFIG_HELP)
    parser_context = subparsers.add_parser('context', help='Show architecture context for one Python file')
    parser_context.add_argument('--file', dest='context_file', type=Path, required=True, help='Python file to inspect')
    parser_context.add_argument('--config', default=None, help=CONFIG_HELP)
    parser_context.add_argument('--report-format', choices=['json'], default='json', help='Format of the context report')
    parser_context.set_defaults(parallel=None, output=None, mermaid=False, baseline=None, write_baseline=None,
                                max_violations=0)
    parser_init = subparsers.add_parser('init', help='Write a starter configuration file from a packaged preset')
    init_selection = parser_init.add_mutually_exclusive_group(required=True)
    init_selection.add_argument('--preset', choices=available_presets(), help='Preset to write')
    init_selection.add_argument('--list-presets', action='store_true', help='List available presets and exit')
    parser_init.add_argument('--output', default='deply.yaml', help='Configuration file to create')
    parser_init.add_argument('--paths', nargs='+', default=['.'], help='Analysis paths written to the configuration')
    parser_init.add_argument('--force', action='store_true', help='Overwrite an existing configuration file')
    # pragma: no mutate end

    args = parser.parse_args()

    if args.version:
        print(f"deply {__version__}")
        sys.exit(0)

    if args.command is None:
        args = parser.parse_args(['analyze'] + sys.argv[1:])  # pragma: no mutate

    if args.config is None:
        args.config = str(discover_config_path(Path()))

    log_level = logging.WARNING
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose >= 2:
        log_level = logging.DEBUG

    logging.basicConfig(
        level=log_level,
        format='[%(asctime)s] [%(levelname)s] %(message)s',  # pragma: no mutate
        datefmt='%Y-%m-%d %H:%M:%S'  # pragma: no mutate
    )

    if args.command == "init":
        if args.list_presets:
            print("\n".join(available_presets()))
            sys.exit(0)
        sys.exit(0 if initialize_configuration(args.preset, args.output, args.paths, args.force) else 1)

    if args.command == "validate":
        sys.exit(0 if validate_configuration(args.config) else 1)

    if args.baseline or args.write_baseline:
        if args.write_baseline and args.output:
            parser.error("--output cannot be combined with --write-baseline")
        if args.max_violations != 0:
            parser.error("baseline options cannot be combined with nonzero --max-violations")
        protected_paths = [Path(args.config), Path(args.baseline or args.write_baseline)]
        if args.output and any(
            Path(args.output).resolve() == path.resolve()
            or (Path(args.output).exists() and path.exists() and Path(args.output).samefile(path))
            for path in protected_paths
        ):
            parser.error("--output must differ from the configuration and baseline paths")

    if not validate_configuration(args.config, report_success=False,
                                  report_format=args.report_format, output=args.output):
        sys.exit(1)

    logging.getLogger(__name__).info("Starting Deply analysis...")  # pragma: no mutate
    runner = DeplyRunner(args)
    if runner.run():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
