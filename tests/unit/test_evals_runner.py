"""Unit tests for the eval runner — uses FakeBigQueryClient and a mock model callback."""

from __future__ import annotations

from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.evals.runner import run_evals

FIXTURE = Path(__file__).parent.parent / "fixtures" / "fake_warehouse.yaml"
GOLDEN = Path(__file__).parent.parent / "fixtures" / "golden_fake.yaml"


def _perfect_model(prompt: dict[str, str], gold_sql: str) -> str:
    """Mock model that always returns the gold SQL → 100% accuracy."""
    return gold_sql


def _broken_model(prompt: dict[str, str], gold_sql: str) -> str:
    """Mock model that always returns wrong SQL → 0% accuracy."""
    return "SELECT 999 AS wrong"


def _invalid_sql_model(prompt: dict[str, str], gold_sql: str) -> str:
    """Mock model that returns invalid SQL → 0% accuracy + error recorded."""
    return "NOT A SQL QUERY"


def test_runner_perfect_model_yields_100_percent() -> None:
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    report = run_evals(
        client=client,
        golden_path=GOLDEN,
        model_fn=_perfect_model,
    )
    assert report.accuracy == 1.0
    assert report.total == 5
    assert report.passes == 5


def test_runner_broken_model_yields_0_percent() -> None:
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    report = run_evals(
        client=client,
        golden_path=GOLDEN,
        model_fn=_broken_model,
    )
    assert report.accuracy == 0.0
    assert report.passes == 0


def test_runner_records_per_pair_results() -> None:
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    report = run_evals(
        client=client,
        golden_path=GOLDEN,
        model_fn=_perfect_model,
    )
    assert len(report.per_pair) == 5
    for r in report.per_pair:
        assert r.passed is True
        assert r.predicted_sql is not None
        assert r.gold_sql is not None
        assert r.error is None
        assert r.id > 0
        assert r.dataset != ""
        assert r.nl != ""


def test_runner_handles_invalid_predicted_sql_as_failure() -> None:
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    report = run_evals(
        client=client,
        golden_path=GOLDEN,
        model_fn=_invalid_sql_model,
    )
    assert report.passes == 0
    assert report.accuracy == 0.0
    for r in report.per_pair:
        assert r.passed is False
        assert r.error is not None  # error message recorded


def test_runner_limit_truncates_pairs() -> None:
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    report = run_evals(
        client=client,
        golden_path=GOLDEN,
        model_fn=_perfect_model,
        limit=2,
    )
    assert report.total == 2
    assert report.passes == 2
    assert report.accuracy == 1.0


def test_runner_limit_zero_returns_empty_report() -> None:
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    report = run_evals(
        client=client,
        golden_path=GOLDEN,
        model_fn=_perfect_model,
        limit=0,
    )
    assert report.total == 0
    assert report.passes == 0
    assert report.accuracy == 0.0
    assert report.per_pair == []


def test_runner_aggregates_metrics() -> None:
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    report = run_evals(
        client=client,
        golden_path=GOLDEN,
        model_fn=_perfect_model,
    )
    assert report.avg_bytes_scanned > 0
    assert report.avg_latency_ms >= 0
    assert report.total_cost_usd >= 0


def test_runner_report_to_dict_round_trips() -> None:
    """Verify the dataclass-to-dict conversion preserves all fields for JSON serialization."""
    from mcp_bigquery_evals.evals.runner import report_to_dict

    client = FakeBigQueryClient.from_yaml(FIXTURE)
    report = run_evals(
        client=client,
        golden_path=GOLDEN,
        model_fn=_perfect_model,
        limit=1,
    )
    d = report_to_dict(report)
    assert d["accuracy"] == 1.0
    assert d["total"] == 1
    assert d["passes"] == 1
    assert isinstance(d["per_pair"], list)
    assert len(d["per_pair"]) == 1
    pair_dict = d["per_pair"][0]
    assert "id" in pair_dict
    assert "nl" in pair_dict
    assert "gold_sql" in pair_dict
    assert "predicted_sql" in pair_dict
    assert "passed" in pair_dict
    assert "error" in pair_dict


def test_runner_records_predicted_sql_even_when_failing() -> None:
    """Wrong SQL that runs but produces wrong result: predicted_sql is still captured."""
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    report = run_evals(
        client=client,
        golden_path=GOLDEN,
        model_fn=_broken_model,
    )
    for r in report.per_pair:
        assert r.predicted_sql == "SELECT 999 AS wrong"
