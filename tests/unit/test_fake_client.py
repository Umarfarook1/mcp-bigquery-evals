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


def test_sample_rows_returns_n(client: FakeBigQueryClient):
    rows = client.sample_rows("analytics.users", n=3)
    assert len(rows) == 3
    assert {"user_id", "email", "signup_date", "country"} <= set(rows[0].keys())


def test_sample_rows_caps_at_total(client: FakeBigQueryClient):
    rows = client.sample_rows("analytics.users", n=999)
    assert len(rows) == 5  # only 5 rows in fixture


def test_sample_rows_unknown_table_raises(client: FakeBigQueryClient):
    with pytest.raises(KeyError):
        client.sample_rows("analytics.nonexistent", n=1)


def test_sample_rows_negative_n_returns_empty(client: FakeBigQueryClient):
    rows = client.sample_rows("analytics.users", n=-3)
    assert rows == []


def test_sample_rows_zero_n_returns_empty(client: FakeBigQueryClient):
    rows = client.sample_rows("analytics.users", n=0)
    assert rows == []


def test_execute_select_count(client: FakeBigQueryClient):
    r = client.execute("SELECT COUNT(*) AS n FROM `analytics.users`")
    assert r.rows == [{"n": 5}]
    assert r.bytes_scanned > 0
    assert r.cost_usd >= 0
    assert r.ms >= 0


def test_execute_select_filter(client: FakeBigQueryClient):
    r = client.execute(
        "SELECT user_id FROM `analytics.users` WHERE country = 'IN' ORDER BY user_id"
    )
    assert r.rows == [{"user_id": "u3"}, {"user_id": "u5"}]


def test_execute_join(client: FakeBigQueryClient):
    r = client.execute(
        "SELECT u.country, COUNT(*) AS events "
        "FROM `analytics.users` u "
        "JOIN `analytics.events` e ON u.user_id = e.user_id "
        "GROUP BY u.country "
        "ORDER BY u.country"
    )
    assert r.rows == [
        {"country": "IN", "events": 3},
        {"country": "US", "events": 3},
    ]


def test_dry_run_returns_estimate(client: FakeBigQueryClient):
    r = client.dry_run("SELECT * FROM `analytics.users`")
    assert r.bytes_scanned > 0
    assert r.estimated_usd >= 0


def test_execute_invalid_sql_raises(client: FakeBigQueryClient):
    with pytest.raises(ValueError):
        client.execute("NOT A QUERY")


def test_bq_to_sqlite_translates_backticked_two_part(client: FakeBigQueryClient):
    out = client._bq_to_sqlite("SELECT * FROM `analytics.users`")
    assert "analytics__users" in out
    assert "`" not in out


def test_bq_to_sqlite_translates_bare_two_part_for_known_tables(client: FakeBigQueryClient):
    out = client._bq_to_sqlite("SELECT * FROM analytics.users WHERE 1=1")
    assert "analytics__users" in out
    assert "analytics.users" not in out


def test_bq_to_sqlite_does_not_touch_alias_dot_columns(client: FakeBigQueryClient):
    out = client._bq_to_sqlite("SELECT u.country FROM `analytics.users` u")
    assert "u.country" in out  # alias ref preserved
    assert "analytics__users" in out


def test_table_referenced_uses_word_boundary():
    from mcp_bigquery_evals.bq.fake import _table_referenced

    assert _table_referenced("SELECT * FROM `analytics.users`", "analytics.users")
    assert not _table_referenced("SELECT * FROM `analytics.users_extended`", "analytics.users")
