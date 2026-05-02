from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.search_schema import search_schema_tool

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_search_schema_finds_user_id():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = search_schema_tool(client, "userid")
    assert isinstance(result, list)
    top = result[0]
    assert top["table"] == "analytics.users"
    assert top["column"] == "user_id"
    assert top["similarity"] >= 80
