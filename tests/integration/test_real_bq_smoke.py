"""Real BigQuery smoke test against bigquery-public-data.

Run with: pytest -m bq

Requires:
- BIGQUERY_PROJECT env var set to a personal GCP project (NOT bigquery-public-data;
  that's the data source, but query jobs run under YOUR project).
- Application Default Credentials configured locally (run `gcloud auth application-default login`).

Cost: each test scans ~1KB of bigquery-public-data.samples.shakespeare.
Total cost per run: well under $0.001.
"""

from __future__ import annotations

import os

import pytest

from mcp_bigquery_evals.bq.errors import BigQueryError
from mcp_bigquery_evals.bq.real import RealBigQueryClient

pytestmark = pytest.mark.bq


@pytest.fixture
def real_client() -> RealBigQueryClient:
    project = os.environ.get("BIGQUERY_PROJECT")
    if not project:
        pytest.skip("BIGQUERY_PROJECT env var not set")
    return RealBigQueryClient(project=project)


def test_real_dry_run_against_public_dataset(real_client: RealBigQueryClient) -> None:
    """Verify dry_run hits real BQ API and returns sensible cost numbers."""
    sql = (
        "SELECT COUNT(*) AS n FROM `bigquery-public-data.samples.shakespeare` WHERE word = 'hamlet'"
    )
    dr = real_client.dry_run(sql)
    assert dr.bytes_scanned > 0, "dry_run should report nonzero bytes for a real query"
    assert dr.estimated_usd > 0, "dry_run should compute a positive cost estimate"


def test_real_execute_against_public_dataset(real_client: RealBigQueryClient) -> None:
    """Verify execute returns rows from real BQ."""
    sql = (
        "SELECT word, word_count "
        "FROM `bigquery-public-data.samples.shakespeare` "
        "WHERE word = 'hamlet' "
        "ORDER BY word_count DESC LIMIT 1"
    )
    result = real_client.execute(sql)
    assert len(result.rows) == 1
    assert result.rows[0]["word"] == "hamlet"
    assert isinstance(result.rows[0]["word_count"], int)
    assert result.bytes_scanned > 0
    assert result.ms >= 0


def test_real_invalid_sql_raises_bigquery_error(real_client: RealBigQueryClient) -> None:
    """Real BadRequest should translate to invalid_sql code."""
    with pytest.raises(BigQueryError) as exc_info:
        real_client.dry_run("SELECT * FRM `bigquery-public-data.samples.shakespeare`")
    assert exc_info.value.code == "invalid_sql"


def test_real_unknown_table_raises_table_not_found(real_client: RealBigQueryClient) -> None:
    """Real NotFound should translate to table_not_found code."""
    with pytest.raises(BigQueryError) as exc_info:
        real_client.dry_run("SELECT * FROM `bigquery-public-data.samples.nonexistent_table_xyz`")
    assert exc_info.value.code == "table_not_found"


def test_real_list_datasets_for_personal_project(real_client: RealBigQueryClient) -> None:
    """list_datasets must succeed (returning [] is fine for an empty project)."""
    result = real_client.list_datasets()
    assert isinstance(result, list)


def test_real_list_tables_for_public_dataset(real_client: RealBigQueryClient) -> None:
    """list_tables against a known public dataset returns at least one table."""
    tables = real_client.list_tables("bigquery-public-data.samples")
    assert len(tables) > 0
    table_ids = {t.id for t in tables}
    assert "bigquery-public-data.samples.shakespeare" in table_ids


def test_real_get_table_for_public_dataset(real_client: RealBigQueryClient) -> None:
    """describe_table on a known public table returns a populated schema."""
    schema = real_client.get_table("bigquery-public-data.samples.shakespeare")
    assert schema.table.row_count > 0
    assert schema.table.size_bytes > 0
    col_names = {c.name for c in schema.columns}
    assert {"word", "word_count", "corpus"}.issubset(col_names)


def test_real_sample_table_returns_rows(real_client: RealBigQueryClient) -> None:
    """sample_rows returns the requested number of rows."""
    rows = real_client.sample_rows("bigquery-public-data.samples.shakespeare", n=3)
    assert len(rows) == 3
    assert all("word" in r for r in rows)


def test_real_run_query_under_default_cap(real_client: RealBigQueryClient) -> None:
    """The MCP run_query tool against real BQ with default 100MB cap."""
    from typing import cast

    from mcp_bigquery_evals.tools.run_query import run_query

    result = run_query(
        real_client,
        "SELECT word FROM `bigquery-public-data.samples.shakespeare` WHERE word = 'hamlet' LIMIT 1",
    )
    assert "rows" in result, f"expected success, got: {result}"
    rows = cast(list[dict[str, object]], result["rows"])
    assert len(rows) == 1
    assert rows[0]["word"] == "hamlet"
