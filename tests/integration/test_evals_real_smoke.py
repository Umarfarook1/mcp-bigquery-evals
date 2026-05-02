"""End-to-end smoke: real BQ + real Anthropic, 3 golden pairs.

Run with: pytest -m live

Cost per run:
  - ~3 BQ dry-runs + ~3 BQ executions ≈ ~$0.001 (depends on which 3 pairs run first)
  - ~3 Anthropic Haiku calls ≈ ~$0.005-0.015 depending on schema size

Skipped when:
  - The default pytest invocation runs (excluded by addopts in pyproject.toml)
  - BIGQUERY_PROJECT env var is missing
  - ANTHROPIC_API_KEY env var is missing
  - golden.yaml does not exist (which it does as of T15, but be defensive)
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from mcp_bigquery_evals.bq.real import RealBigQueryClient
from mcp_bigquery_evals.evals.anthropic_model import make_anthropic_model
from mcp_bigquery_evals.evals.runner import run_evals

pytestmark = pytest.mark.live

GOLDEN = Path("src/mcp_bigquery_evals/evals/golden.yaml")


@pytest.fixture
def real_client() -> RealBigQueryClient:
    project = os.environ.get("BIGQUERY_PROJECT")
    if not project:
        pytest.skip("BIGQUERY_PROJECT not set")
    return RealBigQueryClient(project=project)


def test_live_eval_smoke_3_pairs(real_client: RealBigQueryClient) -> None:
    """Run the eval harness end-to-end against real BQ + real Anthropic, limited to 3 pairs."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
    if not GOLDEN.exists():
        pytest.skip("golden.yaml does not exist")

    model_fn = make_anthropic_model(model_id="claude-haiku-4-5")
    report = run_evals(
        client=real_client,
        golden_path=GOLDEN,
        model_fn=model_fn,
        limit=3,
    )

    # Don't assert a specific accuracy - that's what we're measuring.
    # Just assert the run completed without crashing and produced sensible numbers.
    assert report.total == 3
    assert 0.0 <= report.accuracy <= 1.0
    assert all(r.predicted_sql is not None for r in report.per_pair)
    # No gold pair should fail to execute (golden.yaml is hand-written; if a
    # gold_sql fails, that's a bug in the golden, not in the model).
    assert report.gold_errors == 0, (
        "unexpected gold_errors > 0; check the first 3 pairs in golden.yaml: "
        + "; ".join(f"id={r.id}: {r.error}" for r in report.per_pair if r.gold_errored)
    )
    print(f"\nSmoke accuracy on 3 pairs: {report.accuracy:.1%}")


def test_live_real_client_can_query_public_dataset(real_client: RealBigQueryClient) -> None:
    """Standalone live check: real BQ client can hit bigquery-public-data."""
    sql = (
        "SELECT word FROM `bigquery-public-data.samples.shakespeare` WHERE word = 'hamlet' LIMIT 1"
    )
    result = real_client.execute(sql)
    assert len(result.rows) == 1
    assert result.rows[0]["word"] == "hamlet"
