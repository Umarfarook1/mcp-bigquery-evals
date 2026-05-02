from mcp_bigquery_evals.evals.anthropic_model import _strip_markdown_fences


def test_strip_no_fences() -> None:
    assert _strip_markdown_fences("SELECT 1") == "SELECT 1"


def test_strip_sql_fence() -> None:
    text = "```sql\nSELECT * FROM users\n```"
    assert _strip_markdown_fences(text).strip() == "SELECT * FROM users"


def test_strip_bare_fence() -> None:
    text = "```\nSELECT 1\n```"
    assert _strip_markdown_fences(text).strip() == "SELECT 1"


def test_strip_uppercase_sql_fence() -> None:
    text = "```SQL\nSELECT 1\n```"
    assert _strip_markdown_fences(text).strip() == "SELECT 1"


def test_strip_only_opening_fence() -> None:
    text = "```sql\nSELECT 1"
    assert _strip_markdown_fences(text).strip() == "SELECT 1"


def test_strip_only_closing_fence() -> None:
    text = "SELECT 1\n```"
    assert _strip_markdown_fences(text).strip() == "SELECT 1"


def test_strip_preserves_inner_backticks() -> None:
    """Backticks INSIDE the SQL (e.g. table refs) must NOT be stripped."""
    text = "```sql\nSELECT * FROM `analytics.users`\n```"
    assert _strip_markdown_fences(text).strip() == "SELECT * FROM `analytics.users`"
