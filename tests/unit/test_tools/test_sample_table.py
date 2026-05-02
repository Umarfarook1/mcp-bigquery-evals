from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.sample_table import sample_table

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_sample_table_default_n():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = sample_table(client, "analytics.users")
    assert len(result) == 5  # default n=5; fixture has 5 rows
    assert result[0]["user_id"] == "u1"


def test_sample_table_custom_n():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = sample_table(client, "analytics.events", n=2)
    assert len(result) == 2


def test_sample_table_unknown_returns_error_dict():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = sample_table(client, "analytics.nonexistent")
    assert result == {"error": "table_not_found", "table_id": "analytics.nonexistent"}
