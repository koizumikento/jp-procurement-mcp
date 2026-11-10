import json
import sys
from io import BytesIO
from zipfile import ZipFile

import httpx
import pytest
import respx
from mcp import Client, StdioServerParameters
from mcp.types import TextContent

from procurement_awards_mcp import create_server
from procurement_awards_mcp.client import API_URL, download_archive


@pytest.mark.asyncio
async def test_stdio_tools() -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "procurement_awards_mcp"])
    async with Client(params, mode="legacy", read_timeout_seconds=10) as client:
        result = await client.list_tools()
    assert {tool.name for tool in result.tools} == {"search_awards", "summarize_awards"}
    assert all(tool.annotations and tool.annotations.read_only_hint for tool in result.tools)


@pytest.mark.asyncio
@respx.mock
async def test_daily_archive_filter_and_exact_price() -> None:
    download_archive.cache_clear()
    filename = "successful_bid_record_info_diff_20260115"
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            filename + ".csv",
            (
                '1,"Mapping, update",2026-01-14,12345678901234567.25,'
                "01,0000001,Vendor,1234567890123\r\n"
                "2,Other,2026-01-14,100.00,01,0000001,Vendor,1234567890123\r\n"
            ).encode("utf-8-sig"),
        )
    route = respx.get(API_URL, params={"fileversion": "v001", "filename": filename + ".zip"}).mock(
        return_value=httpx.Response(200, content=buffer.getvalue())
    )
    async with Client(create_server()) as client:
        result = await client.call_tool(
            "search_awards",
            {"published_on": "2026-01-15", "query": "MAPPING", "corporate_number": "1234567890123"},
        )
        invalid = await client.call_tool(
            "search_awards", {"fiscal_year": 2025, "published_on": "2026-01-15"}
        )
    assert route.call_count == 1
    assert not result.is_error
    assert isinstance(result.content[0], TextContent)
    payload = json.loads(result.content[0].text)
    assert payload["total"] == 1
    assert payload["awards"][0]["title"] == "Mapping, update"
    assert payload["awards"][0]["award_price"] == "12345678901234567.25"
    assert invalid.is_error


@pytest.mark.asyncio
@respx.mock
async def test_summary_by_year_and_ministry_excludes_multi_row_prices() -> None:
    download_archive.cache_clear()
    rows = {
        2024: [
            "1,Mapping,2024-05-01,12345678901234567.25,L1,0000001,Vendor,1234567890123",
            "2,Mapping,2024-05-01,0.75,L1,0000001,Vendor,1234567890123",
            "3,Mapping,2024-05-01,100,L1,0000001,Vendor,1234567890123",
            "3,Other title,2024-05-01,500,L1,0000001,Another,1234567890124",
            "4,Mapping,2024-05-01,,L1,0000001,Vendor,1234567890123",
            "1,Mapping,2024-05-01,10,Q1,0000001,Vendor,1234567890123",
        ],
        2025: ["1,Mapping,2025-05-01,NaN,L1,0000001,Vendor,1234567890123"],
    }
    for year, records in rows.items():
        filename = f"successful_bid_record_info_all_{year}"
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr(filename + ".csv", "\r\n".join(records).encode("utf-8-sig"))
        respx.get(API_URL, params={"fileversion": "v001", "filename": filename + ".zip"}).mock(
            return_value=httpx.Response(200, content=buffer.getvalue())
        )

    async with Client(create_server()) as client:
        result = await client.call_tool(
            "summarize_awards", {"fiscal_years": [2025, 2024], "query": "MAPPING"}
        )
        invalid = await client.call_tool("summarize_awards", {"fiscal_years": [2024, 2024]})
        search = await client.call_tool(
            "search_awards", {"fiscal_year": 2024, "ministry_code": "Q1"}
        )
    assert not result.is_error
    assert invalid.is_error
    assert not search.is_error
    assert isinstance(search.content[0], TextContent)
    assert json.loads(search.content[0].text)["total"] == 1
    assert isinstance(result.content[0], TextContent)
    first, second = json.loads(result.content[0].text)["years"]
    assert first["fiscal_year"] == 2024
    assert first["source_file"] == "successful_bid_record_info_all_2024.zip"
    assert first["download_url"].endswith(first["source_file"])
    assert first["ministries"][0] == {
        "ministry_code": "L1",
        "matching_row_count": 4,
        "distinct_case_count": 4,
        "ambiguous_case_count": 1,
        "priced_case_count": 2,
        "unpriced_case_count": 1,
        "single_row_award_price_total": "12345678901234568.00",
    }
    assert first["ministries"][1]["ministry_code"] == "Q1"
    assert second["fiscal_year"] == 2025
    assert second["ministries"][0]["single_row_award_price_total"] is None
