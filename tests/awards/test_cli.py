import json
from unittest.mock import AsyncMock

import pytest

from procurement_awards_mcp import cli


def test_cli_uses_public_function(
    monkeypatch: pytest.MonkeyPatch, capsysbinary: pytest.CaptureFixture[bytes]
) -> None:
    payload = {"name": "日本語"}
    handler = AsyncMock(return_value=payload)
    monkeypatch.setattr(cli, "search_awards", handler)
    args = ["search-awards", "--fiscal-year", "2025", "--query", "地図", "--limit", "3"]
    cli.run_cli(args)
    handler.assert_awaited_once_with(**{"fiscal_year": 2025, "query": "地図", "limit": 3})
    assert json.loads(capsysbinary.readouterr().out) == payload


def test_summary_cli_passes_repeated_years(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = AsyncMock(return_value={})
    monkeypatch.setattr(cli, "summarize_awards", handler)
    cli.run_cli(
        [
            "summarize-awards",
            "--fiscal-year",
            "2024",
            "--fiscal-year",
            "2025",
            "--ministry-code",
            "L1",
        ]
    )
    handler.assert_awaited_once_with(fiscal_years=[2024, 2025], ministry_code="L1")
