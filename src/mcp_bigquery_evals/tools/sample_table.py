from mcp_bigquery_evals.bq.protocol import BigQueryClient


def sample_table(
    client: BigQueryClient, table_id: str, n: int = 5
) -> list[dict[str, object]] | dict[str, object]:
    """MCP tool: return up to n sample rows from a table."""
    try:
        return client.sample_rows(table_id, n)
    except KeyError:
        return {"error": "table_not_found", "table_id": table_id}
