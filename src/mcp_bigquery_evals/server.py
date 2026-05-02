from __future__ import annotations

import os
from pathlib import Path
from typing import cast

from mcp.server.fastmcp import FastMCP

from mcp_bigquery_evals.bq.protocol import BigQueryClient
from mcp_bigquery_evals.tools.describe_table import describe_table
from mcp_bigquery_evals.tools.estimate_cost import estimate_cost
from mcp_bigquery_evals.tools.list_datasets import list_datasets
from mcp_bigquery_evals.tools.list_tables import list_tables
from mcp_bigquery_evals.tools.run_query import run_query
from mcp_bigquery_evals.tools.sample_table import sample_table
from mcp_bigquery_evals.tools.search_schema import search_schema_tool


def build_client() -> BigQueryClient:
    """Wire up the BigQueryClient based on env vars.

    - MCP_BIGQUERY_FAKE_FIXTURE set → FakeBigQueryClient.from_yaml(...)
    - otherwise → RealBigQueryClient with ADC + BIGQUERY_PROJECT
    """
    fake_path = os.environ.get("MCP_BIGQUERY_FAKE_FIXTURE")
    if fake_path:
        from mcp_bigquery_evals.bq.fake import FakeBigQueryClient

        return FakeBigQueryClient.from_yaml(Path(fake_path))

    project = os.environ.get("BIGQUERY_PROJECT")
    if not project:
        raise RuntimeError(
            "BIGQUERY_PROJECT env var is required (or set MCP_BIGQUERY_FAKE_FIXTURE for the fake)."
        )

    from mcp_bigquery_evals.bq.real import RealBigQueryClient

    return cast(BigQueryClient, RealBigQueryClient(project=project))


def build_server() -> FastMCP:
    """Construct the MCP server with all 7 tools registered."""
    mcp = FastMCP("mcp-bigquery-evals")
    client = build_client()

    @mcp.tool(name="list_datasets")
    def _ld() -> list[dict[str, object]]:
        """List all datasets in the configured BigQuery project."""
        return list_datasets(client)

    @mcp.tool(name="list_tables")
    def _lt(dataset_id: str) -> list[dict[str, object]]:
        """List all tables in a given dataset."""
        return list_tables(client, dataset_id)

    @mcp.tool(name="describe_table")
    def _dt(table_id: str) -> dict[str, object]:
        """Schema and metadata for a single table."""
        return describe_table(client, table_id)

    @mcp.tool(name="sample_table")
    def _st(table_id: str, n: int = 5) -> list[dict[str, object]] | dict[str, object]:
        """Return up to n sample rows from a table."""
        return sample_table(client, table_id, n)

    @mcp.tool(name="search_schema")
    def _ss(term: str) -> list[dict[str, object]]:
        """Fuzzy-match a term against all column names; return top hits."""
        # search_schema_tool returns list[SchemaHit]; SchemaHit is a TypedDict
        # (subtype of dict[str, object]), so the cast is safe.
        return [dict(hit) for hit in search_schema_tool(client, term)]

    @mcp.tool(name="estimate_cost")
    def _ec(sql: str) -> dict[str, object]:
        """Dry-run a query; return bytes_scanned and estimated_usd."""
        return estimate_cost(client, sql)

    @mcp.tool(name="run_query")
    def _rq(sql: str, max_bytes_scanned: int = 100 * 1024 * 1024) -> dict[str, object]:
        """Execute a SELECT after dry-run cap check; returns rows or structured error."""
        return run_query(client, sql, max_bytes_scanned=max_bytes_scanned)

    return mcp
