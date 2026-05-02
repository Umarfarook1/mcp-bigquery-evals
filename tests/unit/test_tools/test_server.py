from mcp_bigquery_evals.server import build_server


async def test_build_server_registers_seven_tools(monkeypatch, tmp_path):
    """Sanity check that all seven MCP tools are registered."""
    fixture = tmp_path / "fake.yaml"
    fixture.write_text("datasets: []\ntables: []\n")
    monkeypatch.setenv("MCP_BIGQUERY_FAKE_FIXTURE", str(fixture))

    server = build_server()
    # FastMCP.list_tools() is async in mcp>=1.27; returns list[mcp.types.Tool]
    tools = await server.list_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == {
        "list_datasets",
        "list_tables",
        "describe_table",
        "sample_table",
        "search_schema",
        "estimate_cost",
        "run_query",
    }
