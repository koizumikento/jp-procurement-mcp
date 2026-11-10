from datetime import date
from typing import Annotated, Any, Literal
from xml.etree import ElementTree

import httpx
from pydantic import Field, validate_call

API_URL = "https://www.kkj.go.jp/api/"
Query = Annotated[str, Field(min_length=1, max_length=200, pattern=r"\S")]
Prefecture = Annotated[str, Field(pattern=r"^(0[1-9]|[1-3][0-9]|4[0-7])$")]
Limit = Annotated[int, Field(ge=1, le=50)]
Period = Annotated[str, Field(min_length=10, max_length=21)]
Code = Literal[1, 2, 3]
Qualifications = Annotated[list[Literal["A", "B", "C", "D"]], Field(min_length=1, max_length=4)]
MAX_BODY_CHARS = 2_000
MAX_ATTACHMENTS = 10


def _check_period(period: str) -> None:
    dates = []
    try:
        for value in period.split("/"):
            if value:
                parsed = date.fromisoformat(value)
                if parsed.isoformat() != value:
                    raise ValueError
                dates.append(parsed)
        if not dates or period.count("/") > 1 or dates != sorted(dates):
            raise ValueError
    except ValueError:
        raise ValueError("Use YYYY-MM-DD or an inclusive start/end date range.") from None


def _notice(row: ElementTree.Element, include_details: bool) -> dict[str, Any]:
    fields = {
        "title": "ProjectName",
        "organization": "OrganizationName",
        "prefecture": "PrefectureName",
        "category": "Category",
        "published_at": "CftIssueDate",
        "source_url": "ExternalDocumentURI",
        "result_id": "ResultId",
        "notice_id": "Key",
        "collected_at": "Date",
        "prefecture_code": "LgCode",
        "city_code": "CityCode",
        "city": "CityName",
        "procedure_type": "ProcedureType",
        "qualification": "Certification",
        "tender_start_at": "TenderSubmissionDeadline",
        "opening_at": "OpeningTendersEvent",
        "delivery_deadline": "PeriodEndTime",
        "location": "Location",
        "file_type": "FileType",
        "file_size": "FileSize",
        "item_code": "ItemCode",
    }
    result: dict[str, Any] = {key: row.findtext(tag) for key, tag in fields.items()}
    if include_details:
        body = row.findtext("ProjectDescription")
        attachments = row.findall("Attachments/Attachment")
        result.update(
            body=body[:MAX_BODY_CHARS] if body is not None else None,
            body_truncated=body is not None and len(body) > MAX_BODY_CHARS,
            attachments=[
                {"name": item.findtext("Name"), "url": item.findtext("Uri")}
                for item in attachments[:MAX_ATTACHMENTS]
            ],
            attachments_truncated=len(attachments) > MAX_ATTACHMENTS,
        )
    return result


@validate_call
async def search_notices(
    query: Query | None = None,
    prefecture_code: Prefecture | None = None,
    limit: Limit = 10,
    *,
    project_name: Query | None = None,
    organization_name: Query | None = None,
    category: Code | None = None,
    procedure_type: Code | None = None,
    qualification: Qualifications | None = None,
    issue_period: Period | None = None,
    tender_start_period: Period | None = None,
    opening_period: Period | None = None,
    delivery_deadline_period: Period | None = None,
    include_details: bool = False,
) -> dict[str, Any]:
    """Search KKJ notices by keyword, project name, organization or prefecture.

    Optional date filters accept YYYY-MM-DD, start/end, start/ or /end.
    Set include_details to return a bounded body excerpt and attachment links.
    """
    if not any((query, project_name, organization_name, prefecture_code)):
        raise ValueError("Specify a query, project_name, organization_name or prefecture_code.")
    periods = {
        "CFT_Issue_Date": issue_period,
        "Tender_Submission_Deadline": tender_start_period,
        "Opening_Tenders_Event": opening_period,
        "Period_End_Time": delivery_deadline_period,
    }
    for period in periods.values():
        if period is not None:
            _check_period(period)
    filters = {
        "Query": query,
        "Project_Name": project_name,
        "Organization_Name": organization_name,
        "LG_Code": prefecture_code,
        "Category": category,
        "Procedure_Type": procedure_type,
        "Certification": ",".join(qualification) if qualification is not None else None,
        **periods,
    }
    params: dict[str, str | int] = {"Count": limit}
    params.update({key: value for key, value in filters.items() if value is not None})
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(API_URL, params=params)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"KKJ returned HTTP {exc.response.status_code}.") from None
    except httpx.RequestError:
        raise ValueError("Could not reach the procurement notices API.") from None

    try:
        xml = response.content.decode("utf-8-sig")
        if "<!DOCTYPE" in xml:
            raise ValueError
        root = ElementTree.fromstring(xml)
    except (ValueError, ElementTree.ParseError):
        raise ValueError("KKJ returned an unexpected XML response.") from None
    if root.find("Error") is not None:
        raise ValueError("KKJ rejected the search or is temporarily busy.")
    try:
        total = int(root.findtext("SearchResults/SearchHits", "-1"))
    except ValueError:
        raise ValueError("KKJ returned an unexpected XML response.") from None
    rows = root.findall("SearchResults/SearchResult")
    if total < len(rows) or len(rows) > limit:
        raise ValueError("KKJ returned an unexpected XML response.")
    return {
        "total": total,
        "source_url": "https://www.kkj.go.jp/s/",
        "items": [_notice(row, include_details) for row in rows],
    }
