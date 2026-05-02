from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.schema_search import search_schema

FIXTURE = Path(__file__).parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_search_finds_user_id_for_term_userid():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    hits = search_schema(client, "userid")
    top = hits[0]
    assert top["table"] == "analytics.users"
    assert top["column"] == "user_id"
    assert top["similarity"] >= 80


def test_search_returns_sorted_descending_by_similarity():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    hits = search_schema(client, "country")
    sims = [h["similarity"] for h in hits]
    assert sims == sorted(sims, reverse=True)


def test_search_caps_at_default_limit():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    hits = search_schema(client, "x")
    assert len(hits) <= 10
