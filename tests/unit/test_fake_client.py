from pathlib import Path

import pytest

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.bq.protocol import BigQueryClient

FIXTURE = Path(__file__).parent.parent / "fixtures" / "fake_warehouse.yaml"


@pytest.fixture
def client() -> FakeBigQueryClient:
    return FakeBigQueryClient.from_yaml(FIXTURE)


def test_implements_protocol(client: FakeBigQueryClient):
    assert isinstance(client, BigQueryClient)


def test_list_datasets(client: FakeBigQueryClient):
    datasets = client.list_datasets()
    ids = [d.id for d in datasets]
    assert ids == ["analytics", "ops"]
    analytics = next(d for d in datasets if d.id == "analytics")
    assert analytics.location == "US"
    assert "User and event data" in (analytics.description or "")


def test_list_tables(client: FakeBigQueryClient):
    tables = client.list_tables("analytics")
    ids = [t.id for t in tables]
    assert ids == ["analytics.users", "analytics.events"]


def test_list_tables_unknown_dataset_returns_empty(client: FakeBigQueryClient):
    assert client.list_tables("nonexistent") == []


def test_get_table_returns_schema(client: FakeBigQueryClient):
    schema = client.get_table("analytics.users")
    assert schema.table.id == "analytics.users"
    col_names = [c.name for c in schema.columns]
    assert col_names == ["user_id", "email", "signup_date", "country"]
    assert schema.table.row_count == 5


def test_get_table_unknown_raises(client: FakeBigQueryClient):
    with pytest.raises(KeyError):
        client.get_table("analytics.nonexistent")
