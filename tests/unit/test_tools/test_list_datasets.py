from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.list_datasets import list_datasets

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_list_datasets_returns_serializable_dicts():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = list_datasets(client)
    assert result == [
        {"id": "analytics", "location": "US", "description": "User and event data for the demo product."},
        {"id": "ops", "location": "US", "description": "Operational metrics."},
    ]
