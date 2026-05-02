# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-DD

### Public surface (locked)

The following are the public contract of v0.1.0 and will follow semver going forward.
Breaking changes to any of these require a major-version bump.

- **MCP tool surface:** `list_datasets`, `list_tables`, `describe_table`, `sample_table`, `search_schema`, `estimate_cost`, `run_query` (signatures + return shapes)
- **`BigQueryError` codes:** `invalid_sql`, `table_not_found`, `permission_denied`, `unauthenticated`, `rate_limited`, `query_timeout`, `unknown`
- **`BigQueryError.to_dict()` shape:** `{"error": code, "message": str, "details": dict?}`
- **CLI:** `mcp-bigquery-evals serve`, `mcp-bigquery-evals evals run --model X --golden P --limit N --report P`
- **golden.yaml schema:** required keys `id`, `dataset`, `nl`, `gold_sql`; optional `tags`, `verified`
- **Eval JSON report shape:** `EvalReport` dataclass fields (model, generated_at, accuracy, total, passes, gold_errors, avg_bytes_scanned, avg_latency_ms, total_cost_usd, per_pair[])
- **Shields.io badge JSON shape:** `{schemaVersion, label, message, color}` per https://shields.io/badges/endpoint-badge

### Added (initial release)

- 7 read-only MCP tools for BigQuery exploration via stdio
- Mandatory dry-run cost cap on `run_query` (default 100 MB scanned)
- Structured `BigQueryError` translation for `google.api_core.exceptions.*`
- `RealBigQueryClient` (production) and `FakeBigQueryClient` (in-memory, sqlite-backed)
- `BigQueryClient` Protocol seam for testability and future warehouse adapters
- Result-set-equivalence eval harness (Spider/BIRD methodology) with NaN, Decimal, ARRAY/STRUCT, bool/int handling
- `mcp-bigquery-evals evals run` CLI subcommand with Anthropic SDK adapter
- JSON report + shields.io endpoint badge writer
- 15 golden NL-to-SQL pairs against `bigquery-public-data.samples` / `.stackoverflow` / `.usa_names` (UNVERIFIED at release; user verifies before publishing accuracy claims)
- GitHub Actions: ruff/mypy/pytest CI on every PR; nightly evals on `main` push that auto-commits the badge
- Documentation: README quickstart, Claude Desktop setup guide, architecture overview, eval harness walkthrough
- PEP 561 `py.typed` marker - package ships type information to consumers

### Known limitations (planned for 0.1.x / 0.2.x)

- N+1 round trips in `list_datasets` / `list_tables` (will batch concurrently in 0.1.x)
- No global cost cap env var (per-call only); a `MCP_BIGQUERY_MAX_BYTES_SCANNED` env var is on the 0.1.x roadmap
- Multi-warehouse adapters (Snowflake, Postgres) - out of scope for v1; planned as separate package `nl2sql-evals`
