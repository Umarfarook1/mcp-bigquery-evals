import json
from pathlib import Path

from mcp_bigquery_evals.evals.report import write_badge, write_report
from mcp_bigquery_evals.evals.runner import EvalReport, PairResult


def _sample_report(accuracy: float = 0.74) -> EvalReport:
    return EvalReport(
        accuracy=accuracy,
        total=50,
        passes=int(round(accuracy * 50)),
        gold_errors=0,
        avg_bytes_scanned=12_000_000,
        avg_latency_ms=1_200,
        total_cost_usd=0.0034,
        per_pair=[
            PairResult(
                id=1,
                nl="...",
                dataset="x",
                gold_sql="...",
                predicted_sql="...",
                passed=True,
                error=None,
                bytes_scanned=10_000_000,
                cost_usd=0.00005,
                latency_ms=1100,
                gold_errored=False,
            )
        ],
    )


def test_write_report_creates_json(tmp_path: Path) -> None:
    out = tmp_path / "r.json"
    write_report(_sample_report(), out, model_id="claude-haiku-4-5")
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["model"] == "claude-haiku-4-5"
    assert data["accuracy"] == 0.74
    assert data["total"] == 50
    assert "per_pair" in data
    assert "generated_at" in data
    # Timestamp should be ISO 8601 with timezone
    assert "T" in data["generated_at"]


def test_write_report_creates_parent_directory(tmp_path: Path) -> None:
    """write_report must mkdir -p its parent directory."""
    out = tmp_path / "nested" / "subdir" / "r.json"
    write_report(_sample_report(), out, model_id="x")
    assert out.exists()


def test_write_badge_creates_shields_endpoint_json(tmp_path: Path) -> None:
    out = tmp_path / "badge.json"
    write_badge(_sample_report(), out, model_id="claude-haiku-4-5")
    data = json.loads(out.read_text())
    assert data["schemaVersion"] == 1
    assert "claude-haiku-4-5" in data["label"] or "accuracy" in data["label"].lower()
    assert "74%" in data["message"]
    assert data["color"] in {"red", "orange", "yellow", "green", "brightgreen"}


def test_write_badge_creates_parent_directory(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "badge.json"
    write_badge(_sample_report(), out, model_id="x")
    assert out.exists()


def test_badge_color_thresholds(tmp_path: Path) -> None:
    """Color buckets: <40% red, <60% orange, <75% yellow, <90% green, ≥90% brightgreen."""
    cases = [
        (0.10, "red"),
        (0.39, "red"),
        (0.40, "orange"),
        (0.59, "orange"),
        (0.60, "yellow"),
        (0.74, "yellow"),
        (0.75, "green"),
        (0.89, "green"),
        (0.90, "brightgreen"),
        (1.00, "brightgreen"),
    ]
    for acc, expected in cases:
        out = tmp_path / f"b_{int(acc * 100)}.json"
        report = _sample_report(accuracy=acc)
        write_badge(report, out, model_id="x")
        data = json.loads(out.read_text())
        assert data["color"] == expected, f"acc={acc}: expected {expected}, got {data['color']}"


def test_badge_zero_accuracy_is_red(tmp_path: Path) -> None:
    out = tmp_path / "b.json"
    write_badge(_sample_report(accuracy=0.0), out, model_id="x")
    data = json.loads(out.read_text())
    assert data["color"] == "red"
    assert data["message"] == "0%"


def test_badge_perfect_accuracy_is_brightgreen(tmp_path: Path) -> None:
    out = tmp_path / "b.json"
    write_badge(_sample_report(accuracy=1.0), out, model_id="x")
    data = json.loads(out.read_text())
    assert data["color"] == "brightgreen"
    assert data["message"] == "100%"


def test_badge_label_includes_model_id(tmp_path: Path) -> None:
    out = tmp_path / "b.json"
    write_badge(_sample_report(), out, model_id="claude-sonnet-4-6")
    data = json.loads(out.read_text())
    assert "claude-sonnet-4-6" in data["label"]
