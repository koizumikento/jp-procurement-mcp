import httpx
import pytest
import respx

from procurement_notices_mcp import search_notices
from procurement_notices_mcp.client import API_URL


@pytest.mark.asyncio
@respx.mock
async def test_query_filter_and_publication_date() -> None:
    route = respx.get(API_URL).mock(
        return_value=httpx.Response(
            200,
            text="""
        <Results><SearchResults><SearchHits>5</SearchHits><SearchResult>
        <ProjectName>防災設備</ProjectName><CftIssueDate>2026-01-01</CftIssueDate>
        <ExternalDocumentURI>https://example.org/notice</ExternalDocumentURI>
        </SearchResult></SearchResults></Results>""",
        )
    )
    result = await search_notices("防災", prefecture_code="13", limit=1)
    assert dict(route.calls[0].request.url.params) == {
        "Query": "防災",
        "LG_Code": "13",
        "Count": "1",
    }
    assert result["total"] == 5
    assert result["items"][0]["published_at"] == "2026-01-01"
    assert "body" not in result["items"][0]
    assert "attachments" not in result["items"][0]


@pytest.mark.asyncio
@respx.mock
async def test_search_filters_and_bounded_details() -> None:
    attachments = (
        "<Attachment><Name>仕様書</Name><Uri>https://example.org/spec</Uri></Attachment>" * 11
    )
    route = respx.get(API_URL).mock(
        return_value=httpx.Response(
            200,
            text=f"""
        <Results><SearchResults><SearchHits>1</SearchHits><SearchResult>
        <Key>example-id</Key><Date>2026-04-01T09:00:00+09:00</Date>
        <TenderSubmissionDeadline>2026-04-01</TenderSubmissionDeadline>
        <ProjectDescription>{"あ" * 2001}</ProjectDescription>
        <Attachments>{attachments}</Attachments>
        </SearchResult></SearchResults></Results>""",
        )
    )
    result = await search_notices(
        project_name="設備",
        organization_name="法務省",
        category=3,
        procedure_type=1,
        qualification=["A", "C"],
        issue_period="2026-04-01/2026-04-30",
        tender_start_period="2026-04-01/",
        opening_period="/2026-04-30",
        delivery_deadline_period="2026-04-30",
        include_details=True,
    )
    assert dict(route.calls[0].request.url.params) == {
        "Count": "10",
        "Project_Name": "設備",
        "Organization_Name": "法務省",
        "Category": "3",
        "Procedure_Type": "1",
        "Certification": "A,C",
        "CFT_Issue_Date": "2026-04-01/2026-04-30",
        "Tender_Submission_Deadline": "2026-04-01/",
        "Opening_Tenders_Event": "/2026-04-30",
        "Period_End_Time": "2026-04-30",
    }
    notice = result["items"][0]
    assert notice["notice_id"] == "example-id"
    assert notice["collected_at"] == "2026-04-01T09:00:00+09:00"
    assert notice["tender_start_at"] == "2026-04-01"
    assert notice["body"] == "あ" * 2000
    assert notice["body_truncated"]
    assert len(notice["attachments"]) == 10
    assert notice["attachments"][0] == {"name": "仕様書", "url": "https://example.org/spec"}
    assert notice["attachments_truncated"]


@pytest.mark.asyncio
async def test_invalid_search_filters() -> None:
    with pytest.raises(ValueError, match="Specify a query"):
        await search_notices(category=1)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        await search_notices("防災", issue_period="2026-04-30/2026-04-01")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        await search_notices("防災", opening_period="2026-02-30")
