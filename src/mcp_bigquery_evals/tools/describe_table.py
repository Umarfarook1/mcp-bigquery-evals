from mcp_bigquery_evals.bq.protocol import BigQueryClient


def describe_table(client: BigQueryClient, table_id: str) -> dict[str, object]:
    """MCP tool: schema + metadata for a single table."""
    try:
        schema = client.get_table(table_id)
    except KeyError:
        return {"error": "table_not_found", "table_id": table_id}
    return {
        "id": schema.table.id,
        "row_count": schema.table.row_count,
        "size_bytes": schema.table.size_bytes,
        "columns": [
            {"name": c.name, "type": c.type, "description": c.description} for c in schema.columns
        ],
    }
