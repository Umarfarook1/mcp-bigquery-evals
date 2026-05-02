from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.run_query import run_query

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_run_query_under_cap_returns_rows():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = run_query(client, "SELECT COUNT(*) AS n FROM `analytics.users`")
    assert "rows" in result
    assert result["rows"] == [{"n": 5}]
    assert result["bytes_scanned"] >= 0
    assert result["cost_usd"] >= 0
    assert "ms" in result


def test_run_query_over_cap_returns_error():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    # max_bytes_scanned=1 forces refusal even on tiny fake data
    result = run_query(
        client,
        "SELECT * FROM `analytics.users`",
        max_bytes_scanned=1,
    )
    assert result["error"] == "cost_cap_exceeded"
    assert "would_scan" in result
    assert "cap" in result
    assert "hint" in result


def test_run_query_invalid_sql_returns_error():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = run_query(client, "NOT A QUERY")
    assert result["error"] == "execution_failed"
    assert "message" in result
