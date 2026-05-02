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
    from google.api_core.exceptions import NotFound

    mock = MagicMock()
    mock.list_tables.side_effect = NotFound("dataset not found")
    client = RealBigQueryClient(project="myproj", _client=mock)
    assert client.list_tables("nonexistent") == []


def test_list_tables_propagates_non_structural_errors() -> None:
    from google.api_core.exceptions import ServiceUnavailable

    mock = MagicMock()
    mock.list_tables.side_effect = ServiceUnavailable("transient")
    client = RealBigQueryClient(project="myproj", _client=mock)
    with pytest.raises(ServiceUnavailable):
        client.list_tables("analytics")


def test_list_tables_handles_null_num_rows(mock_bq: MagicMock) -> None:
    """Streaming/external tables return None for num_rows; we must coerce to 0."""
    t_streaming = MagicMock()
    t_streaming.table_id = "live_stream"
    mock_bq.list_tables.side_effect = lambda ds: (
        [t_streaming] if (ds == "analytics" or getattr(ds, "dataset_id", "") == "analytics") else []
    )

    def _get_table_with_null_rows(table_ref: object) -> MagicMock:
        t = MagicMock()
        t.table_id = "live_stream"
        t.num_rows = None  # streaming table without materialized stats
        t.num_bytes = None
        t.schema = []
        return t

    mock_bq.get_table.side_effect = _get_table_with_null_rows

    client = RealBigQueryClient(project="myproj", _client=mock_bq)
    tables = client.list_tables("analytics")
    assert len(tables) == 1
    assert tables[0].row_count == 0
    assert tables[0].size_bytes == 0


def test_list_datasets_empty_project() -> None:
    mock = MagicMock()
    mock.list_datasets.return_value = []
    client = RealBigQueryClient(project="myproj", _client=mock)
    assert client.list_datasets() == []


def test_method_calls_after_close_raise_clear_error(real_client: RealBigQueryClient) -> None:
    real_client.close()
    with pytest.raises(RuntimeError, match="closed"):
        real_client.list_datasets()


def test_close_idempotent(real_client: RealBigQueryClient) -> None:
    real_client.close()
    real_client.close()  # must not raise


def test_get_table_returns_schema(real_client: RealBigQueryClient) -> None:
    schema = real_client.get_table("analytics.users")
    assert schema.table.id == "analytics.users"
    assert schema.table.row_count == 100
    assert schema.columns[0].name == "user_id"
    assert schema.columns[0].type == "STRING"
    assert schema.columns[0].description == "Primary key."


def test_get_table_handles_null_metadata(mock_bq: MagicMock) -> None:
    """Tables that haven't been materialized return None for num_rows/num_bytes."""

    def _get_table_with_nulls(table_ref: object) -> MagicMock:
        t = MagicMock()
        t.table_id = "live"
        t.num_rows = None
        t.num_bytes = None
        t.schema = []
        return t

    mock_bq.get_table.side_effect = _get_table_with_nulls

    client = RealBigQueryClient(project="myproj", _client=mock_bq)
    schema = client.get_table("analytics.live")
    assert schema.table.row_count == 0
    assert schema.table.size_bytes == 0
    assert schema.columns == []


def test_sample_rows_returns_dicts(mock_bq: MagicMock) -> None:
    """sample_rows uses list_rows() which returns RowIterator yielding Row objects."""
    row_a = MagicMock()
    row_a.items.return_value = [("user_id", "u1"), ("email", "alice@example.com")]
    row_b = MagicMock()
    row_b.items.return_value = [("user_id", "u2"), ("email", "bob@example.com")]
    row_c = MagicMock()
    row_c.items.return_value = [("user_id", "u3"), ("email", "carol@example.com")]
    mock_bq.list_rows.return_value = [row_a, row_b, row_c]

    client = RealBigQueryClient(project="myproj", _client=mock_bq)
    rows = client.sample_rows("analytics.users", n=3)
    assert len(rows) == 3
    assert rows[0] == {"user_id": "u1", "email": "alice@example.com"}
    mock_bq.list_rows.assert_called_once_with("analytics.users", max_results=3)


def test_sample_rows_clamps_negative_n(mock_bq: MagicMock) -> None:
    mock_bq.list_rows.return_value = []
    client = RealBigQueryClient(project="myproj", _client=mock_bq)
    rows = client.sample_rows("analytics.users", n=-5)
    assert rows == []
    mock_bq.list_rows.assert_called_once_with("analytics.users", max_results=0)


def test_sample_rows_zero_n(mock_bq: MagicMock) -> None:
    mock_bq.list_rows.return_value = []
    client = RealBigQueryClient(project="myproj", _client=mock_bq)
    rows = client.sample_rows("analytics.users", n=0)
    assert rows == []


def test_dry_run_returns_estimate(mock_bq: MagicMock) -> None:
    job = MagicMock()
    job.total_bytes_processed = 1_000_000_000  # 1 GB
    mock_bq.query.return_value = job
    client = RealBigQueryClient(project="myproj", _client=mock_bq)

    result = client.dry_run("SELECT * FROM `analytics.users`")
    assert result.bytes_scanned == 1_000_000_000
    # 1 GB / (1 TB) * $5 ≈ $0.00488...
    assert 0.004 < result.estimated_usd < 0.006

    # Verify the dry-run flag was set
    call = mock_bq.query.call_args
    job_config = call.kwargs.get("job_config")
    assert job_config is not None
    assert job_config.dry_run is True
    assert job_config.use_query_cache is False


def test_dry_run_handles_null_total_bytes(mock_bq: MagicMock) -> None:
    """If BQ returns None for total_bytes_processed, we should treat as 0."""
    job = MagicMock()
    job.total_bytes_processed = None
    mock_bq.query.return_value = job
    client = RealBigQueryClient(project="myproj", _client=mock_bq)

    result = client.dry_run("SELECT 1")
    assert result.bytes_scanned == 0
    assert result.estimated_usd == 0.0


def test_execute_returns_rows(mock_bq: MagicMock) -> None:
    job = MagicMock()
    row1 = MagicMock()
    row1.items.return_value = [("n", 5)]
    job.result.return_value = [row1]
    job.total_bytes_processed = 2048
    mock_bq.query.return_value = job

    client = RealBigQueryClient(project="myproj", _client=mock_bq)
    result = client.execute("SELECT COUNT(*) AS n FROM `analytics.users`")
    assert result.rows == [{"n": 5}]
    assert result.bytes_scanned == 2048
    assert result.cost_usd >= 0
    assert result.ms >= 0


def test_execute_returns_empty_for_zero_rows(mock_bq: MagicMock) -> None:
    job = MagicMock()
    job.result.return_value = []
    job.total_bytes_processed = 1024
    mock_bq.query.return_value = job

    client = RealBigQueryClient(project="myproj", _client=mock_bq)
    result = client.execute("SELECT * FROM `t` WHERE 1=0")
    assert result.rows == []
    assert result.bytes_scanned == 1024
