import argparse
import logging
import sys
from pathlib import Path

import yaml
from deply import __version__
from deply.config_parser import ConfigParser
from deply.config_validator import ConfigValidator
from deply.deply_runner import DeplyRunner


def validate_configuration(config_path: str) -> bool:
    configuration_path = Path(config_path)
    try:
        config = ConfigParser(configuration_path).parse()
        errors = ConfigValidator(configuration_path).validate(config)
    except (OSError, ValueError, yaml.YAMLError) as exception:
        errors = [str(exception)]

    if not errors:
        print(f"Configuration is valid: {configuration_path}")
        return True

    print("Invalid deply configuration:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    return False


def main():
    # pragma: no mutate start
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
    parser_validate.add_argument('--config', type=str, default="deply.yaml", help="Path to the configuration YAML file")
    # pragma: no mutate end

    args = parser.parse_args()

    if args.version:
        print(f"deply {__version__}")
        sys.exit(0)

    if args.command is None:
        args = parser.parse_args(['analyze'] + sys.argv[1:])  # pragma: no mutate

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

    if args.command == "validate":
        sys.exit(0 if validate_configuration(args.config) else 1)

    logging.getLogger(__name__).info("Starting Deply analysis...")  # pragma: no mutate
    runner = DeplyRunner(args)
    if runner.run():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
