from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.list_tables import list_tables

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_list_tables_for_known_dataset():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = list_tables(client, "analytics")
    ids = [t["id"] for t in result]
    assert ids == ["analytics.users", "analytics.events"]
    users = next(t for t in result if t["id"] == "analytics.users")
    assert users["row_count"] == 5
    assert users["size_bytes"] > 0


def test_list_tables_for_unknown_dataset_returns_empty():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    assert list_tables(client, "nonexistent") == []
