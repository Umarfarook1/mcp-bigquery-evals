"""Prompt builder for the eval runner.

Composes a schema context (textual dump of tables + columns + descriptions)
and a per-pair user message asking the model to produce a single SQL query.
"""

from __future__ import annotations

from mcp_bigquery_evals.bq.protocol import BigQueryClient

_SYSTEM_PROMPT = """\
You are a BigQuery SQL writer. Given a natural-language question and a database
schema, produce ONE valid Standard SQL query that answers the question against
that BigQuery schema.

Rules:
- Output ONLY the SQL query. No explanation, no markdown fences, no surrounding text.
- Use BigQuery Standard SQL syntax (backticked `dataset.table` identifiers).
- Use only tables and columns from the provided schema.
- Prefer simple, readable queries over clever ones.
- If the question is ambiguous, make the most natural interpretation and proceed.
"""


def build_schema_context(client: BigQueryClient, dataset_id: str) -> str:
    """Format every table in the dataset as a textual schema block.

    Returns "" if the dataset has no tables.
    """
    blocks: list[str] = []
    for table in client.list_tables(dataset_id):
        schema = client.get_table(table.id)
        col_lines = [
            f"  - {c.name} ({c.type})" + (f" - {c.description}" if c.description else "")
            for c in schema.columns
        ]
        block = f"Table `{table.id}` ({table.row_count} rows):\n" + "\n".join(col_lines)
        blocks.append(block)
    return "\n\n".join(blocks)


def build_prompt(
    client: BigQueryClient,
    dataset_id: str,
    nl: str,
) -> dict[str, str]:
    """Returns {'system': ..., 'user': ...} ready for an Anthropic Messages call."""
    schema = build_schema_context(client, dataset_id)
    user = f"Schema (dataset `{dataset_id}`):\n\n{schema}\n\nQuestion: {nl}\n\nSQL:"
    return {"system": _SYSTEM_PROMPT, "user": user}
