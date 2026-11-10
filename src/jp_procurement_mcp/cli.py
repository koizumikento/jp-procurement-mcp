from argparse import ArgumentParser
from collections.abc import Sequence

from procurement_awards_mcp.cli import run_cli as awards_cli
from procurement_notices_mcp.cli import run_cli as notices_cli


def run_cli(argv: Sequence[str]) -> None:
    parser = ArgumentParser(prog="jp-procurement-mcp")
    commands = parser.add_subparsers(required=True)
    commands.add_parser("notices", help="調達公告", add_help=False).set_defaults(
        handler=notices_cli
    )
    commands.add_parser("awards", help="落札実績", add_help=False).set_defaults(handler=awards_cli)
    arguments, remaining = parser.parse_known_args(argv)
    arguments.handler(remaining)
