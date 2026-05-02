"""Unit tests for RealBigQueryClient.

Uses unittest.mock to stub google.cloud.bigquery.Client so tests run without
GCP credentials. Real-BQ smoke tests live in tests/integration/test_real_bq_smoke.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mcp_bigquery_evals.bq.protocol import BigQueryClient
from mcp_bigquery_evals.bq.real import RealBigQueryClient


@pytest.fixture
def mock_bq() -> MagicMock:
    """A google.cloud.bigquery.Client mock pre-loaded with two datasets and two tables."""
    client = MagicMock()

    # list_datasets() returns iterable of DatasetListItem
    ds1 = MagicMock()
    ds1.dataset_id = "analytics"
    ds2 = MagicMock()
    ds2.dataset_id = "ops"
    client.list_datasets.return_value = [ds1, ds2]

    # get_dataset() returns Dataset with description + location
    def _get_dataset(ref: object) -> MagicMock:
        ds_id = ref if isinstance(ref, str) else getattr(ref, "dataset_id", str(ref))
        ds = MagicMock()
        ds.dataset_id = ds_id
        ds.description = f"description for {ds_id}"
        ds.location = "US"
        return ds

    client.get_dataset.side_effect = _get_dataset

    # list_tables() returns iterable of TableListItem
    def _list_tables(dataset_ref: object) -> list[MagicMock]:
        ds_id = (
            dataset_ref if isinstance(dataset_ref, str) else getattr(dataset_ref, "dataset_id", "")
        )
        if ds_id == "analytics":
            t1 = MagicMock()
            t1.table_id = "users"
            t2 = MagicMock()
            t2.table_id = "events"
            return [t1, t2]
        return []

    client.list_tables.side_effect = _list_tables

    # get_table() returns Table with num_rows + num_bytes + schema
    def _get_table(table_ref: object) -> MagicMock:
        t = MagicMock()
        t.table_id = "users"
        t.num_rows = 100
        t.num_bytes = 5000
        col = MagicMock()
        col.name = "user_id"
        col.field_type = "STRING"
        col.description = "Primary key."
        t.schema = [col]
        return t

    client.get_table.side_effect = _get_table

    return client


@pytest.fixture
def real_client(mock_bq: MagicMock) -> RealBigQueryClient:
    return RealBigQueryClient(project="myproj", _client=mock_bq)


def test_implements_protocol(real_client: RealBigQueryClient) -> None:
    assert isinstance(real_client, BigQueryClient)


def test_list_datasets(real_client: RealBigQueryClient) -> None:
    datasets = real_client.list_datasets()
    ids = [d.id for d in datasets]
    assert ids == ["analytics", "ops"]
    assert datasets[0].location == "US"
    assert datasets[0].description == "description for analytics"


def test_list_tables_for_known_dataset(real_client: RealBigQueryClient) -> None:
    tables = real_client.list_tables("analytics")
    ids = [t.id for t in tables]
    assert ids == ["analytics.users", "analytics.events"]
    assert tables[0].row_count == 100
    assert tables[0].size_bytes == 5000


def test_list_tables_for_unknown_dataset_returns_empty(real_client: RealBigQueryClient) -> None:
    # Mock raises if asked for nonexistent; client should return [] gracefully
    mock = MagicMock()
    mock.list_tables.side_effect = Exception("not found")
    client = RealBigQueryClient(project="myproj", _client=mock)
    assert client.list_tables("nonexistent") == []


def test_close_idempotent(real_client: RealBigQueryClient) -> None:
    real_client.close()
    real_client.close()  # must not raise
