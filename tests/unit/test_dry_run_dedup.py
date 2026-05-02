"""Verify run_query calls client.dry_run exactly once per invocation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.run_query import run_query

FIXTURE = Path(__file__).parent.parent / "fixtures" / "fake_warehouse.yaml"


@pytest.fixture
def client() -> FakeBigQueryClient:
    return FakeBigQueryClient.from_yaml(FIXTURE)


def test_run_query_calls_dry_run_exactly_once(client: FakeBigQueryClient) -> None:
    with patch.object(client, "dry_run", wraps=client.dry_run) as spy:
        result = run_query(client, "SELECT COUNT(*) AS n FROM `analytics.users`")
    assert "rows" in result, f"expected success, got: {result}"
    assert spy.call_count == 1, (
        f"run_query should dry-run exactly once; called {spy.call_count} times"
    )


def test_fake_execute_dry_runs_when_no_result_provided(client: FakeBigQueryClient) -> None:
    """Backward compat: execute() without dry_run_result still works (dry-runs internally)."""
    with patch.object(client, "dry_run", wraps=client.dry_run) as spy:
        r = client.execute("SELECT COUNT(*) AS n FROM `analytics.users`")
    assert r.rows == [{"n": 5}]
    assert spy.call_count == 1


def test_fake_execute_uses_provided_dry_run_result(client: FakeBigQueryClient) -> None:
    """When a DryRunResult is passed, execute() must NOT call dry_run again."""
    from mcp_bigquery_evals.bq.types import DryRunResult

    with patch.object(client, "dry_run", wraps=client.dry_run) as spy:
        r = client.execute(
            "SELECT COUNT(*) AS n FROM `analytics.users`",
            dry_run_result=DryRunResult(bytes_scanned=999, estimated_usd=0.0042),
        )
    assert r.rows == [{"n": 5}]
    assert r.bytes_scanned == 999
    assert r.cost_usd == 0.0042
    assert spy.call_count == 0, "dry_run should not be called when result is supplied"
