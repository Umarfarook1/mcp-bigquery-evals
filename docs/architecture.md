# Architecture

This document explains the design decisions behind `mcp-bigquery-evals` v1. For the original design spec, see [`superpowers/specs/2026-05-02-bq-nl2sql-mcp-design.md`](superpowers/specs/2026-05-02-bq-nl2sql-mcp-design.md).

## High-level shape

```
Claude Desktop ⇄ stdio MCP ⇄ mcp-bigquery-evals server
                                       │
                              7 MCP tool handlers
                                       │
                              BigQueryClient Protocol
                              ┌────────┴────────┐
                              │                 │
                          RealBQ             FakeBQ
                  (google-cloud-bigquery)  (sqlite + yaml fixture)
```

## Key decisions

### 1. The single seam: `BigQueryClient` Protocol

Every tool handler depends on the `BigQueryClient` Protocol (PEP 544). This decouples tool logic from BQ specifics and lets us:
- Develop and test the entire server without GCP credentials (against `FakeBigQueryClient`)
- Swap implementations later (Snowflake? Postgres? new MCP server)
- Translate API exceptions at the seam (see `bq/errors.py`) instead of leaking them through the tool layer

### 2. Mandatory dry-run before every `run_query`

`run_query(sql, max_bytes_scanned=100MB)` always dry-runs first. If the estimate exceeds the cap, the call returns a structured error before any data is scanned. This eliminates the worst failure mode (an agent kicking off a 1 TB scan).

The cap is per-call; the agent may explicitly raise it. There is no global daily limit in v1 (deferred to v1.1).

The `dry_run_result` is threaded through to `execute()` so a single dry-run serves both cap-checking and cost-reporting - no double round-trip to the BQ API.

### 3. Read-only by design

No `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`. The blast radius of an LLM mistake is bounded to scanning bytes, not mutating data. Write operations are explicitly out of scope for v1.

### 4. No internal LLM calls in the server runtime

The MCP server is deterministic. It does not call Claude, GPT, or any other LLM internally. The consumer (Claude Desktop) IS the LLM - it can summarize SQL, explain results, and reason about errors itself. Putting an LLM inside an MCP server whose only consumer is an LLM is a design smell.

The eval harness is a separate process (`mcp-bigquery-evals evals run`) and DOES call Anthropic's API to generate predicted SQL. It does NOT touch the MCP server runtime.

### 5. Result-set equivalence for evals

We chose result-set equivalence (Spider/BIRD methodology) over LLM-as-judge:
- Deterministic
- Single number (`passes / total`) for the README badge
- Respected by the senior-engineer audience (Hamel Husain has written explicitly against LLM-as-judge for SQL)
- Costs real BQ scans, but small datasets (`bigquery-public-data.samples`) keep this manageable

The comparator (`evals/compare.py`) handles BQ-realistic data types: NaN equality, NULL equality, Decimal tolerance, ARRAY/STRUCT recursion, and float tolerance via `math.isclose`. The bool-vs-int distinction is preserved (Python's `True == 1` is misleading for evals).

### 6. Structured error contract

All BigQueryClient methods that can raise translate `google.api_core.exceptions.*` into `BigQueryError` with one of 7 stable codes: `invalid_sql`, `table_not_found`, `permission_denied`, `unauthenticated`, `rate_limited`, `query_timeout`, `unknown`. The MCP tool layer catches `BigQueryError` and returns its `to_dict()` shape. This means an LLM agent receives a structured signal it can reason about (e.g., suggest re-authenticating on `unauthenticated`) instead of a stack trace.

### 7. CLI subcommands share the same binary

`mcp-bigquery-evals serve` (default) runs the MCP server. `mcp-bigquery-evals evals run` runs the eval harness. Both share `build_client()` so the BQ wiring is consistent.

## Module map

| Path | Responsibility |
|---|---|
| `src/mcp_bigquery_evals/__main__.py` | Module entry → CLI |
| `cli.py` | argparse with `serve` and `evals run` subcommands |
| `server.py` | Construct FastMCP, register 7 tools, wire BigQueryClient |
| `bq/protocol.py` | `BigQueryClient` Protocol |
| `bq/types.py` | Domain dataclasses |
| `bq/real.py` | `RealBigQueryClient` (google-cloud-bigquery) |
| `bq/fake.py` | `FakeBigQueryClient` (sqlite-backed, yaml-loaded) |
| `bq/errors.py` | API exception → `BigQueryError` translation |
| `tools/` | One file per MCP tool |
| `guardrails.py` | Cost-cap logic |
| `schema_search.py` | Fuzzy column matching (rapidfuzz) |
| `evals/runner.py` | Eval orchestrator |
| `evals/compare.py` | Result-set equivalence |
| `evals/prompt.py` | Schema context + system/user prompt |
| `evals/anthropic_model.py` | Anthropic SDK adapter |
| `evals/report.py` | JSON report + shields.io badge |

## What's intentionally not here

- A semantic layer / metric definitions (a separate concern; spec §3 non-goal)
- Multi-warehouse support (one MCP per warehouse is the right pattern; don't build leaky abstractions)
- Web UI or dashboard
- An LLM-as-judge path in evals
- Write operations of any kind
