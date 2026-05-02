from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.estimate_cost import estimate_cost

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_estimate_cost_returns_bytes_and_usd():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = estimate_cost(client, "SELECT * FROM `analytics.users`")
    assert "bytes_scanned" in result
    assert "estimated_usd" in result
    assert result["bytes_scanned"] > 0
    assert result["estimated_usd"] >= 0
