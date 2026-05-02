from mcp_bigquery_evals.bq.protocol import BigQueryClient


def estimate_cost(client: BigQueryClient, sql: str) -> dict[str, object]:
    """MCP tool: dry-run a query, return bytes_scanned and estimated_usd."""
    dr = client.dry_run(sql)
    return {"bytes_scanned": dr.bytes_scanned, "estimated_usd": dr.estimated_usd}
