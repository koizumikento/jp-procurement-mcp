import subprocess
import sys

import pytest
from mcp import Client, StdioServerParameters

from jp_procurement_mcp import create_server
from jp_procurement_mcp.cli import run_cli
from procurement_awards_mcp import cli as awards_cli
from procurement_awards_mcp.server import create_server as awards_server
from procurement_notices_mcp import cli as notices_cli
from procurement_notices_mcp.server import create_server as notices_server


@pytest.mark.asyncio
async def test_combined_tools_preserve_source_schemas() -> None:
    expected = []
    for factory in (
        notices_server,
        awards_server,
    ):
        expected.extend(await factory().list_tools())
    actual = await create_server().list_tools()
    assert len(actual) == 3
    assert len({tool.name for tool in actual}) == len(actual)
    assert {tool.name: tool.model_dump(exclude_none=True) for tool in actual} == {
        tool.name: tool.model_dump(exclude_none=True) for tool in expected
    }


@pytest.mark.asyncio
async def test_combined_stdio_lists_all_tools() -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "jp_procurement_mcp"])
    async with Client(params, mode="legacy", read_timeout_seconds=10) as client:
        result = await client.list_tools()
    assert len(result.tools) == 3
    assert all(tool.annotations and tool.annotations.read_only_hint for tool in result.tools)


@pytest.mark.parametrize("group, module", [("notices", notices_cli), ("awards", awards_cli)])
def test_cli_dispatches_without_changing_arguments(monkeypatch, group, module) -> None:
    calls = []
    monkeypatch.setattr(module, "run_cli", lambda args: calls.append(list(args)))
    from jp_procurement_mcp import cli

    monkeypatch.setattr(cli, group.replace("-", "_") + "_cli", module.run_cli)
    run_cli([group, "query", "--limit", "2"])
    assert calls == [["query", "--limit", "2"]]


def test_command_help() -> None:
    for group in ["notices", "awards"]:
        result = subprocess.run(
            [sys.executable, "-m", "jp_procurement_mcp", group, "--help"],
            capture_output=True,
            check=True,
        )
        assert b"usage:" in result.stdout
