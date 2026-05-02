<div align="center">

# mcp-bigquery-evals

**The BigQuery MCP server with mandatory cost guardrails and a measurable accuracy number.**

[![PyPI](https://img.shields.io/pypi/v/mcp-bigquery-evals.svg?color=blue)](https://pypi.org/project/mcp-bigquery-evals/)
[![accuracy](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Umarfarook1/mcp-bigquery-evals/main/evals/badge.json)](#eval-harness)
[![CI](https://github.com/Umarfarook1/mcp-bigquery-evals/actions/workflows/ci.yml/badge.svg)](https://github.com/Umarfarook1/mcp-bigquery-evals/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/mcp-bigquery-evals.svg)](https://pypi.org/project/mcp-bigquery-evals/)
[![License](https://img.shields.io/pypi/l/mcp-bigquery-evals.svg)](LICENSE)

`uvx mcp-bigquery-evals` &nbsp;·&nbsp; works with Claude Desktop, Cursor, Claude Code &nbsp;·&nbsp; v0.1.0

</div>

---

## Why use this over the other BigQuery MCPs

| | Most BQ MCPs | `mcp-bigquery-evals` |
|---|---|---|
| Cost guardrails | none | **mandatory** dry-run before every query, refuses if over cap |
| Quality signal | "trust me" | **live accuracy badge**, recomputed every release |
| Write operations | usually enabled | **disabled by design** (read-only) |
| Errors when things break | raw API exceptions | **7 stable error codes** an agent can switch on |
| Local dev without GCP | impossible | **in-memory sqlite-backed fake** ships in the box |

## What ships in the box

- **7 read-only MCP tools** for warehouse discovery and querying
- **Mandatory dry-run cost cap** on every `run_query` (default 100 MB scanned, about $0.0005 per query)
- **Result-set-equivalence eval harness** (Spider/BIRD methodology) with a live accuracy badge in this README
- **Structured BigQuery errors** with 7 stable codes (`invalid_sql`, `table_not_found`, `permission_denied`, `unauthenticated`, `rate_limited`, `query_timeout`, `unknown`)
- **Two BigQueryClient implementations**: `RealBigQueryClient` (production, wraps `google-cloud-bigquery`) and `FakeBigQueryClient` (in-memory, sqlite-backed, for dev and CI without GCP credentials)

## Quickstart (5 minutes)

### 1. Install

```bash
uvx mcp-bigquery-evals --help
```

First run takes about 30s while `uv` fetches dependencies; subsequent runs are instant from the local cache. Plain `pip install mcp-bigquery-evals` also works.

### 2. Authenticate to GCP

```bash
gcloud auth application-default login
```

### 3. Wire into Claude Desktop

Open Claude Desktop, then Settings, then Developer, then Edit Config. Add:

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

Restart Claude Desktop. The MCP indicator should show "bigquery" with 7 tools.

### 4. Try it

> Using the bigquery tool, find the top 5 most-viewed Stack Overflow questions tagged 'python'.

Claude chains `list_datasets`, `list_tables`, `describe_table`, `run_query` to answer. Every `run_query` is dry-run-cost-capped before execution.

Detailed setup, troubleshooting, and the alternative `pip` install path live in [`docs/claude_desktop_setup.md`](docs/claude_desktop_setup.md).

## The 7 tools

| Tool | Purpose |
|---|---|
| `list_datasets()` | List all datasets in your GCP project |
| `list_tables(dataset_id)` | List tables in a dataset |
| `describe_table(table_id)` | Schema, row count, size |
| `sample_table(table_id, n=5)` | Up to n sample rows |
| `search_schema(term)` | Fuzzy-match a term against all column names |
| `estimate_cost(sql)` | Free dry-run; returns bytes_scanned and estimated USD |
| `run_query(sql, max_bytes_scanned=100MB)` | Dry-run, refuse if over cap, then execute |

All tools are read-only. There are no write operations in v1 by design. See [`docs/architecture.md`](docs/architecture.md) for the design rationale.

## Cost guardrails

Every `run_query` call dry-runs first (free) before execution. If the dry-run estimate exceeds `max_bytes_scanned`, the call returns a structured error rather than burning bytes:

```json
{
  "error": "cost_cap_exceeded",
  "would_scan": "1.4 GB",
  "cap": "100.0 MB",
  "estimated_usd": 0.007,
  "hint": "narrow your WHERE clause or pass max_bytes_scanned=1500000000 to override"
}
```

The agent reads the structured error and self-corrects (narrows the WHERE clause, raises the cap explicitly, picks a different table).

## Eval harness

Every release runs a result-set-equivalence eval suite against `bigquery-public-data` and updates the accuracy badge above. The methodology matches Spider and BIRD academic benchmarks: execute both gold and predicted SQL, compare result sets as multisets of rows (order-independent, with float tolerance, Decimal handling, NULL equality, NaN equality, ARRAY/STRUCT recursion, bool/int distinction).

Run locally:

```bash
mcp-bigquery-evals evals run --model claude-haiku-4-5
```

Full methodology, golden-pairs YAML format, and how to add your own pairs: [`docs/how_evals_work.md`](docs/how_evals_work.md).

## Development

```bash
git clone https://github.com/Umarfarook1/mcp-bigquery-evals
cd mcp-bigquery-evals
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

pytest                    # unit tests (no GCP needed; ~160 tests)
pytest -m bq              # real-BQ integration tests (needs GCP creds)
pytest -m live            # end-to-end with real model + real BQ
```

## Contributing

Issues and PRs welcome. Highest-leverage contributions:

1. **More verified golden NL-to-SQL pairs** against `bigquery-public-data`
2. **Prompt improvements** with before/after eval numbers showing the accuracy badge moved
3. **Bug reports** with minimum reproductions

## License

MIT, see [`LICENSE`](LICENSE).
