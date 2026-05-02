from mcp_bigquery_evals.bq.protocol import BigQueryClient


def list_datasets(client: BigQueryClient) -> list[dict[str, object]]:
    """MCP tool: list all datasets in the configured project."""
    return [
        {"id": d.id, "location": d.location, "description": d.description}
        for d in client.list_datasets()
    ]
