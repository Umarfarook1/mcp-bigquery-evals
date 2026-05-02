"""End-to-end smoke: build the server and exercise each tool against the fake fixture.

This bypasses the stdio transport and calls handlers directly via build_server().
A separate stdio-protocol test is deferred to Plan B's CI integration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mcp_bigquery_evals.server import build_server

FIXTURE = Path(__file__).parent.parent / "fixtures" / "fake_warehouse.yaml"

EXPECTED_TOOLS = {
    "list_datasets",
    "list_tables",
    "describe_table",
    "sample_table",
    "search_schema",
    "estimate_cost",
    "run_query",
}


@pytest.fixture(autouse=True)
def use_fake_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_BIGQUERY_FAKE_FIXTURE", str(FIXTURE))


def _parse_result(result: Any) -> Any:
    """Return the parsed payload from a call_tool response.

    FastMCP returns a tuple (unstructured: list[TextContent], structured: dict)
    when structured output is in use, or just list[TextContent] for tools that
    have no output schema.  We prefer the structured half when available, and
    fall back to JSON-decoding the concatenated text blocks otherwise.
    """
    # Tuple form: (list[ContentBlock], dict) - structured output
    if isinstance(result, tuple) and len(result) == 2:
        _content_blocks, structured = result
        return structured

    # Plain sequence of ContentBlock - unstructured only
    texts = [block.text for block in result if hasattr(block, "text")]
    text = "".join(texts)
    return json.loads(text) if text else result


@pytest.mark.asyncio
async def test_seven_tools_registered() -> None:
    """All 7 tool names must be present in list_tools."""
    server = build_server()
    tools = await server.list_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == EXPECTED_TOOLS


def _unwrap_list(payload: Any) -> list[Any]:
    """Structured output wraps list-returning tools in {'result': [...]}.
    Unwrap that layer; plain lists pass through unchanged.
    """
    if isinstance(payload, dict) and "result" in payload:
        return payload["result"]  # type: ignore[return-value]
    return payload  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_list_datasets() -> None:
    server = build_server()
    result = await server.call_tool("list_datasets", {})
    payload = _unwrap_list(_parse_result(result))
    # Should be a list with at least the 'analytics' and 'ops' datasets
    assert isinstance(payload, list)
    ids = {d["id"] for d in payload}
    assert "analytics" in ids
    assert "ops" in ids


@pytest.mark.asyncio
async def test_list_tables() -> None:
    server = build_server()
    result = await server.call_tool("list_tables", {"dataset_id": "analytics"})
    payload = _unwrap_list(_parse_result(result))
    assert isinstance(payload, list)
    table_ids = {t["id"] for t in payload}
    assert "analytics.users" in table_ids


@pytest.mark.asyncio
async def test_describe_table() -> None:
    server = build_server()
    result = await server.call_tool("describe_table", {"table_id": "analytics.users"})
    payload = _parse_result(result)
    assert isinstance(payload, dict)
    # describe_table returns schema/metadata; 'columns' is the canonical key
    assert "columns" in payload
    col_names = [c["name"] for c in payload["columns"]]
    assert "user_id" in col_names


@pytest.mark.asyncio
async def test_sample_table() -> None:
    server = build_server()
    result = await server.call_tool("sample_table", {"table_id": "analytics.users", "n": 3})
    payload = _unwrap_list(_parse_result(result))
    assert isinstance(payload, list)
    assert 1 <= len(payload) <= 3


@pytest.mark.asyncio
async def test_search_schema() -> None:
    server = build_server()
    result = await server.call_tool("search_schema", {"term": "userid"})
    payload = _unwrap_list(_parse_result(result))
    # Should return a list; fuzzy match on "userid" should find user_id columns
    assert isinstance(payload, list)
    assert len(payload) > 0
    # At least one hit should reference the 'user_id' column
    columns = [hit["column"] for hit in payload]
    assert "user_id" in columns


@pytest.mark.asyncio
async def test_estimate_cost() -> None:
    server = build_server()
    result = await server.call_tool("estimate_cost", {"sql": "SELECT * FROM `analytics.users`"})
    payload = _parse_result(result)
    assert isinstance(payload, dict)
    assert "bytes_scanned" in payload
    assert "estimated_usd" in payload


@pytest.mark.asyncio
async def test_run_query() -> None:
    server = build_server()
    result = await server.call_tool(
        "run_query",
        {"sql": "SELECT COUNT(*) AS n FROM `analytics.users`"},
    )
    payload = _parse_result(result)
    assert isinstance(payload, dict)
    # Successful run returns 'rows'; cost-cap error returns 'error'
    assert "error" not in payload, f"run_query returned error: {payload}"
    assert "rows" in payload
    assert payload["rows"] == [{"n": 5}]
