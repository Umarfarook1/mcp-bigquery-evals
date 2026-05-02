from mcp_bigquery_evals.bq.types import DryRunResult
from mcp_bigquery_evals.guardrails import check_cost_cap, format_bytes


def test_format_bytes_units():
    assert format_bytes(0) == "0 B"
    assert format_bytes(500) == "500 B"
    assert format_bytes(2048) == "2.0 KB"
    assert format_bytes(5 * 1024 * 1024) == "5.0 MB"
    assert format_bytes(int(1.5 * 1024 * 1024 * 1024)) == "1.5 GB"


def test_check_cost_cap_under_limit_returns_none():
    dr = DryRunResult(bytes_scanned=1_000_000, estimated_usd=0.000005)
    assert check_cost_cap(dr, max_bytes_scanned=100_000_000) is None


def test_check_cost_cap_over_limit_returns_error_dict():
    dr = DryRunResult(bytes_scanned=1_500_000_000, estimated_usd=0.0075)
    err = check_cost_cap(dr, max_bytes_scanned=100_000_000)
    assert err is not None
    assert err["error"] == "cost_cap_exceeded"
    assert err["would_scan"] == "1.4 GB"
    assert err["cap"] == "95.4 MB"
    assert err["estimated_usd"] == 0.0075
    assert "narrow your WHERE clause" in err["hint"]
