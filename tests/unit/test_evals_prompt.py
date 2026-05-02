from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.evals.prompt import build_prompt, build_schema_context

FIXTURE = Path(__file__).parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_build_schema_context_includes_table_columns_and_types() -> None:
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    ctx = build_schema_context(client, dataset_id="analytics")
    assert "analytics.users" in ctx
    assert "user_id" in ctx
    assert "STRING" in ctx
    assert "Primary key" in ctx
    assert "analytics.events" in ctx


def test_build_schema_context_omits_other_datasets() -> None:
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    ctx = build_schema_context(client, dataset_id="analytics")
    assert "ops.daily_metrics" not in ctx


def test_build_schema_context_for_empty_dataset_returns_empty_string() -> None:
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    ctx = build_schema_context(client, dataset_id="nonexistent")
    assert ctx == ""


def test_build_prompt_returns_system_and_user_strings() -> None:
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    prompt = build_prompt(
        client,
        dataset_id="analytics",
        nl="How many users are there?",
    )
    assert "system" in prompt
    assert "user" in prompt
    assert "BigQuery" in prompt["system"]
    assert "How many users are there?" in prompt["user"]
    assert "analytics.users" in prompt["user"]


def test_build_prompt_instructs_model_to_return_sql_only() -> None:
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    prompt = build_prompt(client, dataset_id="analytics", nl="...")
    sys_lower = prompt["system"].lower()
    # The system prompt must instruct: SQL only, no explanation, no markdown.
    assert "only" in sys_lower or "no explanation" in sys_lower


def test_build_prompt_includes_schema_context_in_user_message() -> None:
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    prompt = build_prompt(client, dataset_id="analytics", nl="X?")
    assert "user_id (STRING)" in prompt["user"] or "user_id" in prompt["user"]
    # Make sure the question and schema are both in the user message
    assert "X?" in prompt["user"]
