from mcp_bigquery_evals.bq.protocol import BigQueryClient


def list_tables(client: BigQueryClient, dataset_id: str) -> list[dict[str, object]]:
    """MCP tool: list all tables in a given dataset."""
    return [
        {"id": t.id, "row_count": t.row_count, "size_bytes": t.size_bytes}
        for t in client.list_tables(dataset_id)
    ]
