from mcp_bigquery_evals.bq.types import (
    Column,
    Dataset,
    DryRunResult,
    QueryResult,
    Table,
)


def test_dataset_minimal_fields():
    d = Dataset(id="analytics", location="US", description=None)
    assert d.id == "analytics"
    assert d.location == "US"
    assert d.description is None


def test_table_with_metadata():
    t = Table(id="analytics.users", row_count=1000, size_bytes=50_000)
    assert t.id == "analytics.users"
    assert t.row_count == 1000
    assert t.size_bytes == 50_000


def test_column_with_description():
    c = Column(name="user_id", type="STRING", description="primary key")
    assert c.name == "user_id"
    assert c.type == "STRING"
    assert c.description == "primary key"


def test_dry_run_result():
    r = DryRunResult(bytes_scanned=1_000_000, estimated_usd=0.000005)
    assert r.bytes_scanned == 1_000_000
    assert r.estimated_usd == 0.000005


def test_query_result():
    r = QueryResult(
        rows=[{"a": 1}, {"a": 2}],
        bytes_scanned=2048,
        cost_usd=0.00001,
        ms=120,
    )
    assert len(r.rows) == 2
    assert r.bytes_scanned == 2048
    assert r.ms == 120
