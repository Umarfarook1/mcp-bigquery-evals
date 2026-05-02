# mcp-bigquery-evals

> An MCP server for BigQuery exploration with cost guardrails and a built-in NL→SQL eval harness.

[![PyPI](https://img.shields.io/pypi/v/mcp-bigquery-evals.svg)](https://pypi.org/project/mcp-bigquery-evals/)
[![accuracy](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Umarfarook1/mcp-bigquery-evals/main/evals/badge.json)](#eval-harness)
[![CI](https://github.com/Umarfarook1/mcp-bigquery-evals/actions/workflows/ci.yml/badge.svg)](https://github.com/Umarfarook1/mcp-bigquery-evals/actions/workflows/ci.yml)

## What it is

A [Model Context Protocol](https://modelcontextprotocol.io/) server that lets Claude Desktop, Cursor, and Claude Code explore and query a BigQuery warehouse safely.

- **7 read-only tools** for warehouse discovery + querying
- **Mandatory dry-run cost cap** on every `run_query` (default 100 MB scanned, ≈ $0.0005)
- **Built-in eval harness** with result-set-equivalence methodology — every release ships an accuracy number, not a vibe

Two clients ship in the box: `RealBigQueryClient` (production) and `FakeBigQueryClient` (in-memory, sqlite-backed; for dev and CI without GCP credentials).

## Quickstart (5 minutes)

### 1. Install

```bash
uvx mcp-bigquery-evals --help
```

(First run takes ~30s while uv fetches dependencies; subsequent runs are instant from the local cache.)

(Or `pip install mcp-bigquery-evals` if you prefer.)

### 2. Authenticate to GCP

```bash
gcloud auth application-default login
```

### 3. Add to `claude_desktop_config.json`

Open Claude Desktop → Settings → Developer → Edit Config, then add:

```json
{
  "mcpServers": {
    "bigquery": {
      "command": "uvx",
      "args": ["mcp-bigquery-evals", "serve"],
      "env": {
        "BIGQUERY_PROJECT": "YOUR_GCP_PROJECT_ID_HERE"
      }
    }
  }
}
```

Restart Claude Desktop. You should see "bigquery" with 7 tools in the MCP indicator.

### 4. Try it

Ask Claude:
> "Using the bigquery tool, find the top 5 most-viewed Stack Overflow questions tagged 'python'."

Claude will use `list_datasets` → `list_tables` → `describe_table` → `run_query` to explore and answer. Every `run_query` is dry-run-cost-capped before execution.

## The 7 tools

| Tool | Purpose |
|---|---|
| `list_datasets` | List all datasets in your GCP project |
| `list_tables(dataset_id)` | List tables in a dataset |
| `describe_table(table_id)` | Schema + row count + size |
| `sample_table(table_id, n=5)` | Up to n sample rows |
| `search_schema(term)` | Fuzzy-match a term against all column names |
| `estimate_cost(sql)` | Free dry-run; returns bytes_scanned + estimated USD |
| `run_query(sql, max_bytes_scanned=100MB)` | Dry-run, refuse if over cap, then execute |

All tools are read-only. There are no write operations in v1 by design. See [`docs/architecture.md`](docs/architecture.md).

## Cost guardrails

Every `run_query` call dry-runs first (free) before execution. If the dry-run estimate exceeds `max_bytes_scanned` (default 100 MB), the call returns a structured error rather than running:

```json
{
  "error": "cost_cap_exceeded",
  "would_scan": "1.4 GB",
  "cap": "100.0 MB",
  "estimated_usd": 0.007,
  "hint": "narrow your WHERE clause or pass max_bytes_scanned=1500000000 to override"
}
```

The agent can read the structured error and self-correct (narrow the WHERE clause, raise the cap explicitly, etc.).

## Structured BigQuery errors

When something goes wrong against real BigQuery, the response is a stable code an agent can reason about:

| Code | When |
|---|---|
| `invalid_sql` | SQL syntax error |
| `table_not_found` | Referenced table doesn't exist |
| `permission_denied` | IAM 403 |
| `unauthenticated` | Credentials missing or expired (run `gcloud auth application-default login`) |
| `rate_limited` | Quota or rate limit hit |
| `query_timeout` | Query exceeded its execution timeout |
| `unknown` | Catch-all for anything else |

## Eval harness

Every release runs a result-set-equivalence eval suite against `bigquery-public-data` and updates the accuracy badge above. Run locally:

```bash
mcp-bigquery-evals evals run --model claude-haiku-4-5
```

See [`docs/how_evals_work.md`](docs/how_evals_work.md) for the methodology, golden pairs format, and how to add your own.

## Why this exists

There are a few BigQuery MCP servers floating around. This one is different in three ways:

1. **Cost guardrails** are mandatory and surfaced as structured errors agents can act on. Most don't have them.
2. **Result-set-equivalence evals** ship in the box, with a live accuracy badge in this README. Agent quality is measurable, not assumed.
3. **Read-only by design** — no INSERT/UPDATE/DELETE. The blast radius of an LLM mistake is bounded to scanning bytes, not mutating data.

## Development

```bash
git clone https://github.com/Umarfarook1/mcp-bigquery-evals
cd mcp-bigquery-evals
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                    # unit tests (no GCP needed)
pytest -m bq              # real-BQ integration tests (needs GCP)
pytest -m live            # end-to-end with real model + real BQ
```

## License

MIT — see [`LICENSE`](LICENSE).

## Contributing

Issues and PRs welcome. Especially valuable:
- More golden NL→SQL pairs (hand-verified, against bigquery-public-data)
- Improved prompts (with eval numbers showing the change moves the accuracy badge)
- Bug reports with reproduction steps
