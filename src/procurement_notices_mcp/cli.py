import asyncio
import json
import sys
from argparse import SUPPRESS, ArgumentParser
from collections.abc import Sequence

import httpx

from .client import search_notices


def run_cli(argv: Sequence[str]) -> None:
    parser = ArgumentParser(prog="procurement-notices-mcp")
    commands = parser.add_subparsers(required=True)

    command = commands.add_parser("search-notices", argument_default=SUPPRESS)
    command.add_argument("--query")
    command.add_argument("--project-name")
    command.add_argument("--organization-name")
    command.add_argument("--prefecture-code")
    command.add_argument("--category", type=int, choices=(1, 2, 3))
    command.add_argument("--procedure-type", type=int, choices=(1, 2, 3))
    command.add_argument("--qualification", action="append", choices=("A", "B", "C", "D"))
    command.add_argument("--issue-period")
    command.add_argument("--tender-start-period")
    command.add_argument("--opening-period")
    command.add_argument("--delivery-deadline-period")
    command.add_argument("--include-details", action="store_true")
    command.add_argument("--limit", type=int)
    command.set_defaults(handler=search_notices)

    arguments = vars(parser.parse_args(argv))
    handler = arguments.pop("handler")
    try:
        result = asyncio.run(handler(**arguments))
    except (ValueError, OSError, httpx.HTTPError) as exc:
        parser.exit(1, f"{parser.prog}: {exc}\n")
    sys.stdout.buffer.write((json.dumps(result, ensure_ascii=False) + "\n").encode("utf-8"))
