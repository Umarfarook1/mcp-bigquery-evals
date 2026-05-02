# Plan B Carry-Over Notes (from Plan A final review)

These items were identified during the Plan A final code review (2026-05-02) but deferred to Plan B because they are best resolved when `RealBigQueryClient` is written or when CI is added.

## Bake into Plan B's task list

### 1. Translate `RealBigQueryClient` exceptions into structured errors

**Where:** new `src/mcp_bigquery_evals/bq/real.py` (Plan B Task TBD)
**Problem:** `FakeBigQueryClient.dry_run()` silently returns `bytes_scanned=0` for unknown tables; `RealBigQueryClient.dry_run()` will raise `google.api_core.exceptions.BadRequest` (invalid SQL) and `google.api_core.exceptions.NotFound` (unknown table). Neither is `ValueError`, so `run_query`/`estimate_cost`/`list_tables` will leak unstructured exceptions to MCP.
**Fix:** establish the contract that all `BigQueryClient` Protocol methods translate API exceptions into structured return values. Either document this in `protocol.py` and make `RealBigQueryClient` conform, or add an exception-catching layer in the tool handlers.

### 2. Eliminate the double dry-run inside `run_query`

**Where:** `src/mcp_bigquery_evals/tools/run_query.py` and `BigQueryClient` Protocol
**Problem:** `run_query` calls `client.dry_run(sql)` for cap-checking. Then `client.execute(sql)` (in FakeBigQueryClient) calls `self.dry_run(sql)` again to populate `QueryResult.bytes_scanned`/`cost_usd`. Two dry-runs per query. Free in the fake, but `RealBigQueryClient.dry_run()` is a network round trip - doubles latency and counts against quota.
**Fix:** refactor so that `BigQueryClient.execute(sql)` accepts (or returns) the dry-run result without re-fetching. Options: change `execute()` signature to take `DryRunResult`, or restructure `run_query` to compute the cost figures from the already-cached dry-run.

### 3. Add `close()` to `BigQueryClient` Protocol

**Where:** `src/mcp_bigquery_evals/bq/protocol.py` and `server.py`
**Problem:** `FakeBigQueryClient` already has `close()` (closes sqlite). `RealBigQueryClient` will wrap `google.cloud.bigquery.Client` which should also be closed. Currently neither close is in the Protocol; the server doesn't call it; cleanup relies on `__del__`.
**Fix:** add `close()` to the Protocol and wire `build_server()` (or the CLI's `_cmd_serve`) to call it on shutdown - context manager pattern is cleanest.

### 4. Lazy-import `FakeBigQueryClient` in `build_client`

**Where:** `src/mcp_bigquery_evals/server.py`
**Problem:** Top-level `from mcp_bigquery_evals.bq.fake import FakeBigQueryClient` means the `[bq]` optional extra is meaningless - when `RealBigQueryClient` is added, `google-cloud-bigquery` will be imported even when the user only wants the fake.
**Fix:** move both the fake and real imports inside `build_client()` so each is only loaded when its branch is taken.

## Don't fix in Plan B (intentional v1 design)

- `search_schema` returns hits for every column with no relevance cutoff - by design; let the agent decide. Document in tool docstring.
- `describe_table` doesn't include sample rows - by design; agent calls `sample_table` separately.
- No internal LLM calls in the server - by design (spec §3 non-goal).

## Test directory cleanup (low priority)

- `tests/integration/test_server_smoke.py` has two `# type: ignore[return-value]` comments that should be `# type: ignore[no-any-return]` if mypy ever covers tests. Currently silent because mypy excludes tests.
- Test functions are missing `-> None` annotations. Cosmetic.
