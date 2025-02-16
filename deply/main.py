import argparse
import logging
import sys

from deply import __version__
from deply.deply_runner import DeplyRunner


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

    args = parser.parse_args()

    if args.version:
        print(f"deply {__version__}")
        sys.exit(0)

    if args.command is None:
        args = parser.parse_args(['analyze'] + sys.argv[1:])

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

    logging.info("Starting Deply analysis...")
    runner = DeplyRunner(args)
    if runner.run():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
