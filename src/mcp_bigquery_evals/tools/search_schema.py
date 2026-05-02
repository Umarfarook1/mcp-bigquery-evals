from mcp_bigquery_evals.bq.protocol import BigQueryClient
from mcp_bigquery_evals.schema_search import SchemaHit, search_schema


def search_schema_tool(client: BigQueryClient, term: str) -> list[SchemaHit]:
    """MCP tool: fuzzy-match a term against all column names; return top hits."""
    return search_schema(client, term)
