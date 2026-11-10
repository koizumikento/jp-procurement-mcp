from asyncio import to_thread
from collections.abc import Iterator
from csv import reader
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from io import BytesIO, TextIOWrapper
from re import fullmatch
from time import time
from typing import Annotated, Any
from zipfile import BadZipFile, ZipFile

import httpx
from pydantic import Field, validate_call

API_URL = "https://api.p-portal.go.jp/pps-web-biz/UAB03/OAB0301"
SOURCE_URL = "https://www.p-portal.go.jp/pps-web-biz/UAB02/OAB0201"
MAX_ARCHIVE_SIZE = 16 * 1024 * 1024
MAX_CSV_SIZE = 64 * 1024 * 1024
FiscalYear = Annotated[int, Field(ge=2013, le=9999)]
MinistryCode = Annotated[str, Field(pattern=r"^[A-Z0-9]{2}$")]
Query = Annotated[str, Field(max_length=200)]
FIELDS = (
    "case_number",
    "title",
    "award_date",
    "award_price",
    "ministry_code",
    "method_code",
    "supplier_name",
    "corporate_number",
)


@lru_cache(maxsize=2)
def download_archive(filename: str, time_bucket: int) -> bytes:
    with httpx.stream(
        "GET", API_URL, params={"fileversion": "v001", "filename": filename}, timeout=25.0
    ) as response:
        if response.status_code in {400, 404}:
            raise ValueError("The procurement portal does not have this snapshot.")
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_bytes(64 * 1024):
            if len(data) + len(chunk) > MAX_ARCHIVE_SIZE:
                raise ValueError("The procurement ZIP exceeds the supported size.")
            data.extend(chunk)
    return bytes(data)


def _snapshot_records(filename: str) -> Iterator[dict[str, str]]:
    archive_bytes = download_archive(filename, int(time()) // 1800)
    try:
        with ZipFile(BytesIO(archive_bytes)) as archive:
            member = archive.getinfo(filename.removesuffix(".zip") + ".csv")
            if member.file_size > MAX_CSV_SIZE:
                raise ValueError("The procurement CSV exceeds the supported size.")
            with TextIOWrapper(archive.open(member), encoding="utf-8-sig", newline="") as source:
                for row in reader(source, strict=True):
                    yield dict(zip(FIELDS, row, strict=True))
    except (BadZipFile, KeyError) as exc:
        raise ValueError("The procurement portal returned an unexpected archive.") from exc


def search_snapshot(
    filename: str,
    query: str,
    ministry_code: str | None,
    corporate_number: str | None,
    limit: int,
    offset: int,
) -> tuple[int, list[dict[str, str]]]:
    total = 0
    results = []
    for record in _snapshot_records(filename):
        if (
            query not in record["title"].casefold()
            or (ministry_code is not None and ministry_code != record["ministry_code"])
            or (corporate_number is not None and corporate_number != record["corporate_number"])
        ):
            continue
        if offset <= total < offset + limit:
            results.append(record)
        total += 1
    return total, results


def _source_file(filename: str) -> dict[str, str]:
    return {
        "source_file": filename,
        "download_url": f"{API_URL}?fileversion=v001&filename={filename}",
    }


@validate_call
async def search_awards(
    fiscal_year: FiscalYear | None = None,
    published_on: date | None = None,
    query: Query = "",
    ministry_code: MinistryCode | None = None,
    corporate_number: Annotated[str, Field(pattern=r"^[0-9]{13}$")] | None = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 10,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> dict[str, int | str | list[dict[str, str]]]:
    """Search award titles in one fiscal-year snapshot or one publication-day delta."""
    if (fiscal_year is None) == (published_on is None):
        raise ValueError("Specify exactly one of fiscal_year or published_on.")
    partition = f"all_{fiscal_year}" if published_on is None else f"diff_{published_on:%Y%m%d}"
    filename = f"successful_bid_record_info_{partition}.zip"
    total, awards = await to_thread(
        search_snapshot,
        filename,
        query.strip().casefold(),
        ministry_code,
        corporate_number,
        limit,
        offset,
    )
    return {
        "total": total,
        "offset": offset,
        "awards": awards,
        "source": "Japan Procurement Portal award records",
        "source_url": SOURCE_URL,
        **_source_file(filename),
    }


@dataclass
class _Case:
    first_price: str
    rows: int = 0
    matching_rows: int = 0


def _price(raw: str) -> Decimal | None:
    return Decimal(raw) if fullmatch(r"-?[0-9]{1,17}(\.[0-9]{1,2})?", raw) else None


def _summarize_snapshot(year: int, query: str, ministry_code: str | None) -> dict[str, Any]:
    filename = f"successful_bid_record_info_all_{year}.zip"
    ministries: dict[str, dict[str, _Case]] = {}
    for record in _snapshot_records(filename):
        code = record["ministry_code"]
        if ministry_code is not None and code != ministry_code:
            continue
        cases = ministries.setdefault(code, {})
        case = cases.get(record["case_number"])
        if case is None:
            case = cases[record["case_number"]] = _Case(record["award_price"])
        case.rows += 1
        if query in record["title"].casefold():
            case.matching_rows += 1

    groups = []
    for code, cases in sorted(ministries.items()):
        matching = [case for case in cases.values() if case.matching_rows]
        if not matching:
            continue
        ambiguous = sum(case.rows > 1 for case in matching)
        prices = [
            price
            for case in matching
            if case.rows == 1 and (price := _price(case.first_price)) is not None
        ]
        groups.append(
            {
                "ministry_code": code,
                "matching_row_count": sum(case.matching_rows for case in matching),
                "distinct_case_count": len(matching),
                "ambiguous_case_count": ambiguous,
                "priced_case_count": len(prices),
                "unpriced_case_count": len(matching) - ambiguous - len(prices),
                "single_row_award_price_total": format(sum(prices), "f") if prices else None,
            }
        )
    return {"fiscal_year": year, **_source_file(filename), "ministries": groups}


@validate_call
async def summarize_awards(
    fiscal_years: Annotated[list[FiscalYear], Field(min_length=1, max_length=3)],
    query: Query = "",
    ministry_code: MinistryCode | None = None,
) -> dict[str, Any]:
    """Compare annual award snapshots by ministry for up to three distinct fiscal years.

    Prices are summed only for case numbers with one source row and a usable price.
    """
    if len(set(fiscal_years)) != len(fiscal_years):
        raise ValueError("Specify distinct fiscal years.")
    years = []
    for year in sorted(fiscal_years):
        years.append(
            await to_thread(_summarize_snapshot, year, query.strip().casefold(), ministry_code)
        )
    return {
        "source": "Japan Procurement Portal award records",
        "source_url": SOURCE_URL,
        "years": years,
    }
