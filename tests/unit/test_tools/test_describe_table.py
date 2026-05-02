from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.describe_table import describe_table

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_describe_table_returns_columns_and_metadata():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = describe_table(client, "analytics.users")
    assert result["id"] == "analytics.users"
    assert result["row_count"] == 5
    assert result["size_bytes"] > 0
    col_names = [c["name"] for c in result["columns"]]
    assert col_names == ["user_id", "email", "signup_date", "country"]
    assert result["columns"][0] == {
        "name": "user_id",
        "type": "STRING",
        "description": "Primary key.",
    }


def test_describe_table_unknown_returns_error_dict():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = describe_table(client, "analytics.nonexistent")
    assert result == {"error": "table_not_found", "table_id": "analytics.nonexistent"}
