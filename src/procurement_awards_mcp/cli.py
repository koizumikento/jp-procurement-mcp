import asyncio
import json
import sys
from argparse import SUPPRESS, ArgumentParser
from collections.abc import Sequence
from datetime import date

import httpx

from .client import search_awards, summarize_awards


def run_cli(argv: Sequence[str]) -> None:
    parser = ArgumentParser(prog="procurement-awards-mcp")
    commands = parser.add_subparsers(required=True)

    command = commands.add_parser(
        "search-awards",
        help="Search an annual snapshot or daily award delta.",
        argument_default=SUPPRESS,
    )
    partition = command.add_mutually_exclusive_group(required=True)
    partition.add_argument("--fiscal-year", type=int)
    partition.add_argument("--published-on", type=date.fromisoformat)
    command.add_argument("--query")
    command.add_argument("--ministry-code")
    command.add_argument("--corporate-number")
    command.add_argument("--limit", type=int)
    command.add_argument("--offset", type=int)
    command.set_defaults(handler=search_awards)

    summary = commands.add_parser(
        "summarize-awards",
        help="Compare up to three annual award snapshots by ministry.",
        argument_default=SUPPRESS,
    )
    summary.add_argument(
        "--fiscal-year", dest="fiscal_years", action="append", type=int, required=True
    )
    summary.add_argument("--query")
    summary.add_argument("--ministry-code")
    summary.set_defaults(handler=summarize_awards)

    arguments = vars(parser.parse_args(argv))
    handler = arguments.pop("handler")
    try:
        result = asyncio.run(handler(**arguments))
        payload = result
    except (ValueError, OSError, httpx.HTTPError) as exc:
        parser.exit(1, f"{parser.prog}: {exc}\n")
    sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
