from mcp_bigquery_evals.bq.errors import BigQueryError
from mcp_bigquery_evals.bq.protocol import BigQueryClient


def estimate_cost(client: BigQueryClient, sql: str) -> dict[str, object]:
    """MCP tool: dry-run a query, return bytes_scanned and estimated_usd."""
    try:
        dr = client.dry_run(sql)
    except BigQueryError as e:
        return e.to_dict()
    return {"bytes_scanned": dr.bytes_scanned, "estimated_usd": dr.estimated_usd}
