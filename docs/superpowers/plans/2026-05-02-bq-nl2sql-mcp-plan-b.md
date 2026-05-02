# mcp-bigquery-evals — Plan B (RealBigQueryClient + Evals + Release) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the working stdio MCP server from Plan A to a publicly-shippable v1.0 — real BigQuery client, eval harness with live accuracy badge, CI, public README, PyPI release, `awesome-mcp-servers` listing, two blog posts.

**Architecture:** Build the real `BigQueryClient` Protocol implementation against `google-cloud-bigquery`, applying the four carry-over refinements identified in the Plan A final review (close() in Protocol, lazy imports, structured error translation, single dry-run). Build the eval harness as a CLI subcommand that uses the Anthropic SDK to generate SQL from natural language, executes both the gold and predicted SQL via the BigQueryClient, and compares result sets using Spider/BIRD-style multiset equality. Then wire CI, write the real README, publish to PyPI.

**Tech Stack additions over Plan A:** `google-cloud-bigquery>=3.20`, `anthropic>=0.40`, `python-dotenv>=1.0` (for local credentials in the eval CLI). Result-set comparison uses stdlib only (`collections.Counter` + `math.isclose`).

**Prerequisites before starting:**
- Personal GCP project with BigQuery API enabled (free; uses the 1 TB/month free tier on `bigquery-public-data`)
- `gcloud auth application-default login` completed locally
- Anthropic API key set as `ANTHROPIC_API_KEY` env var

These prerequisites only block tasks T9, T13, T15+ (anything that hits real BQ or Anthropic). Tasks T1-T8 can be done without them.

---

## File Structure (created/modified across all Plan B tasks)

```
mcp-bigquery-evals/
├── pyproject.toml                                  # T0 (deps), T22 (version + classifiers)
├── README.md                                       # T17 (rewrite)
├── .env.example                                    # T0
├── src/mcp_bigquery_evals/
│   ├── bq/
│   │   ├── protocol.py                             # T1 (add close())
│   │   ├── fake.py                                 # T1 (close already exists, no-op alignment)
│   │   ├── real.py                                 # T3, T4, T5 (new)
│   │   └── errors.py                               # T6 (new — error translation helpers)
│   ├── server.py                                   # T2 (lazy imports), T7 (single dry-run)
│   ├── tools/run_query.py                          # T7 (single dry-run refactor)
│   └── evals/
│       ├── __init__.py                             # T9
│       ├── golden_fake.yaml                        # T9 (small fixture for runner dev)
│       ├── golden.yaml                             # T15 (real pairs against bigquery-public-data)
│       ├── compare.py                              # T10 (multiset equality)
│       ├── prompt.py                               # T11 (model prompt template)
│       ├── runner.py                               # T12, T13 (orchestrator)
│       └── report.py                               # T14 (JSON + badge writer)
├── tests/
│   ├── unit/
│   │   ├── test_real_client.py                     # T3, T4, T5 (mock-based)
│   │   ├── test_real_client_errors.py              # T6
│   │   ├── test_dry_run_dedup.py                   # T7
│   │   ├── test_evals_compare.py                   # T10
│   │   ├── test_evals_prompt.py                    # T11
│   │   ├── test_evals_runner.py                    # T12 (against fake, mock model)
│   │   └── test_evals_report.py                    # T14
│   ├── integration/
│   │   ├── test_real_bq_smoke.py                   # T8 (real BQ; marked @pytest.mark.bq)
│   │   └── test_evals_real_smoke.py                # T16 (real BQ + real model; marked @pytest.mark.live)
│   └── fixtures/
│       └── golden_fake.yaml                        # T9 (test-only golden pairs against fake)
├── docs/
│   ├── superpowers/plans/                          # already populated
│   ├── claude_desktop_setup.md                     # T18
│   ├── architecture.md                             # T19
│   └── how_evals_work.md                           # T20
└── .github/workflows/
    ├── ci.yml                                      # T21
    └── evals.yml                                   # T22
```

---

## Task ordering rationale

The order below front-loads the carry-overs (T1-T2) before adding new code, then builds the real client (T3-T8), then builds the eval harness against the fake (T9-T14) so it's testable without GCP, then wires it to real BQ and Anthropic (T15-T16), then ships (T17-T26).

You can stop after T14 and have a working evals harness against the fake — useful for testing the comparator and runner. Resume T15+ when GCP is set up.

---

### Task 0: Add Plan B dependencies

**Files:**
- Modify: `pyproject.toml`
- Create: `.env.example`

- [ ] **Step 1: Add deps**

In `pyproject.toml`, add to `[project] dependencies`:
```toml
dependencies = [
    "mcp>=1.27.0",
    "rapidfuzz>=3.0",
    "pyyaml>=6.0",
    "google-cloud-bigquery>=3.20",
    "anthropic>=0.40",
    "python-dotenv>=1.0",
]
```

Update `[project.optional-dependencies]`:
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.6",
    "mypy>=1.10",
    "types-PyYAML>=6.0",
]
```

(Drop the `bq = [...]` extra — `google-cloud-bigquery` is now a runtime dep since the eval harness needs it; the lazy-import refactor in T2 means the import cost is paid only when the real path is taken at server startup, not when the fake is used.)

- [ ] **Step 2: Write `.env.example`**

```bash
# Copy to .env (gitignored) and fill in.
# These are read by the eval runner CLI; the MCP server does NOT read .env.
ANTHROPIC_API_KEY=sk-ant-...
BIGQUERY_PROJECT=my-personal-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

- [ ] **Step 3: Install + verify**

```bash
source .venv/Scripts/activate
pip install -e ".[dev]"
pytest -v 2>&1 | tail -3
ruff check src tests
mypy src
```

Expected: all 55 tests still pass, ruff and mypy clean.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .env.example
git commit -m "deps: add google-cloud-bigquery, anthropic, python-dotenv, polars for Plan B"
```

---

### Task 1: Add `close()` to BigQueryClient Protocol

**Files:**
- Modify: `src/mcp_bigquery_evals/bq/protocol.py`
- Modify: `src/mcp_bigquery_evals/bq/fake.py` (already has close(); just verify Protocol conformance)
- Modify: `tests/unit/test_fake_client.py`

- [ ] **Step 1: Append failing test**

Append to `tests/unit/test_fake_client.py`:
```python
def test_close_can_be_called_via_protocol(client: FakeBigQueryClient):
    """The Protocol must expose close() so generic shutdown code works against any impl."""
    bq_client: BigQueryClient = client  # widen to Protocol type
    bq_client.close()  # must not raise


def test_close_is_idempotent(client: FakeBigQueryClient):
    client.close()
    client.close()  # second call must not raise
```

- [ ] **Step 2: Run, verify the first test fails (Protocol doesn't have close())**

Run: `mypy tests/unit/test_fake_client.py`
Expected: `error: "BigQueryClient" has no attribute "close"`.

(The runtime test will pass because `FakeBigQueryClient.close()` exists, but mypy strict catches that the Protocol doesn't promise it.)

- [ ] **Step 3: Add `close()` to Protocol**

Update `src/mcp_bigquery_evals/bq/protocol.py` — add a method to the Protocol body:
```python
@runtime_checkable
class BigQueryClient(Protocol):
    """The single seam between the MCP server and BigQuery.

    Two implementations: RealBigQueryClient (google-cloud-bigquery)
    and FakeBigQueryClient (in-memory, yaml-loaded).
    """

    def list_datasets(self) -> list[Dataset]: ...

    def list_tables(self, dataset_id: str) -> list[Table]: ...

    def get_table(self, table_id: str) -> TableSchema: ...

    def sample_rows(self, table_id: str, n: int) -> list[dict[str, object]]: ...

    def dry_run(self, sql: str) -> DryRunResult: ...

    def execute(self, sql: str) -> QueryResult: ...

    def close(self) -> None:
        """Release any held resources (network connections, sqlite handles, etc.).

        Implementations must make this idempotent — calling close() twice is a no-op.
        """
        ...
```

- [ ] **Step 4: Make `FakeBigQueryClient.close()` idempotent**

In `src/mcp_bigquery_evals/bq/fake.py`, replace the existing `close()` with:
```python
def close(self) -> None:
    conn = getattr(self, "_conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        self._conn = None  # type: ignore[assignment]
```

(Setting `_conn = None` after close is the idempotency guarantee. The `__del__` at the bottom of the class doesn't need to change.)

- [ ] **Step 5: Verify tests pass**

```bash
pytest tests/unit/test_fake_client.py -v
mypy src tests/unit/test_fake_client.py 2>&1 | tail -3
```

Expected: all tests pass, mypy clean.

- [ ] **Step 6: Commit**

```bash
git add src/mcp_bigquery_evals/bq/protocol.py src/mcp_bigquery_evals/bq/fake.py tests/unit/test_fake_client.py
git commit -m "bq: add close() to BigQueryClient Protocol; make FakeBigQueryClient close idempotent"
```

---

### Task 2: Lazy-import FakeBigQueryClient in `server.py`

**Files:**
- Modify: `src/mcp_bigquery_evals/server.py`

- [ ] **Step 1: Verify the test still asserts what we want**

`tests/unit/test_tools/test_server.py` exercises `build_server()` end-to-end via the env var. The test sets `MCP_BIGQUERY_FAKE_FIXTURE` and calls `build_server()`. After this refactor, that path still works — fake is just imported lazily inside `build_client()` instead of at module top-level.

- [ ] **Step 2: Refactor `server.py`**

In `src/mcp_bigquery_evals/server.py`, REMOVE the top-level import of `FakeBigQueryClient`:
```python
# DELETE this line at the top of the file:
# from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
```

Then update `build_client()` to import lazily:
```python
def build_client() -> BigQueryClient:
    """Wire up the BigQueryClient based on env vars.

    - MCP_BIGQUERY_FAKE_FIXTURE set → FakeBigQueryClient.from_yaml(...)
    - otherwise → RealBigQueryClient with ADC + BIGQUERY_PROJECT
    """
    fake_path = os.environ.get("MCP_BIGQUERY_FAKE_FIXTURE")
    if fake_path:
        from mcp_bigquery_evals.bq.fake import FakeBigQueryClient

        return FakeBigQueryClient.from_yaml(Path(fake_path))

    project = os.environ.get("BIGQUERY_PROJECT")
    if not project:
        raise RuntimeError(
            "BIGQUERY_PROJECT env var is required (or set MCP_BIGQUERY_FAKE_FIXTURE for the fake)."
        )

    from mcp_bigquery_evals.bq.real import RealBigQueryClient

    return RealBigQueryClient(project=project)
```

(The `RealBigQueryClient` import will fail until T3 lands — that's fine; the test in T2 only exercises the fake path. The import is inside the conditional, so it only resolves at runtime when needed.)

- [ ] **Step 3: Verify**

```bash
pytest tests/unit/test_tools/test_server.py -v
pytest -v 2>&1 | tail -3
mypy src
ruff check src tests
```

Expected: all 55+ tests still pass, mypy + ruff clean.

- [ ] **Step 4: Commit**

```bash
git add src/mcp_bigquery_evals/server.py
git commit -m "server: lazy-import BQ client implementations so [bq] extra is meaningful"
```

---

### Task 3: RealBigQueryClient — list_datasets + list_tables (with mock-based tests)

**Files:**
- Create: `src/mcp_bigquery_evals/bq/real.py`
- Create: `tests/unit/test_real_client.py`

- [ ] **Step 1: Write failing tests (mock-based, no real BQ needed)**

`tests/unit/test_real_client.py`:
```python
"""Unit tests for RealBigQueryClient.

Uses unittest.mock to stub google.cloud.bigquery.Client so tests run without
GCP credentials. Real-BQ smoke tests live in tests/integration/test_real_bq_smoke.py.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mcp_bigquery_evals.bq.protocol import BigQueryClient
from mcp_bigquery_evals.bq.real import RealBigQueryClient


@pytest.fixture
def mock_bq() -> MagicMock:
    """A google.cloud.bigquery.Client mock pre-loaded with two datasets and two tables."""
    client = MagicMock()

    # list_datasets() returns iterable of DatasetListItem
    ds1 = MagicMock()
    ds1.dataset_id = "analytics"
    ds1.location = "US"
    ds1.full_dataset_id = "myproj:analytics"
    ds2 = MagicMock()
    ds2.dataset_id = "ops"
    ds2.location = "US"
    ds2.full_dataset_id = "myproj:ops"
    client.list_datasets.return_value = [ds1, ds2]

    # get_dataset() returns Dataset with description
    def _get_dataset(ref):
        ds = MagicMock()
        ds.dataset_id = ref.split(".")[-1] if isinstance(ref, str) else ref.dataset_id
        ds.description = f"description for {ds.dataset_id}"
        return ds
    client.get_dataset.side_effect = _get_dataset

    # list_tables() returns iterable of TableListItem
    def _list_tables(dataset_ref):
        ds_id = dataset_ref.split(".")[-1] if isinstance(dataset_ref, str) else dataset_ref.dataset_id
        if ds_id == "analytics":
            t1 = MagicMock()
            t1.table_id = "users"
            t1.full_table_id = "myproj:analytics.users"
            t2 = MagicMock()
            t2.table_id = "events"
            t2.full_table_id = "myproj:analytics.events"
            return [t1, t2]
        return []
    client.list_tables.side_effect = _list_tables

    # get_table() returns Table with row count + bytes + schema
    def _get_table(table_ref):
        t = MagicMock()
        t.table_id = "users"
        t.num_rows = 100
        t.num_bytes = 5000
        col = MagicMock()
        col.name = "user_id"
        col.field_type = "STRING"
        col.description = "Primary key."
        t.schema = [col]
        t.full_table_id = "myproj:analytics.users"
        return t
    client.get_table.side_effect = _get_table

    return client


@pytest.fixture
def real_client(mock_bq: MagicMock) -> RealBigQueryClient:
    return RealBigQueryClient(project="myproj", _client=mock_bq)


def test_implements_protocol(real_client: RealBigQueryClient):
    assert isinstance(real_client, BigQueryClient)


def test_list_datasets(real_client: RealBigQueryClient):
    datasets = real_client.list_datasets()
    ids = [d.id for d in datasets]
    assert ids == ["analytics", "ops"]
    assert datasets[0].location == "US"
    assert datasets[0].description == "description for analytics"


def test_list_tables_for_known_dataset(real_client: RealBigQueryClient):
    tables = real_client.list_tables("analytics")
    ids = [t.id for t in tables]
    assert ids == ["analytics.users", "analytics.events"]
    assert tables[0].row_count == 100
    assert tables[0].size_bytes == 5000


def test_list_tables_for_unknown_dataset_returns_empty(real_client: RealBigQueryClient):
    assert real_client.list_tables("nonexistent") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_real_client.py -v`
Expected: ImportError on `mcp_bigquery_evals.bq.real`.

- [ ] **Step 3: Implement `real.py` (list_datasets + list_tables only)**

`src/mcp_bigquery_evals/bq/real.py`:
```python
"""RealBigQueryClient — wraps google-cloud-bigquery.

Auth precedence:
1. GOOGLE_APPLICATION_CREDENTIALS env var → service-account JSON
2. Application Default Credentials (gcloud auth application-default login)

The wrapper exists to:
- Translate google.cloud.bigquery types into our domain types (bq/types.py)
- Translate google.api_core.exceptions into structured returns (see Task 6)
- Keep the BigQueryClient Protocol surface stable across fake and real impls.
"""
from __future__ import annotations

from typing import Any

from google.cloud import bigquery

from mcp_bigquery_evals.bq.types import (
    Column,
    Dataset,
    DryRunResult,
    QueryResult,
    Table,
    TableSchema,
)


class RealBigQueryClient:
    """Production BigQueryClient backed by google-cloud-bigquery."""

    def __init__(self, project: str, _client: Any | None = None) -> None:
        # _client is for testing; production callers leave it None.
        self._project = project
        self._client = _client if _client is not None else bigquery.Client(project=project)

    # ---- BigQueryClient Protocol ----

    def list_datasets(self) -> list[Dataset]:
        result: list[Dataset] = []
        for ds_item in self._client.list_datasets():
            ds = self._client.get_dataset(ds_item.dataset_id)
            result.append(
                Dataset(
                    id=ds.dataset_id,
                    location=getattr(ds, "location", "") or "",
                    description=getattr(ds, "description", None),
                )
            )
        return result

    def list_tables(self, dataset_id: str) -> list[Table]:
        result: list[Table] = []
        try:
            items = list(self._client.list_tables(dataset_id))
        except Exception:
            return []
        for t_item in items:
            t = self._client.get_table(f"{dataset_id}.{t_item.table_id}")
            result.append(
                Table(
                    id=f"{dataset_id}.{t_item.table_id}",
                    row_count=getattr(t, "num_rows", 0) or 0,
                    size_bytes=getattr(t, "num_bytes", 0) or 0,
                )
            )
        return result

    def get_table(self, table_id: str) -> TableSchema:
        raise NotImplementedError  # Task 4

    def sample_rows(self, table_id: str, n: int) -> list[dict[str, object]]:
        raise NotImplementedError  # Task 4

    def dry_run(self, sql: str) -> DryRunResult:
        raise NotImplementedError  # Task 5

    def execute(self, sql: str) -> QueryResult:
        raise NotImplementedError  # Task 5

    def close(self) -> None:
        client = getattr(self, "_client", None)
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
            self._client = None  # type: ignore[assignment]
```

(The `Any` for `_client` is intentional — typing it as `bigquery.Client` would force test mocks to satisfy the full BQ client interface. We trust the runtime duck-typing here since the test fixtures already validate behavior.)

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_real_client.py -v
mypy src
ruff check src tests
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/bq/real.py tests/unit/test_real_client.py
git commit -m "bq(real): add RealBigQueryClient with list_datasets and list_tables"
```

---

### Task 4: RealBigQueryClient — get_table + sample_rows

**Files:**
- Modify: `src/mcp_bigquery_evals/bq/real.py`
- Modify: `tests/unit/test_real_client.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/test_real_client.py`:
```python
def test_get_table_returns_schema(real_client: RealBigQueryClient):
    schema = real_client.get_table("analytics.users")
    assert schema.table.id == "analytics.users"
    assert schema.table.row_count == 100
    assert schema.columns[0].name == "user_id"
    assert schema.columns[0].type == "STRING"
    assert schema.columns[0].description == "Primary key."


def test_sample_rows_returns_dicts(mock_bq: MagicMock):
    """sample_rows uses list_rows() which returns RowIterator yielding Row objects."""
    # Configure mock to return 3 rows
    row_a = MagicMock()
    row_a.items.return_value = [("user_id", "u1"), ("email", "alice@example.com")]
    row_b = MagicMock()
    row_b.items.return_value = [("user_id", "u2"), ("email", "bob@example.com")]
    row_c = MagicMock()
    row_c.items.return_value = [("user_id", "u3"), ("email", "carol@example.com")]
    mock_bq.list_rows.return_value = [row_a, row_b, row_c]

    client = RealBigQueryClient(project="myproj", _client=mock_bq)
    rows = client.sample_rows("analytics.users", n=3)
    assert len(rows) == 3
    assert rows[0] == {"user_id": "u1", "email": "alice@example.com"}
    mock_bq.list_rows.assert_called_once_with("analytics.users", max_results=3)


def test_sample_rows_clamps_negative_n(mock_bq: MagicMock):
    mock_bq.list_rows.return_value = []
    client = RealBigQueryClient(project="myproj", _client=mock_bq)
    rows = client.sample_rows("analytics.users", n=-5)
    assert rows == []
    mock_bq.list_rows.assert_called_once_with("analytics.users", max_results=0)
```

- [ ] **Step 2: Run, verify they fail**

Run: `pytest tests/unit/test_real_client.py -v -k "get_table or sample_rows"`
Expected: 3 failures with NotImplementedError.

- [ ] **Step 3: Implement `get_table` and `sample_rows`**

In `src/mcp_bigquery_evals/bq/real.py`, replace the two stub bodies:
```python
def get_table(self, table_id: str) -> TableSchema:
    t = self._client.get_table(table_id)
    columns = [
        Column(
            name=field.name,
            type=field.field_type,
            description=getattr(field, "description", None),
        )
        for field in t.schema
    ]
    return TableSchema(
        table=Table(
            id=table_id,
            row_count=getattr(t, "num_rows", 0) or 0,
            size_bytes=getattr(t, "num_bytes", 0) or 0,
        ),
        columns=columns,
    )

def sample_rows(self, table_id: str, n: int) -> list[dict[str, object]]:
    n = max(0, n)
    rows_iter = self._client.list_rows(table_id, max_results=n)
    return [dict(row.items()) for row in rows_iter]
```

- [ ] **Step 4: Verify**

```bash
pytest tests/unit/test_real_client.py -v
mypy src
ruff check src tests
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/bq/real.py tests/unit/test_real_client.py
git commit -m "bq(real): implement get_table and sample_rows"
```

---

### Task 5: RealBigQueryClient — dry_run + execute (raw, no error translation yet)

**Files:**
- Modify: `src/mcp_bigquery_evals/bq/real.py`
- Modify: `tests/unit/test_real_client.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/test_real_client.py`:
```python
def test_dry_run_returns_estimate(mock_bq: MagicMock):
    job = MagicMock()
    job.total_bytes_processed = 1_000_000_000  # 1 GB
    mock_bq.query.return_value = job
    client = RealBigQueryClient(project="myproj", _client=mock_bq)

    result = client.dry_run("SELECT * FROM `analytics.users`")
    assert result.bytes_scanned == 1_000_000_000
    # 1 GB / (1 TB) * $5 = $0.00488...
    assert 0.004 < result.estimated_usd < 0.006

    # Verify the dry-run flag was set
    call = mock_bq.query.call_args
    job_config = call.kwargs.get("job_config") or call.args[1]
    assert job_config.dry_run is True
    assert job_config.use_query_cache is False


def test_execute_returns_rows(mock_bq: MagicMock):
    job = MagicMock()
    row1 = MagicMock()
    row1.items.return_value = [("n", 5)]
    job.result.return_value = [row1]
    job.total_bytes_processed = 2048
    job.slot_millis = 50
    mock_bq.query.return_value = job

    client = RealBigQueryClient(project="myproj", _client=mock_bq)
    result = client.execute("SELECT COUNT(*) AS n FROM `analytics.users`")
    assert result.rows == [{"n": 5}]
    assert result.bytes_scanned == 2048
    assert result.cost_usd >= 0
    assert result.ms >= 0
```

- [ ] **Step 2: Run, verify they fail**

Run: `pytest tests/unit/test_real_client.py -v -k "dry_run or execute"`
Expected: 2 failures with NotImplementedError.

- [ ] **Step 3: Implement `dry_run` and `execute`**

In `src/mcp_bigquery_evals/bq/real.py`, add this constant near the top (right after the imports):
```python
# BigQuery on-demand pricing: $5 per TB scanned.
_USD_PER_BYTE = 5.0 / (1024**4)
```

Then replace the two stub bodies:
```python
def dry_run(self, sql: str) -> DryRunResult:
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    job = self._client.query(sql, job_config=job_config)
    bytes_scanned = int(job.total_bytes_processed or 0)
    return DryRunResult(
        bytes_scanned=bytes_scanned,
        estimated_usd=bytes_scanned * _USD_PER_BYTE,
    )

def execute(self, sql: str) -> QueryResult:
    import time as _time  # local import to avoid polluting module namespace
    start = _time.perf_counter()
    job = self._client.query(sql)
    rows = [dict(row.items()) for row in job.result()]
    elapsed_ms = int((_time.perf_counter() - start) * 1000)
    bytes_scanned = int(getattr(job, "total_bytes_processed", 0) or 0)
    return QueryResult(
        rows=rows,
        bytes_scanned=bytes_scanned,
        cost_usd=bytes_scanned * _USD_PER_BYTE,
        ms=elapsed_ms,
    )
```

(Note: at this point `execute()` makes its own dry-run-equivalent calculation from `job.total_bytes_processed`, which is set on a real query job after execution. This avoids the double-dry-run issue from Plan A's FakeBigQueryClient. T7 will refactor `run_query` to take advantage of this.)

- [ ] **Step 4: Verify**

```bash
pytest tests/unit/test_real_client.py -v
mypy src
ruff check src tests
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/bq/real.py tests/unit/test_real_client.py
git commit -m "bq(real): implement dry_run and execute against google.cloud.bigquery"
```

---

### Task 6: Translate BQ API exceptions into structured errors

**Files:**
- Create: `src/mcp_bigquery_evals/bq/errors.py`
- Modify: `src/mcp_bigquery_evals/bq/real.py`
- Create: `tests/unit/test_real_client_errors.py`

This task addresses Plan A carry-over #1: when `RealBigQueryClient.dry_run()` hits invalid SQL or unknown tables, `google.api_core.exceptions.BadRequest` and `NotFound` propagate as raw exceptions through the tool layer. The MCP agent receives an exception trace instead of a structured error it can act on.

The fix: catch the BQ exceptions in the `RealBigQueryClient` methods and translate them into structured errors that fit our existing tool error contract.

We have a choice here. Two viable shapes:

**Option A (chosen):** `dry_run` and `execute` raise a custom domain exception (`BigQueryError`) carrying a structured payload. The tool layer catches `BigQueryError` and unwraps the payload into the MCP response. This keeps the Protocol's success-vs-failure semantics clean (success = return a value, failure = raise) while still giving the agent structured info.

**Option B (rejected):** Methods return `DryRunResult | dict` (success or error). Pollutes every consumer with type-narrowing.

- [ ] **Step 1: Write the errors module**

`src/mcp_bigquery_evals/bq/errors.py`:
```python
"""Domain exceptions for BigQueryClient implementations.

Real-world BigQuery API errors get translated into BigQueryError instances
so the tool layer has a stable error contract regardless of which BQ client
implementation is in use.
"""
from __future__ import annotations


class BigQueryError(Exception):
    """A structured error from a BigQueryClient method.

    Attributes:
        code: One of "invalid_sql", "table_not_found", "permission_denied",
              "rate_limited", "unknown". Stable identifiers safe for an LLM agent
              to switch on.
        message: Human-readable description (safe to surface to the agent).
        details: Optional dict of extra fields (e.g. {"table_id": "..."}).
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, object]:
        return {"error": self.code, "message": self.message, **self.details}


def translate_bq_exception(exc: BaseException) -> BigQueryError:
    """Map a google.api_core.exceptions.* exception to a BigQueryError.

    Falls back to BigQueryError(code="unknown") for anything we don't recognize.
    """
    # Lazy-import google exceptions to keep this module light if user only has the fake.
    try:
        from google.api_core import exceptions as gerr
    except ImportError:
        return BigQueryError(code="unknown", message=str(exc))

    if isinstance(exc, gerr.BadRequest):
        return BigQueryError(
            code="invalid_sql",
            message=_first_error_message(exc) or str(exc),
        )
    if isinstance(exc, gerr.NotFound):
        return BigQueryError(
            code="table_not_found",
            message=_first_error_message(exc) or str(exc),
        )
    if isinstance(exc, gerr.PermissionDenied):
        return BigQueryError(
            code="permission_denied",
            message=_first_error_message(exc) or str(exc),
        )
    if isinstance(exc, (gerr.TooManyRequests, gerr.ResourceExhausted)):
        return BigQueryError(
            code="rate_limited",
            message=_first_error_message(exc) or str(exc),
        )
    return BigQueryError(code="unknown", message=str(exc))


def _first_error_message(exc: BaseException) -> str | None:
    """BadRequest exceptions carry a list of structured errors; return the first message."""
    errors = getattr(exc, "errors", None)
    if errors and isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            msg = first.get("message")
            if isinstance(msg, str):
                return msg
    return None
```

- [ ] **Step 2: Write failing tests**

`tests/unit/test_real_client_errors.py`:
```python
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mcp_bigquery_evals.bq.errors import BigQueryError, translate_bq_exception
from mcp_bigquery_evals.bq.real import RealBigQueryClient


def test_translate_bad_request_returns_invalid_sql():
    from google.api_core import exceptions as gerr

    exc = gerr.BadRequest("Syntax error: Expected end of input but got keyword FROM")
    err = translate_bq_exception(exc)
    assert err.code == "invalid_sql"
    assert "Syntax error" in err.message


def test_translate_not_found_returns_table_not_found():
    from google.api_core import exceptions as gerr

    exc = gerr.NotFound("Not found: Table myproj:analytics.foo")
    err = translate_bq_exception(exc)
    assert err.code == "table_not_found"


def test_translate_permission_denied():
    from google.api_core import exceptions as gerr

    exc = gerr.PermissionDenied("Access denied")
    err = translate_bq_exception(exc)
    assert err.code == "permission_denied"


def test_translate_rate_limited():
    from google.api_core import exceptions as gerr

    exc = gerr.TooManyRequests("Quota exceeded")
    err = translate_bq_exception(exc)
    assert err.code == "rate_limited"


def test_translate_unknown_falls_back():
    err = translate_bq_exception(RuntimeError("something weird"))
    assert err.code == "unknown"
    assert "something weird" in err.message


def test_to_dict_shape():
    err = BigQueryError(
        code="invalid_sql",
        message="bad",
        details={"sql": "SELECT * FRM"},
    )
    d = err.to_dict()
    assert d["error"] == "invalid_sql"
    assert d["message"] == "bad"
    assert d["sql"] == "SELECT * FRM"


# ---- Integration with RealBigQueryClient ----


def test_dry_run_translates_bad_request_to_BigQueryError():
    from google.api_core import exceptions as gerr

    mock_bq = MagicMock()
    mock_bq.query.side_effect = gerr.BadRequest("Syntax error near token 'FRM'")
    client = RealBigQueryClient(project="myproj", _client=mock_bq)

    with pytest.raises(BigQueryError) as exc_info:
        client.dry_run("SELECT * FRM users")
    assert exc_info.value.code == "invalid_sql"


def test_execute_translates_not_found_to_BigQueryError():
    from google.api_core import exceptions as gerr

    mock_bq = MagicMock()
    mock_bq.query.side_effect = gerr.NotFound("Not found: Table myproj:bogus")
    client = RealBigQueryClient(project="myproj", _client=mock_bq)

    with pytest.raises(BigQueryError) as exc_info:
        client.execute("SELECT 1 FROM `bogus`")
    assert exc_info.value.code == "table_not_found"
```

- [ ] **Step 3: Wrap `dry_run` and `execute` in `real.py` to translate exceptions**

In `src/mcp_bigquery_evals/bq/real.py`, add the import:
```python
from mcp_bigquery_evals.bq.errors import BigQueryError, translate_bq_exception
```

Then wrap both methods:
```python
def dry_run(self, sql: str) -> DryRunResult:
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    try:
        job = self._client.query(sql, job_config=job_config)
    except Exception as exc:
        raise translate_bq_exception(exc) from exc
    bytes_scanned = int(job.total_bytes_processed or 0)
    return DryRunResult(
        bytes_scanned=bytes_scanned,
        estimated_usd=bytes_scanned * _USD_PER_BYTE,
    )

def execute(self, sql: str) -> QueryResult:
    import time as _time
    start = _time.perf_counter()
    try:
        job = self._client.query(sql)
        rows = [dict(row.items()) for row in job.result()]
    except Exception as exc:
        if isinstance(exc, BigQueryError):
            raise
        raise translate_bq_exception(exc) from exc
    elapsed_ms = int((_time.perf_counter() - start) * 1000)
    bytes_scanned = int(getattr(job, "total_bytes_processed", 0) or 0)
    return QueryResult(
        rows=rows,
        bytes_scanned=bytes_scanned,
        cost_usd=bytes_scanned * _USD_PER_BYTE,
        ms=elapsed_ms,
    )
```

- [ ] **Step 4: Update `run_query` and `estimate_cost` to handle BigQueryError**

In `src/mcp_bigquery_evals/tools/run_query.py`:
```python
from mcp_bigquery_evals.bq.errors import BigQueryError
from mcp_bigquery_evals.bq.protocol import BigQueryClient
from mcp_bigquery_evals.guardrails import DEFAULT_MAX_BYTES_SCANNED, check_cost_cap


def run_query(
    client: BigQueryClient,
    sql: str,
    max_bytes_scanned: int = DEFAULT_MAX_BYTES_SCANNED,
) -> dict[str, object]:
    """MCP tool: dry-run, check cap, then execute. Returns rows or structured error."""
    try:
        dr = client.dry_run(sql)
    except BigQueryError as e:
        return e.to_dict()
    cap_err = check_cost_cap(dr, max_bytes_scanned=max_bytes_scanned)
    if cap_err is not None:
        return cap_err
    try:
        result = client.execute(sql)
    except BigQueryError as e:
        return e.to_dict()
    except ValueError as e:
        # Fake client raises ValueError for sqlite errors
        return {"error": "execution_failed", "message": str(e)}
    return {
        "rows": result.rows,
        "bytes_scanned": result.bytes_scanned,
        "cost_usd": result.cost_usd,
        "ms": result.ms,
    }
```

In `src/mcp_bigquery_evals/tools/estimate_cost.py`:
```python
from mcp_bigquery_evals.bq.errors import BigQueryError
from mcp_bigquery_evals.bq.protocol import BigQueryClient


def estimate_cost(client: BigQueryClient, sql: str) -> dict[str, object]:
    """MCP tool: dry-run a query, return bytes_scanned and estimated_usd."""
    try:
        dr = client.dry_run(sql)
    except BigQueryError as e:
        return e.to_dict()
    return {"bytes_scanned": dr.bytes_scanned, "estimated_usd": dr.estimated_usd}
```

- [ ] **Step 5: Verify**

```bash
pytest -v 2>&1 | tail -5
mypy src
ruff check src tests
```

Expected: all tests pass (existing + new error tests).

- [ ] **Step 6: Commit**

```bash
git add src/mcp_bigquery_evals/bq/errors.py src/mcp_bigquery_evals/bq/real.py src/mcp_bigquery_evals/tools/run_query.py src/mcp_bigquery_evals/tools/estimate_cost.py tests/unit/test_real_client_errors.py
git commit -m "bq: translate google.cloud.bigquery exceptions to structured BigQueryError"
```

---

### Task 7: Eliminate the double dry-run inside `run_query`

**Files:**
- Modify: `src/mcp_bigquery_evals/bq/protocol.py` (add cost fields contract)
- Modify: `src/mcp_bigquery_evals/bq/fake.py`
- Modify: `src/mcp_bigquery_evals/bq/real.py`
- Create: `tests/unit/test_dry_run_dedup.py`

Plan A's `run_query` calls `client.dry_run(sql)` for cap-check, then `client.execute(sql)` which (in the fake) calls dry_run AGAIN to populate `QueryResult.bytes_scanned`. For the real client, this is two BQ API round-trips per query.

The fix: change `BigQueryClient.execute()` to take the already-computed `DryRunResult` and use it. This makes the flow explicit (dry_run is always done first; execute reuses the result) and eliminates the double call.

- [ ] **Step 1: Write failing test**

`tests/unit/test_dry_run_dedup.py`:
```python
"""Verify run_query calls client.dry_run exactly once per invocation."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.run_query import run_query

FIXTURE = Path(__file__).parent.parent / "fixtures" / "fake_warehouse.yaml"


@pytest.fixture
def client() -> FakeBigQueryClient:
    return FakeBigQueryClient.from_yaml(FIXTURE)


def test_run_query_calls_dry_run_exactly_once(client: FakeBigQueryClient):
    with patch.object(client, "dry_run", wraps=client.dry_run) as spy:
        result = run_query(client, "SELECT COUNT(*) AS n FROM `analytics.users`")
    assert "rows" in result
    assert spy.call_count == 1
```

- [ ] **Step 2: Run, verify it fails**

Run: `pytest tests/unit/test_dry_run_dedup.py -v`
Expected: assertion error — `spy.call_count == 2` (one from run_query, one from execute).

- [ ] **Step 3: Refactor — change `execute()` signature**

Update `src/mcp_bigquery_evals/bq/protocol.py`:
```python
def execute(self, sql: str, dry_run_result: DryRunResult | None = None) -> QueryResult:
    """Execute SQL. If dry_run_result is provided, use it for cost fields without
    a second dry-run call. If None, the implementation may dry-run internally
    (or compute cost from execution metadata, e.g. job.total_bytes_processed).
    """
    ...
```

Update `src/mcp_bigquery_evals/bq/fake.py` `execute()`:
```python
def execute(self, sql: str, dry_run_result: DryRunResult | None = None) -> QueryResult:
    translated = self._bq_to_sqlite(sql)
    start = time.perf_counter()
    try:
        cur = self._conn.execute(translated)
        rows = [dict(r) for r in cur.fetchall()]
    except sqlite3.Error as e:
        raise ValueError(f"SQL execution failed: {e}") from e
    ms = int((time.perf_counter() - start) * 1000)
    dr = dry_run_result if dry_run_result is not None else self.dry_run(sql)
    return QueryResult(
        rows=rows,
        bytes_scanned=dr.bytes_scanned,
        cost_usd=dr.estimated_usd,
        ms=ms,
    )
```

Update `src/mcp_bigquery_evals/bq/real.py` `execute()`:
```python
def execute(self, sql: str, dry_run_result: DryRunResult | None = None) -> QueryResult:
    import time as _time
    start = _time.perf_counter()
    try:
        job = self._client.query(sql)
        rows = [dict(row.items()) for row in job.result()]
    except Exception as exc:
        if isinstance(exc, BigQueryError):
            raise
        raise translate_bq_exception(exc) from exc
    elapsed_ms = int((_time.perf_counter() - start) * 1000)

    if dry_run_result is not None:
        bytes_scanned = dry_run_result.bytes_scanned
        cost_usd = dry_run_result.estimated_usd
    else:
        bytes_scanned = int(getattr(job, "total_bytes_processed", 0) or 0)
        cost_usd = bytes_scanned * _USD_PER_BYTE

    return QueryResult(
        rows=rows,
        bytes_scanned=bytes_scanned,
        cost_usd=cost_usd,
        ms=elapsed_ms,
    )
```

Update `src/mcp_bigquery_evals/tools/run_query.py` to thread the dry-run result through:
```python
def run_query(
    client: BigQueryClient,
    sql: str,
    max_bytes_scanned: int = DEFAULT_MAX_BYTES_SCANNED,
) -> dict[str, object]:
    """MCP tool: dry-run, check cap, then execute. Returns rows or structured error."""
    try:
        dr = client.dry_run(sql)
    except BigQueryError as e:
        return e.to_dict()
    cap_err = check_cost_cap(dr, max_bytes_scanned=max_bytes_scanned)
    if cap_err is not None:
        return cap_err
    try:
        result = client.execute(sql, dry_run_result=dr)
    except BigQueryError as e:
        return e.to_dict()
    except ValueError as e:
        return {"error": "execution_failed", "message": str(e)}
    return {
        "rows": result.rows,
        "bytes_scanned": result.bytes_scanned,
        "cost_usd": result.cost_usd,
        "ms": result.ms,
    }
```

- [ ] **Step 4: Verify**

```bash
pytest -v 2>&1 | tail -5
mypy src
ruff check src tests
```

Expected: the new test passes (1 dry_run call), all prior tests still pass.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/bq/protocol.py src/mcp_bigquery_evals/bq/fake.py src/mcp_bigquery_evals/bq/real.py src/mcp_bigquery_evals/tools/run_query.py tests/unit/test_dry_run_dedup.py
git commit -m "bq: thread DryRunResult through execute() to eliminate double dry-run"
```

---

### Task 8: Real BQ smoke test (gated by env, runs only with credentials)

**Files:**
- Create: `tests/integration/test_real_bq_smoke.py`
- Modify: `pyproject.toml` (add a pytest mark)

This test exercises `RealBigQueryClient` against `bigquery-public-data.samples` (which is free, public, and small). It's marked with `@pytest.mark.bq` so it only runs when explicitly requested with `pytest -m bq`.

- [ ] **Step 1: Add the mark to `pyproject.toml`**

In `pyproject.toml` `[tool.pytest.ini_options]`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
markers = [
    "bq: integration test that hits real BigQuery (requires BIGQUERY_PROJECT + ADC)",
    "live: end-to-end test that hits real BQ AND real Anthropic API (requires API keys)",
]
addopts = "-m 'not bq and not live'"
```

(`addopts` excludes the marked tests by default; you opt in with `pytest -m bq`.)

- [ ] **Step 2: Write the smoke test**

`tests/integration/test_real_bq_smoke.py`:
```python
"""Real BigQuery smoke test against bigquery-public-data.

Run with: pytest -m bq
Requires:
  - BIGQUERY_PROJECT env var set to a personal GCP project (NOT bigquery-public-data;
    that's the data source, but query jobs run under YOUR project)
  - Application Default Credentials (run `gcloud auth application-default login`)
"""
from __future__ import annotations

import os

import pytest

from mcp_bigquery_evals.bq.errors import BigQueryError
from mcp_bigquery_evals.bq.real import RealBigQueryClient

pytestmark = pytest.mark.bq


@pytest.fixture
def real_client() -> RealBigQueryClient:
    project = os.environ.get("BIGQUERY_PROJECT")
    if not project:
        pytest.skip("BIGQUERY_PROJECT not set")
    return RealBigQueryClient(project=project)


def test_real_dry_run_against_public_dataset(real_client: RealBigQueryClient):
    sql = (
        "SELECT COUNT(*) AS n "
        "FROM `bigquery-public-data.samples.shakespeare` "
        "WHERE word = 'hamlet'"
    )
    dr = real_client.dry_run(sql)
    assert dr.bytes_scanned > 0
    assert dr.estimated_usd > 0


def test_real_execute_against_public_dataset(real_client: RealBigQueryClient):
    sql = (
        "SELECT word, word_count "
        "FROM `bigquery-public-data.samples.shakespeare` "
        "WHERE word = 'hamlet' "
        "ORDER BY word_count DESC LIMIT 1"
    )
    result = real_client.execute(sql)
    assert len(result.rows) == 1
    assert result.rows[0]["word"] == "hamlet"
    assert result.bytes_scanned > 0


def test_real_invalid_sql_raises_bigquery_error(real_client: RealBigQueryClient):
    with pytest.raises(BigQueryError) as exc_info:
        real_client.dry_run("SELECT * FRM `bigquery-public-data.samples.shakespeare`")
    assert exc_info.value.code == "invalid_sql"


def test_real_unknown_table_raises_table_not_found(real_client: RealBigQueryClient):
    with pytest.raises(BigQueryError) as exc_info:
        real_client.dry_run(
            "SELECT * FROM `bigquery-public-data.samples.nonexistent_table_xyz`"
        )
    assert exc_info.value.code == "table_not_found"


def test_real_list_datasets_for_personal_project(real_client: RealBigQueryClient):
    # Should not raise even if the project has zero datasets
    result = real_client.list_datasets()
    assert isinstance(result, list)
```

- [ ] **Step 3: Verify the suite still ignores the bq mark by default**

```bash
pytest -v 2>&1 | tail -3
```

Expected: same 60+ tests as before run; the new bq tests are skipped (visible as "deselected" in the summary).

- [ ] **Step 4: (Optional, requires GCP) Run the bq tests**

```bash
export BIGQUERY_PROJECT=your-personal-project
pytest -m bq -v
```

Expected: 5 tests pass against real BigQuery.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_real_bq_smoke.py pyproject.toml
git commit -m "tests: add real BigQuery smoke (gated by @pytest.mark.bq)"
```

---

### Task 9: Eval harness — golden_fake.yaml fixture

**Files:**
- Create: `src/mcp_bigquery_evals/evals/__init__.py`
- Create: `tests/fixtures/golden_fake.yaml`

`golden_fake.yaml` contains golden NL → SQL pairs that target the existing `tests/fixtures/fake_warehouse.yaml` schema. Used by unit tests for the eval runner so we can develop without GCP.

- [ ] **Step 1: Create the evals package init**

`src/mcp_bigquery_evals/evals/__init__.py`:
```python
```

- [ ] **Step 2: Create the golden fixture**

`tests/fixtures/golden_fake.yaml`:
```yaml
# Golden NL→SQL pairs targeting the FakeBigQueryClient fixture (fake_warehouse.yaml).
# Used by unit tests for the eval harness — lets us develop the runner without GCP.
# Real production pairs against bigquery-public-data live in src/mcp_bigquery_evals/evals/golden.yaml
golden_pairs:
  - id: 1
    dataset: analytics
    nl: "How many users are there in total?"
    gold_sql: |
      SELECT COUNT(*) AS n FROM `analytics.users`
    tags: [count, simple]

  - id: 2
    dataset: analytics
    nl: "How many users from India?"
    gold_sql: |
      SELECT COUNT(*) AS n FROM `analytics.users` WHERE country = 'IN'
    tags: [count, filter]

  - id: 3
    dataset: analytics
    nl: "List user emails for users in the US, sorted by user_id."
    gold_sql: |
      SELECT email FROM `analytics.users` WHERE country = 'US' ORDER BY user_id
    tags: [select, filter, order]

  - id: 4
    dataset: analytics
    nl: "How many events did each country generate? Order by country alphabetically."
    gold_sql: |
      SELECT u.country, COUNT(*) AS events
      FROM `analytics.users` u
      JOIN `analytics.events` e ON u.user_id = e.user_id
      GROUP BY u.country
      ORDER BY u.country
    tags: [join, group_by, count]

  - id: 5
    dataset: ops
    nl: "What is the maximum daily active users in the daily metrics table?"
    gold_sql: |
      SELECT MAX(dau) AS max_dau FROM `ops.daily_metrics`
    tags: [aggregate, max]
```

- [ ] **Step 3: Commit**

```bash
git add src/mcp_bigquery_evals/evals/ tests/fixtures/golden_fake.yaml
git commit -m "evals: add golden_fake.yaml fixture (5 NL→SQL pairs against fake warehouse)"
```

---

### Task 10: Eval — result-set comparison helper

**Files:**
- Create: `src/mcp_bigquery_evals/evals/compare.py`
- Create: `tests/unit/test_evals_compare.py`

Result-set comparison is the core of the result-set-equivalence eval methodology. Two result sets are equal if, treated as multisets of rows (with each row treated as a tuple of values, sorted by column name within the row), they have the same elements with the same multiplicity. Float comparison uses an absolute + relative tolerance.

- [ ] **Step 1: Write failing tests**

`tests/unit/test_evals_compare.py`:
```python
from mcp_bigquery_evals.evals.compare import results_equal


def test_equal_simple():
    a = [{"n": 5}]
    b = [{"n": 5}]
    assert results_equal(a, b)


def test_different_rows():
    a = [{"n": 5}]
    b = [{"n": 6}]
    assert not results_equal(a, b)


def test_order_independent():
    a = [{"id": 1}, {"id": 2}, {"id": 3}]
    b = [{"id": 3}, {"id": 1}, {"id": 2}]
    assert results_equal(a, b)


def test_multiset_semantics():
    # Same elements but different multiplicity → not equal
    a = [{"n": 1}, {"n": 1}, {"n": 2}]
    b = [{"n": 1}, {"n": 2}, {"n": 2}]
    assert not results_equal(a, b)


def test_float_tolerance():
    a = [{"x": 1.0000001}]
    b = [{"x": 1.0}]
    assert results_equal(a, b)


def test_float_outside_tolerance():
    a = [{"x": 1.5}]
    b = [{"x": 1.0}]
    assert not results_equal(a, b)


def test_null_equality():
    a = [{"x": None}, {"x": 1}]
    b = [{"x": 1}, {"x": None}]
    assert results_equal(a, b)


def test_column_subset_mismatch():
    # Same row data but model returned an extra column → not equal
    a = [{"n": 5}]
    b = [{"n": 5, "extra": "noise"}]
    assert not results_equal(a, b)


def test_empty_results():
    assert results_equal([], [])


def test_empty_vs_nonempty():
    assert not results_equal([], [{"n": 1}])


def test_string_equality():
    a = [{"name": "alice"}]
    b = [{"name": "alice"}]
    assert results_equal(a, b)
```

- [ ] **Step 2: Run, verify they fail**

Run: `pytest tests/unit/test_evals_compare.py -v`
Expected: ImportError on `mcp_bigquery_evals.evals.compare`.

- [ ] **Step 3: Implement `compare.py`**

`src/mcp_bigquery_evals/evals/compare.py`:
```python
"""Result-set equivalence comparison.

Spider/BIRD-style: two result sets are equal iff they match as multisets of rows,
where rows are compared as sorted-by-column-name tuples and floats use a tolerance.
NULLs compare equal to NULL. Column-set mismatch fails (the model added or removed
a column).
"""
from __future__ import annotations

from collections import Counter
from math import isclose
from typing import Any

_FLOAT_REL_TOL = 1e-6
_FLOAT_ABS_TOL = 1e-9


def results_equal(
    a: list[dict[str, Any]],
    b: list[dict[str, Any]],
) -> bool:
    """Returns True iff `a` and `b` are equal result sets under multiset semantics."""
    if len(a) != len(b):
        return False
    if not a and not b:
        return True

    # Column sets must match
    cols_a = set(a[0].keys()) if a else set()
    cols_b = set(b[0].keys()) if b else set()
    if cols_a != cols_b:
        return False

    # Sort columns within each row, then build hashable tuples for multiset comparison.
    cols = sorted(cols_a)
    rows_a = [_normalize_row(row, cols) for row in a]
    rows_b = [_normalize_row(row, cols) for row in b]

    # If any row contains a float, fall back to manual comparison (Counter can't tolerance-match).
    if any(_has_float(row) for row in rows_a + rows_b):
        return _multiset_equal_with_float_tolerance(rows_a, rows_b)
    return Counter(rows_a) == Counter(rows_b)


def _normalize_row(row: dict[str, Any], cols: list[str]) -> tuple:
    return tuple(row.get(c) for c in cols)


def _has_float(row: tuple) -> bool:
    return any(isinstance(v, float) for v in row)


def _multiset_equal_with_float_tolerance(
    rows_a: list[tuple],
    rows_b: list[tuple],
) -> bool:
    """O(n^2) fallback for float-containing rows. Acceptable for eval result sets (small)."""
    matched = [False] * len(rows_b)
    for ra in rows_a:
        found = False
        for j, rb in enumerate(rows_b):
            if matched[j]:
                continue
            if _row_equal(ra, rb):
                matched[j] = True
                found = True
                break
        if not found:
            return False
    return all(matched)


def _row_equal(a: tuple, b: tuple) -> bool:
    if len(a) != len(b):
        return False
    for va, vb in zip(a, b):
        if va is None and vb is None:
            continue
        if va is None or vb is None:
            return False
        if isinstance(va, float) or isinstance(vb, float):
            if not isclose(float(va), float(vb), rel_tol=_FLOAT_REL_TOL, abs_tol=_FLOAT_ABS_TOL):
                return False
        else:
            if va != vb:
                return False
    return True
```

- [ ] **Step 4: Verify**

```bash
pytest tests/unit/test_evals_compare.py -v
mypy src
ruff check src tests
```

Expected: all 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/evals/compare.py tests/unit/test_evals_compare.py
git commit -m "evals: add result-set comparison (multiset semantics, float tolerance, NULL equality)"
```

---

### Task 11: Eval — model prompt template

**Files:**
- Create: `src/mcp_bigquery_evals/evals/prompt.py`
- Create: `tests/unit/test_evals_prompt.py`

The prompt template tells the model what schema is available and asks it to produce SQL. It's deliberately simple — no chain-of-thought prompting, no few-shot examples for v1. The goal is a baseline measurable accuracy number, not a maxed-out one. Future versions can iterate on the prompt and watch the accuracy badge move.

- [ ] **Step 1: Write failing tests**

`tests/unit/test_evals_prompt.py`:
```python
from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.evals.prompt import build_schema_context, build_prompt

FIXTURE = Path(__file__).parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_build_schema_context_includes_table_columns_and_types():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    ctx = build_schema_context(client, dataset_id="analytics")
    assert "analytics.users" in ctx
    assert "user_id" in ctx
    assert "STRING" in ctx
    assert "Primary key" in ctx
    assert "analytics.events" in ctx


def test_build_schema_context_omits_other_datasets():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    ctx = build_schema_context(client, dataset_id="analytics")
    assert "ops.daily_metrics" not in ctx


def test_build_prompt_returns_system_and_user_strings():
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


def test_build_prompt_instructs_model_to_return_sql_only():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    prompt = build_prompt(client, dataset_id="analytics", nl="...")
    assert "only" in prompt["system"].lower() or "no explanation" in prompt["system"].lower()
```

- [ ] **Step 2: Run, verify they fail**

Run: `pytest tests/unit/test_evals_prompt.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `prompt.py`**

`src/mcp_bigquery_evals/evals/prompt.py`:
```python
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
    """Format every table in the dataset as a textual schema block."""
    blocks: list[str] = []
    for table in client.list_tables(dataset_id):
        schema = client.get_table(table.id)
        col_lines = [
            f"  - {c.name} ({c.type}){f' — {c.description}' if c.description else ''}"
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
    user = (
        f"Schema (dataset `{dataset_id}`):\n\n"
        f"{schema}\n\n"
        f"Question: {nl}\n\n"
        "SQL:"
    )
    return {"system": _SYSTEM_PROMPT, "user": user}
```

- [ ] **Step 4: Verify**

```bash
pytest tests/unit/test_evals_prompt.py -v
mypy src
ruff check src tests
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/evals/prompt.py tests/unit/test_evals_prompt.py
git commit -m "evals: add prompt builder (schema context + system/user message pair)"
```

---

### Task 12: Eval — runner orchestrator (with mock model)

**Files:**
- Create: `src/mcp_bigquery_evals/evals/runner.py`
- Create: `tests/unit/test_evals_runner.py`

The runner loads golden pairs, calls the model for each, executes both SQLs via the BigQueryClient, compares results, accumulates metrics.

For unit tests, we mock the model call so the runner is exercised end-to-end without real Anthropic API calls.

- [ ] **Step 1: Write failing tests**

`tests/unit/test_evals_runner.py`:
```python
"""Unit tests for the eval runner — uses FakeBigQueryClient and a mock model callback."""
from __future__ import annotations

from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.evals.runner import EvalReport, run_evals

FIXTURE = Path(__file__).parent.parent / "fixtures" / "fake_warehouse.yaml"
GOLDEN = Path(__file__).parent.parent / "fixtures" / "golden_fake.yaml"


def _perfect_model(prompt: dict[str, str], gold_sql: str) -> str:
    """Mock model that always returns the gold SQL → 100% accuracy."""
    return gold_sql


def _broken_model(prompt: dict[str, str], gold_sql: str) -> str:
    """Mock model that always returns wrong SQL → 0% accuracy."""
    return "SELECT 999 AS wrong"


def _partial_model(prompt: dict[str, str], gold_sql: str) -> str:
    """Mock model that returns gold for half the pairs (alternating)."""
    # Use the prompt's user content length as a poor man's coin flip.
    return gold_sql if len(prompt["user"]) % 2 == 0 else "SELECT 999 AS wrong"


def test_runner_perfect_model_yields_100_percent():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    report: EvalReport = run_evals(
        client=client,
        golden_path=GOLDEN,
        model_fn=_perfect_model,
    )
    assert report.accuracy == 1.0
    assert report.total == 5
    assert report.passes == 5


def test_runner_broken_model_yields_0_percent():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    report = run_evals(
        client=client,
        golden_path=GOLDEN,
        model_fn=_broken_model,
    )
    assert report.accuracy == 0.0
    assert report.passes == 0


def test_runner_records_per_pair_results():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    report = run_evals(
        client=client,
        golden_path=GOLDEN,
        model_fn=_perfect_model,
    )
    assert len(report.per_pair) == 5
    for r in report.per_pair:
        assert r.passed is True
        assert r.predicted_sql is not None
        assert r.gold_sql is not None
        assert r.error is None


def test_runner_handles_invalid_predicted_sql_as_failure():
    client = FakeBigQueryClient.from_yaml(FIXTURE)

    def bad_model(prompt: dict[str, str], gold_sql: str) -> str:
        return "NOT A SQL QUERY"

    report = run_evals(
        client=client,
        golden_path=GOLDEN,
        model_fn=bad_model,
    )
    assert report.passes == 0
    for r in report.per_pair:
        assert r.passed is False
        assert r.error is not None
        assert "execution_failed" in r.error or "SQL execution" in r.error


def test_runner_limit_truncates_pairs():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    report = run_evals(
        client=client,
        golden_path=GOLDEN,
        model_fn=_perfect_model,
        limit=2,
    )
    assert report.total == 2
    assert report.passes == 2
    assert report.accuracy == 1.0
```

- [ ] **Step 2: Run, verify they fail**

Run: `pytest tests/unit/test_evals_runner.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `runner.py`**

`src/mcp_bigquery_evals/evals/runner.py`:
```python
"""Eval runner orchestrator.

Loads golden pairs, calls a model callback for each, executes gold + predicted SQL,
compares results, accumulates per-pair + aggregate metrics.

The model callback signature is `(prompt: dict[str, str], gold_sql: str) -> str`.
The gold_sql is passed only so test mocks can return it; production callbacks
should ignore it and call the actual model with the prompt.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

import yaml

from mcp_bigquery_evals.bq.errors import BigQueryError
from mcp_bigquery_evals.bq.protocol import BigQueryClient
from mcp_bigquery_evals.evals.compare import results_equal
from mcp_bigquery_evals.evals.prompt import build_prompt

ModelFn = Callable[[dict[str, str], str], str]


@dataclass
class PairResult:
    id: int
    nl: str
    dataset: str
    gold_sql: str
    predicted_sql: str | None
    passed: bool
    error: str | None
    bytes_scanned: int
    cost_usd: float
    latency_ms: int


@dataclass
class EvalReport:
    accuracy: float
    total: int
    passes: int
    avg_bytes_scanned: int
    avg_latency_ms: int
    total_cost_usd: float
    per_pair: list[PairResult] = field(default_factory=list)


def run_evals(
    client: BigQueryClient,
    golden_path: Path,
    model_fn: ModelFn,
    limit: int | None = None,
) -> EvalReport:
    pairs = _load_pairs(golden_path)
    if limit is not None:
        pairs = pairs[:limit]

    per_pair: list[PairResult] = []

    for pair in pairs:
        per_pair.append(_evaluate_one(client, pair, model_fn))

    passes = sum(1 for r in per_pair if r.passed)
    total = len(per_pair)
    return EvalReport(
        accuracy=passes / total if total else 0.0,
        total=total,
        passes=passes,
        avg_bytes_scanned=int(sum(r.bytes_scanned for r in per_pair) / total) if total else 0,
        avg_latency_ms=int(sum(r.latency_ms for r in per_pair) / total) if total else 0,
        total_cost_usd=sum(r.cost_usd for r in per_pair),
        per_pair=per_pair,
    )


def _load_pairs(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(data.get("golden_pairs", []))


def _evaluate_one(
    client: BigQueryClient,
    pair: dict,
    model_fn: ModelFn,
) -> PairResult:
    pair_id = pair["id"]
    dataset = pair["dataset"]
    nl = pair["nl"]
    gold_sql = pair["gold_sql"].strip()

    predicted_sql: str | None = None
    error: str | None = None
    passed = False
    bytes_scanned = 0
    cost_usd = 0.0
    latency_ms = 0

    start = time.perf_counter()

    try:
        prompt = build_prompt(client, dataset_id=dataset, nl=nl)
        predicted_sql = model_fn(prompt, gold_sql).strip()

        # Execute both queries against the BigQueryClient.
        # Errors at this stage = pair fails (invalid predicted SQL counts as wrong).
        try:
            gold_result = _execute(client, gold_sql)
            predicted_result = _execute(client, predicted_sql)
        except (BigQueryError, ValueError) as exec_err:
            error = str(exec_err)
            return _finalize_pair(
                pair_id, nl, dataset, gold_sql, predicted_sql,
                passed=False, error=error,
                bytes_scanned=0, cost_usd=0.0,
                latency_ms=int((time.perf_counter() - start) * 1000),
            )

        passed = results_equal(gold_result.rows, predicted_result.rows)
        bytes_scanned = predicted_result.bytes_scanned
        cost_usd = predicted_result.cost_usd
    except Exception as e:
        error = f"runner_error: {e}"
        passed = False

    latency_ms = int((time.perf_counter() - start) * 1000)

    return _finalize_pair(
        pair_id, nl, dataset, gold_sql, predicted_sql,
        passed=passed, error=error,
        bytes_scanned=bytes_scanned, cost_usd=cost_usd,
        latency_ms=latency_ms,
    )


def _execute(client: BigQueryClient, sql: str):
    """Helper: dry-run then execute (threading the dry-run result through)."""
    dr = client.dry_run(sql)
    return client.execute(sql, dry_run_result=dr)


def _finalize_pair(
    pair_id: int,
    nl: str,
    dataset: str,
    gold_sql: str,
    predicted_sql: str | None,
    passed: bool,
    error: str | None,
    bytes_scanned: int,
    cost_usd: float,
    latency_ms: int,
) -> PairResult:
    return PairResult(
        id=pair_id,
        nl=nl,
        dataset=dataset,
        gold_sql=gold_sql,
        predicted_sql=predicted_sql,
        passed=passed,
        error=error,
        bytes_scanned=bytes_scanned,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
    )


def report_to_dict(report: EvalReport) -> dict:
    return asdict(report)
```

- [ ] **Step 4: Verify**

```bash
pytest tests/unit/test_evals_runner.py -v
mypy src
ruff check src tests
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/evals/runner.py tests/unit/test_evals_runner.py
git commit -m "evals: add runner orchestrator (loads pairs, calls model, executes, compares)"
```

---

### Task 13: Wire `evals run` subcommand in CLI (with Anthropic SDK)

**Files:**
- Modify: `src/mcp_bigquery_evals/cli.py`
- Create: `src/mcp_bigquery_evals/evals/anthropic_model.py`

The CLI subcommand wires together: load env, build BigQueryClient, build the Anthropic model callback, run evals, print report.

- [ ] **Step 1: Write the Anthropic model adapter**

`src/mcp_bigquery_evals/evals/anthropic_model.py`:
```python
"""Anthropic Messages API adapter for the eval runner.

Wraps anthropic.Anthropic into the ModelFn signature expected by runner.run_evals.
"""
from __future__ import annotations

import os
import re
from typing import Any

# Lazy import so unit tests don't need the SDK installed.


def make_anthropic_model(model_id: str = "claude-haiku-4-5") -> Any:
    """Returns a function with signature (prompt, gold_sql) -> predicted_sql.

    Reads ANTHROPIC_API_KEY from env. Raises if missing.
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY env var is required for the eval runner")

    client = anthropic.Anthropic(api_key=api_key)

    def call(prompt: dict[str, str], _gold_sql: str) -> str:
        response = client.messages.create(
            model=model_id,
            max_tokens=2048,
            system=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}],
        )
        text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )
        return _strip_markdown_fences(text).strip()

    return call


def _strip_markdown_fences(text: str) -> str:
    """Remove ```sql ... ``` or ``` ... ``` fences if the model wrapped its output."""
    text = re.sub(r"^```(?:sql)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    return text
```

- [ ] **Step 2: Update `cli.py` to wire the evals subcommand**

Replace `src/mcp_bigquery_evals/cli.py` with:
```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mcp-bigquery-evals")
    sub = parser.add_subparsers(dest="cmd")

    serve = sub.add_parser("serve", help="Run the MCP server over stdio.")
    serve.set_defaults(func=_cmd_serve)

    evals = sub.add_parser("evals", help="Run the NL2SQL eval harness.")
    evals_sub = evals.add_subparsers(dest="evals_cmd")

    run = evals_sub.add_parser("run", help="Execute the eval suite against a model.")
    run.add_argument("--model", default="claude-haiku-4-5", help="Anthropic model id.")
    run.add_argument(
        "--golden",
        type=Path,
        default=Path("src/mcp_bigquery_evals/evals/golden.yaml"),
        help="Path to the golden NL→SQL pairs file.",
    )
    run.add_argument("--limit", type=int, default=None, help="Run only N pairs.")
    run.add_argument(
        "--report",
        type=Path,
        default=Path("evals/last_report.json"),
        help="Where to write the JSON report.",
    )
    run.set_defaults(func=_cmd_evals_run)

    args = parser.parse_args(argv)
    func: Callable[[argparse.Namespace], int] = getattr(args, "func", _cmd_serve)
    return func(args)


def _cmd_serve(_args: argparse.Namespace) -> int:
    from mcp_bigquery_evals.server import build_server

    server = build_server()
    server.run()
    return 0


def _cmd_evals_run(args: argparse.Namespace) -> int:
    # Load .env if present
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    from mcp_bigquery_evals.evals.anthropic_model import make_anthropic_model
    from mcp_bigquery_evals.evals.runner import report_to_dict, run_evals
    from mcp_bigquery_evals.server import build_client

    try:
        client = build_client()
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    try:
        model_fn = make_anthropic_model(model_id=args.model)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print(f"Running evals: model={args.model} golden={args.golden} limit={args.limit}", file=sys.stderr)
    report = run_evals(
        client=client,
        golden_path=args.golden,
        model_fn=model_fn,
        limit=args.limit,
    )

    # Print summary to stderr; write full JSON to file.
    print(
        f"\nResults: accuracy={report.accuracy:.1%} ({report.passes}/{report.total}) "
        f"avg_bytes={report.avg_bytes_scanned} avg_ms={report.avg_latency_ms} "
        f"cost_usd={report.total_cost_usd:.4f}",
        file=sys.stderr,
    )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report_to_dict(report), indent=2, default=str))
    print(f"Wrote report to {args.report}", file=sys.stderr)

    return 0 if report.accuracy > 0 else 1
```

- [ ] **Step 3: Smoke verify the CLI parses**

```bash
source .venv/Scripts/activate
python -m mcp_bigquery_evals --help
python -m mcp_bigquery_evals evals --help
python -m mcp_bigquery_evals evals run --help
```

All three should print clean help text. The `evals run` help should list `--model`, `--golden`, `--limit`, `--report`.

- [ ] **Step 4: Update CLI tests**

In `tests/unit/test_cli.py`, add:
```python
def test_cli_evals_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["evals", "--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "run" in captured.out


def test_cli_evals_run_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["evals", "run", "--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "--model" in captured.out
    assert "--golden" in captured.out
    assert "--limit" in captured.out
    assert "--report" in captured.out
```

- [ ] **Step 5: Verify**

```bash
pytest -v 2>&1 | tail -5
mypy src
ruff check src tests
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/mcp_bigquery_evals/cli.py src/mcp_bigquery_evals/evals/anthropic_model.py tests/unit/test_cli.py
git commit -m "cli: wire 'evals run' subcommand with Anthropic SDK + report output"
```

---

### Task 14: Eval — JSON report + accuracy badge writer

**Files:**
- Create: `src/mcp_bigquery_evals/evals/report.py`
- Create: `tests/unit/test_evals_report.py`

The report writer outputs both a full JSON report (consumed by humans + the badge generator) and a small `badge.json` consumable by `shields.io`'s endpoint API for live README badges.

- [ ] **Step 1: Write failing tests**

`tests/unit/test_evals_report.py`:
```python
import json
from pathlib import Path

from mcp_bigquery_evals.evals.report import write_badge, write_report
from mcp_bigquery_evals.evals.runner import EvalReport, PairResult


def _sample_report() -> EvalReport:
    return EvalReport(
        accuracy=0.74,
        total=50,
        passes=37,
        avg_bytes_scanned=12_000_000,
        avg_latency_ms=1_200,
        total_cost_usd=0.0034,
        per_pair=[
            PairResult(
                id=1, nl="...", dataset="x", gold_sql="...", predicted_sql="...",
                passed=True, error=None, bytes_scanned=10_000_000,
                cost_usd=0.00005, latency_ms=1100,
            )
        ],
    )


def test_write_report_creates_json(tmp_path: Path):
    out = tmp_path / "r.json"
    write_report(_sample_report(), out, model_id="claude-haiku-4-5")
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["model"] == "claude-haiku-4-5"
    assert data["accuracy"] == 0.74
    assert data["total"] == 50
    assert "per_pair" in data


def test_write_badge_creates_shields_endpoint_json(tmp_path: Path):
    out = tmp_path / "badge.json"
    write_badge(_sample_report(), out, model_id="claude-haiku-4-5")
    data = json.loads(out.read_text())
    assert data["schemaVersion"] == 1
    assert "claude-haiku-4-5" in data["label"] or "accuracy" in data["label"]
    assert "74%" in data["message"]
    assert data["color"] in {"red", "orange", "yellow", "green", "brightgreen"}


def test_badge_color_thresholds(tmp_path: Path):
    """Color buckets: <40% red, <60% orange, <75% yellow, <90% green, ≥90% brightgreen."""
    cases = [(0.10, "red"), (0.50, "orange"), (0.70, "yellow"), (0.85, "green"), (0.95, "brightgreen")]
    for acc, expected in cases:
        out = tmp_path / f"b_{int(acc * 100)}.json"
        report = _sample_report()
        report.accuracy = acc
        write_badge(report, out, model_id="x")
        data = json.loads(out.read_text())
        assert data["color"] == expected, f"acc={acc}: expected {expected}, got {data['color']}"
```

- [ ] **Step 2: Run, verify they fail**

Run: `pytest tests/unit/test_evals_report.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `report.py`**

`src/mcp_bigquery_evals/evals/report.py`:
```python
"""JSON report + shields.io badge writer for eval runs."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from mcp_bigquery_evals.evals.runner import EvalReport


def write_report(report: EvalReport, out: Path, model_id: str) -> None:
    """Write the full eval report as JSON. Includes model id and timestamp."""
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": model_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **asdict(report),
    }
    out.write_text(json.dumps(payload, indent=2, default=str))


def write_badge(report: EvalReport, out: Path, model_id: str) -> None:
    """Write a shields.io endpoint JSON file (https://shields.io/endpoint).

    The README references this file at a known URL; shields.io fetches it
    and renders a colored badge. CI updates this file on every main merge.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    pct = int(round(report.accuracy * 100))
    payload = {
        "schemaVersion": 1,
        "label": f"{model_id} accuracy",
        "message": f"{pct}%",
        "color": _color_for_accuracy(report.accuracy),
    }
    out.write_text(json.dumps(payload))


def _color_for_accuracy(acc: float) -> str:
    if acc < 0.40:
        return "red"
    if acc < 0.60:
        return "orange"
    if acc < 0.75:
        return "yellow"
    if acc < 0.90:
        return "green"
    return "brightgreen"
```

- [ ] **Step 4: Wire the badge writer into the CLI subcommand**

In `src/mcp_bigquery_evals/cli.py` `_cmd_evals_run()`, add after the JSON report write:
```python
from mcp_bigquery_evals.evals.report import write_badge, write_report

# Replace the existing args.report.write_text(...) with:
write_report(report, args.report, model_id=args.model)
badge_path = args.report.parent / "badge.json"
write_badge(report, badge_path, model_id=args.model)
print(f"Wrote badge to {badge_path}", file=sys.stderr)
```

(Remove the manual `json.dumps` calls; `write_report` handles it now.)

- [ ] **Step 5: Verify**

```bash
pytest -v 2>&1 | tail -5
mypy src
ruff check src tests
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/mcp_bigquery_evals/evals/report.py src/mcp_bigquery_evals/cli.py tests/unit/test_evals_report.py
git commit -m "evals: add JSON report + shields.io badge writer; CLI emits both"
```

---

### Task 15: Real golden pairs against `bigquery-public-data`

**Files:**
- Create: `src/mcp_bigquery_evals/evals/golden.yaml`

This is the production golden set. Targets 3 `bigquery-public-data` datasets: `samples` (Shakespeare, natality), `stackoverflow`, `usa_names`. Starts with **15 pairs**; the goal is to grow to 30-50 over time.

The pairs are hand-written (you wrote them, you can defend them). Each is a real, plausible analyst question with an unambiguous gold answer.

> **Tactical note:** If you want to scale to 50+ pairs, the right pattern is to ask Claude to generate candidates against each dataset's schema, then YOU verify each one runs and the gold result is what you expected. Don't ship pairs you haven't personally verified — the eval harness's credibility depends on the goldens being right.

- [ ] **Step 1: Write the golden.yaml**

`src/mcp_bigquery_evals/evals/golden.yaml`:
```yaml
# Production golden NL→SQL pairs for the eval harness.
# Targets bigquery-public-data — anyone with a GCP project can reproduce.
# Each pair must be MANUALLY VERIFIED by running gold_sql against real BQ
# and confirming the result matches the question's intent.
golden_pairs:
  # ---- bigquery-public-data.samples (small, free, no quota concerns) ----

  - id: 1
    dataset: bigquery-public-data.samples
    nl: "How many unique words appear in the Shakespeare dataset?"
    gold_sql: |
      SELECT COUNT(DISTINCT word) AS n
      FROM `bigquery-public-data.samples.shakespeare`
    tags: [count, distinct]

  - id: 2
    dataset: bigquery-public-data.samples
    nl: "What are the top 5 most-frequent words in the Shakespeare dataset, excluding words shorter than 4 characters?"
    gold_sql: |
      SELECT word, SUM(word_count) AS total
      FROM `bigquery-public-data.samples.shakespeare`
      WHERE LENGTH(word) >= 4
      GROUP BY word
      ORDER BY total DESC
      LIMIT 5
    tags: [aggregate, filter, group_by, order, limit]

  - id: 3
    dataset: bigquery-public-data.samples
    nl: "How many corpora (distinct works) are in the Shakespeare dataset?"
    gold_sql: |
      SELECT COUNT(DISTINCT corpus) AS n
      FROM `bigquery-public-data.samples.shakespeare`
    tags: [count, distinct]

  - id: 4
    dataset: bigquery-public-data.samples
    nl: "What is the average baby weight in pounds for births recorded in the natality dataset?"
    gold_sql: |
      SELECT AVG(weight_pounds) AS avg_weight
      FROM `bigquery-public-data.samples.natality`
      WHERE weight_pounds IS NOT NULL
    tags: [aggregate, null_handling]

  - id: 5
    dataset: bigquery-public-data.samples
    nl: "Total natality records by year, ordered chronologically. Limit to first 5 years."
    gold_sql: |
      SELECT year, COUNT(*) AS births
      FROM `bigquery-public-data.samples.natality`
      GROUP BY year
      ORDER BY year
      LIMIT 5
    tags: [group_by, count, order, limit]

  # ---- bigquery-public-data.stackoverflow ----

  - id: 6
    dataset: bigquery-public-data.stackoverflow
    nl: "How many questions tagged with 'python' were asked in 2023?"
    gold_sql: |
      SELECT COUNT(*) AS n
      FROM `bigquery-public-data.stackoverflow.posts_questions`
      WHERE EXTRACT(YEAR FROM creation_date) = 2023
        AND tags LIKE '%python%'
    tags: [count, filter, year_extract, like]

  - id: 7
    dataset: bigquery-public-data.stackoverflow
    nl: "Top 3 most-viewed Stack Overflow questions tagged 'sql' (by view_count)."
    gold_sql: |
      SELECT title, view_count
      FROM `bigquery-public-data.stackoverflow.posts_questions`
      WHERE tags LIKE '%sql%'
      ORDER BY view_count DESC
      LIMIT 3
    tags: [select, filter, order, limit]

  - id: 8
    dataset: bigquery-public-data.stackoverflow
    nl: "How many users on Stack Overflow have a reputation greater than 100,000?"
    gold_sql: |
      SELECT COUNT(*) AS n
      FROM `bigquery-public-data.stackoverflow.users`
      WHERE reputation > 100000
    tags: [count, filter]

  - id: 9
    dataset: bigquery-public-data.stackoverflow
    nl: "Which year had the most questions asked on Stack Overflow? Return the year."
    gold_sql: |
      SELECT EXTRACT(YEAR FROM creation_date) AS year, COUNT(*) AS n
      FROM `bigquery-public-data.stackoverflow.posts_questions`
      GROUP BY year
      ORDER BY n DESC
      LIMIT 1
    tags: [group_by, count, year_extract, order, limit]

  - id: 10
    dataset: bigquery-public-data.stackoverflow
    nl: "Average score of accepted answers in the stackoverflow dataset (use posts_answers; accepted answers have parent_id matching a question's accepted_answer_id)."
    gold_sql: |
      SELECT AVG(a.score) AS avg_score
      FROM `bigquery-public-data.stackoverflow.posts_answers` a
      JOIN `bigquery-public-data.stackoverflow.posts_questions` q
        ON a.id = q.accepted_answer_id
    tags: [aggregate, join]

  # ---- bigquery-public-data.usa_names ----

  - id: 11
    dataset: bigquery-public-data.usa_names
    nl: "What are the top 5 most popular baby names of all time in the USA names dataset?"
    gold_sql: |
      SELECT name, SUM(number) AS total
      FROM `bigquery-public-data.usa_names.usa_1910_2013`
      GROUP BY name
      ORDER BY total DESC
      LIMIT 5
    tags: [group_by, aggregate, order, limit]

  - id: 12
    dataset: bigquery-public-data.usa_names
    nl: "How many distinct baby names were recorded in the USA names dataset?"
    gold_sql: |
      SELECT COUNT(DISTINCT name) AS n
      FROM `bigquery-public-data.usa_names.usa_1910_2013`
    tags: [count, distinct]

  - id: 13
    dataset: bigquery-public-data.usa_names
    nl: "What is the most popular baby boy name in 2010?"
    gold_sql: |
      SELECT name
      FROM `bigquery-public-data.usa_names.usa_1910_2013`
      WHERE year = 2010 AND gender = 'M'
      ORDER BY number DESC
      LIMIT 1
    tags: [select, filter, order, limit]

  - id: 14
    dataset: bigquery-public-data.usa_names
    nl: "Total births recorded by gender in the USA names dataset."
    gold_sql: |
      SELECT gender, SUM(number) AS total
      FROM `bigquery-public-data.usa_names.usa_1910_2013`
      GROUP BY gender
    tags: [group_by, aggregate]

  - id: 15
    dataset: bigquery-public-data.usa_names
    nl: "Year with the highest total recorded births. Return the year and the total."
    gold_sql: |
      SELECT year, SUM(number) AS total
      FROM `bigquery-public-data.usa_names.usa_1910_2013`
      GROUP BY year
      ORDER BY total DESC
      LIMIT 1
    tags: [group_by, aggregate, order, limit]
```

- [ ] **Step 2: Manually verify each pair against real BQ (requires GCP)**

```bash
export BIGQUERY_PROJECT=your-personal-project
# For each pair, run the gold_sql via bq command-line tool or via a small Python script
# and confirm the result matches the question's intent.
```

If a gold_sql produces a result that doesn't match what the NL question intends (e.g., wrong year extract), fix the SQL or the NL.

> **Engineer note:** If you can't verify against real BQ right now (no GCP yet), commit the file as-is with a `verified: false` flag in the YAML for each pair, and add a TODO to verify before T16 (which actually runs against real BQ). I'd recommend deferring this entire task until GCP is set up — the goldens are useless if not verified.

- [ ] **Step 3: Commit (after verification)**

```bash
git add src/mcp_bigquery_evals/evals/golden.yaml
git commit -m "evals: add 15 verified golden pairs against bigquery-public-data"
```

---

### Task 16: End-to-end real eval smoke (real BQ + real Anthropic)

**Files:**
- Create: `tests/integration/test_evals_real_smoke.py`

Marked with `@pytest.mark.live`. Runs only with `pytest -m live` AND requires both `BIGQUERY_PROJECT` and `ANTHROPIC_API_KEY` set. Costs a few cents in API calls per run — kept small (3 pairs).

- [ ] **Step 1: Write the smoke test**

`tests/integration/test_evals_real_smoke.py`:
```python
"""End-to-end smoke: real BQ + real Anthropic, 3 golden pairs.

Run with: pytest -m live
Cost: ~$0.001 in BQ scans + ~$0.01 in Anthropic Haiku tokens (one-shot).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from mcp_bigquery_evals.bq.real import RealBigQueryClient
from mcp_bigquery_evals.evals.anthropic_model import make_anthropic_model
from mcp_bigquery_evals.evals.runner import run_evals

pytestmark = pytest.mark.live

GOLDEN = Path("src/mcp_bigquery_evals/evals/golden.yaml")


@pytest.fixture
def client() -> RealBigQueryClient:
    project = os.environ.get("BIGQUERY_PROJECT")
    if not project:
        pytest.skip("BIGQUERY_PROJECT not set")
    return RealBigQueryClient(project=project)


def test_real_eval_smoke_3_pairs(client: RealBigQueryClient):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
    if not GOLDEN.exists():
        pytest.skip("golden.yaml does not exist yet (run T15)")

    model_fn = make_anthropic_model(model_id="claude-haiku-4-5")
    report = run_evals(client=client, golden_path=GOLDEN, model_fn=model_fn, limit=3)

    assert report.total == 3
    # Don't assert a specific accuracy — that's what we're measuring.
    # Just assert the run completed without crashing and produced a number.
    assert 0.0 <= report.accuracy <= 1.0
    assert all(r.predicted_sql is not None for r in report.per_pair)
    print(f"\nSmoke accuracy on 3 pairs: {report.accuracy:.1%}")
```

- [ ] **Step 2: (Optional, requires creds) Run the smoke**

```bash
export BIGQUERY_PROJECT=your-project ANTHROPIC_API_KEY=sk-ant-...
pytest -m live -v -s
```

You should see the actual accuracy number printed.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_evals_real_smoke.py
git commit -m "tests: add live eval smoke (real BQ + real Anthropic, 3 pairs)"
```

---

### Task 17: README v1.0 (the real one)

**Files:**
- Modify: `README.md` (rewrite from placeholder)

The README is the v1 sales pitch. Structure:
1. One-line hook + accuracy badge
2. What it is
3. Quickstart (Claude Desktop in 5 minutes)
4. The 7 tools
5. Cost guardrails
6. Eval harness (link to docs)
7. Why this exists (differentiation)
8. License + contributing

- [ ] **Step 1: Replace `README.md`**

`README.md`:
````markdown
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
        "BIGQUERY_PROJECT": "your-personal-gcp-project-id"
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

All tools are read-only. There are no write operations in v1 by design. See `docs/architecture.md`.

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

## Eval harness

Every release runs a result-set-equivalence eval suite against `bigquery-public-data` and updates the accuracy badge above. Run locally:

```bash
mcp-bigquery-evals evals run --model claude-haiku-4-5
```

See `docs/how_evals_work.md` for the methodology, golden pairs format, and how to add your own.

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

MIT — see `LICENSE`.

## Contributing

Issues and PRs welcome. Especially valuable:
- More golden NL→SQL pairs (hand-verified, against bigquery-public-data)
- Improved prompts (with eval numbers showing the change moves the accuracy badge)
- Bug reports with reproduction steps
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: write v1.0 README with quickstart, tools, guardrails, evals"
```

---

### Task 18: docs/claude_desktop_setup.md

**Files:**
- Create: `docs/claude_desktop_setup.md`

- [ ] **Step 1: Write the doc**

`docs/claude_desktop_setup.md`:
```markdown
# Claude Desktop Setup

This guide walks through wiring `mcp-bigquery-evals` into Claude Desktop on macOS, Windows, and Linux.

## Prerequisites

- Claude Desktop installed (latest version)
- Python 3.11+ available on PATH
- A GCP project with the BigQuery API enabled
- (Optional) `uv` installed (recommended for `uvx` zero-install). Install via `pip install uv` or `brew install uv`.

## 1. Authenticate to GCP

The MCP server uses Application Default Credentials. Set them up once:

```bash
gcloud auth application-default login
```

This opens a browser tab. After login, ADC are stored at `~/.config/gcloud/application_default_credentials.json` and the server reads them automatically.

If you'd rather use a service account JSON, set `GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json` instead.

## 2. Find your `claude_desktop_config.json`

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

If the file doesn't exist, create it with `{}`.

## 3. Add the MCP server

```json
{
  "mcpServers": {
    "bigquery": {
      "command": "uvx",
      "args": ["mcp-bigquery-evals", "serve"],
      "env": {
        "BIGQUERY_PROJECT": "your-project-id"
      }
    }
  }
}
```

If you don't have `uv` installed, swap `command` to your `python` and use `args: ["-m", "mcp_bigquery_evals", "serve"]` after `pip install mcp-bigquery-evals` into a venv whose python is on PATH.

## 4. Restart Claude Desktop

Fully quit Claude Desktop (not just close window) and reopen. You should see "bigquery" listed in the MCP indicator (the small icon at the bottom of the chat input). Click it to confirm 7 tools are available.

## 5. Verify

Ask Claude:
> "Using the bigquery tool, list the datasets in my project."

If you see a list, you're done. If you see an error, see Troubleshooting below.

## Troubleshooting

### "BIGQUERY_PROJECT env var is required"

The `env` block in your config wasn't passed through. Double-check the JSON is valid (no trailing commas) and restart Claude Desktop fully.

### "Reauthentication is needed" or 401 errors

Run `gcloud auth application-default login` again. ADC tokens expire periodically.

### "Permission denied" when listing tables

Your account doesn't have BigQuery Data Viewer on the dataset. For `bigquery-public-data`, this is granted by default to any authenticated GCP user; for your own data, grant `roles/bigquery.dataViewer` to your account.

### The MCP indicator says "bigquery: 0 tools"

The server crashed on startup. Check Claude Desktop's MCP logs:
- macOS: `~/Library/Logs/Claude/mcp-server-bigquery.log`
- Windows: `%APPDATA%\Claude\Logs\mcp-server-bigquery.log`

The most common cause is a missing dependency. Re-run `uvx --no-cache mcp-bigquery-evals --help` to force a fresh install.

### Cost cap errors blocking your queries

The default cap is 100 MB scanned. To raise it for a single query, ask Claude:
> "Use the bigquery tool with max_bytes_scanned=2_000_000_000 to run [your query]"

To change the default permanently, fork this repo and patch `DEFAULT_MAX_BYTES_SCANNED` in `src/mcp_bigquery_evals/guardrails.py`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/claude_desktop_setup.md
git commit -m "docs: add Claude Desktop setup guide"
```

---

### Task 19: docs/architecture.md

**Files:**
- Create: `docs/architecture.md`

- [ ] **Step 1: Write the doc**

`docs/architecture.md`:
```markdown
# Architecture

This document explains the design decisions behind `mcp-bigquery-evals` v1. For the original design spec, see [`superpowers/specs/2026-05-02-bq-nl2sql-mcp-design.md`](./superpowers/specs/2026-05-02-bq-nl2sql-mcp-design.md).

## High-level shape

```
┌─────────────────┐     stdio        ┌─────────────────────────────────┐
│ Claude Desktop  │ ◄─── MCP ────►  │  mcp-bigquery-evals server      │
└─────────────────┘                  │                                 │
                                     │  ┌─────────────────────────┐    │
                                     │  │ 7 MCP tool handlers     │    │
                                     │  │ (one Python file each)  │    │
                                     │  └────────────┬────────────┘    │
                                     │               │                 │
                                     │  ┌────────────▼─────────────┐   │
                                     │  │ BigQueryClient Protocol  │   │
                                     │  └────────────┬─────────────┘   │
                                     │               │                 │
                                     │   ┌───────────┴────────────┐    │
                                     │   │                        │    │
                                     │  RealBQ                 FakeBQ  │
                                     │  (google-cloud-bigquery)  (sqlite + yaml)│
                                     └─────────────────────────────────┘
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

### 3. Read-only by design

No `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`. The blast radius of an LLM mistake is bounded to scanning bytes, not mutating data. Write operations are explicitly out of scope for v1.

### 4. No internal LLM calls in the server runtime

The MCP server is deterministic. It does not call Claude, GPT, or any other LLM internally. The consumer (Claude Desktop) IS the LLM — it can summarize SQL, explain results, and reason about errors itself. Putting an LLM inside an MCP server whose only consumer is an LLM is a design smell.

The eval harness is a separate process (`mcp-bigquery-evals evals run`) and DOES call Anthropic's API to generate predicted SQL. It does NOT touch the MCP server runtime.

### 5. Result-set equivalence for evals

We chose result-set equivalence (Spider/BIRD methodology) over LLM-as-judge:
- Deterministic
- Single number (`passes / total`) for the README badge
- Respected by the senior-engineer audience (Hamel Husain has written explicitly against LLM-as-judge for SQL)
- Costs real BQ scans, but small datasets (`bigquery-public-data.samples`) keep this manageable

### 6. CLI subcommands share the same binary

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
```

- [ ] **Step 2: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: add architecture overview"
```

---

### Task 20: docs/how_evals_work.md

**Files:**
- Create: `docs/how_evals_work.md`

- [ ] **Step 1: Write the doc**

`docs/how_evals_work.md`:
```markdown
# How the eval harness works

This document explains the methodology, the golden pairs format, and how to add your own.

## Methodology: result-set equivalence

For each golden pair `{nl, gold_sql, dataset}`:

1. Build a schema context (textual dump of every table in `dataset` + their columns + descriptions)
2. Send the schema + the natural-language question to Claude (via the Anthropic API), asking for a single SQL query
3. Execute the gold SQL via BigQuery → `gold_result` (list of row dicts)
4. Execute the model's predicted SQL via BigQuery → `predicted_result` (list of row dicts)
5. Compare the two as multisets of rows (order-independent, with float tolerance and NULL equality)
6. Pass = identical results

Aggregate `accuracy = passes / total` is the headline metric, displayed as a shields.io badge in the README.

## Why result-set equivalence (and not LLM-as-judge)

- **Deterministic.** The same model + the same goldens always yields the same accuracy. CI runs are reproducible.
- **Defensible.** This is the methodology used by Spider, BIRD, and most academic NL2SQL benchmarks.
- **Single number.** "Accuracy: 74%" goes in a badge. "LLM judge says these answers were mostly fine" doesn't.
- **No judge bias.** No model has a vested interest in the outcome.

The downside: result-set equivalence is strict. A model that produces `SELECT name, COUNT(*)` instead of `SELECT name, COUNT(*) AS n` will fail because the column name differs. A model that returns rows in a different order passes (we sort multiset-style). A model that returns the right count but as a float instead of int passes (we tolerance-match).

## The golden pairs file

Production goldens: `src/mcp_bigquery_evals/evals/golden.yaml`. Format:

```yaml
golden_pairs:
  - id: 1
    dataset: bigquery-public-data.samples
    nl: "How many unique words appear in the Shakespeare dataset?"
    gold_sql: |
      SELECT COUNT(DISTINCT word) AS n
      FROM `bigquery-public-data.samples.shakespeare`
    tags: [count, distinct]
```

Fields:
- `id` (int) — unique identifier
- `dataset` (string) — fully-qualified dataset (`project.dataset`); used to build the schema context
- `nl` (string) — natural-language question, written as a real analyst would ask it
- `gold_sql` (string) — the canonical correct SQL; you must verify this returns the right answer
- `tags` (list[string]) — optional; useful for slicing accuracy by query category

## Running the harness

```bash
mcp-bigquery-evals evals run --model claude-haiku-4-5
```

Optional flags:
- `--golden PATH` — use a different golden file (default: `src/mcp_bigquery_evals/evals/golden.yaml`)
- `--limit N` — run only the first N pairs (useful for fast iteration)
- `--report PATH` — where to write the JSON report (default: `evals/last_report.json`)

The runner also writes a `badge.json` next to the report (consumed by shields.io).

## Adding a new golden pair

1. Pick a `bigquery-public-data` dataset and a real analyst question
2. Write the gold SQL
3. Run it manually against real BQ:
   ```bash
   bq query --use_legacy_sql=false 'SELECT ...'
   ```
4. Confirm the result matches what the question intended
5. Add the entry to `golden.yaml`
6. Re-run the harness to confirm the new pair works
7. Open a PR

## Cost

Each golden pair costs:
- ~1 BQ dry-run (free)
- ~1 BQ query execution (typically ~1MB scanned ≈ $0.000005)
- ~1 Anthropic API call (Haiku ~$0.0001 per pair)

15 pairs at Haiku ≈ ~$0.002 per run. 50 pairs ≈ ~$0.007 per run. CI runs the full set on every main merge.

## Cost-effectively iterating on prompts

To test a prompt change without paying full freight:
```bash
mcp-bigquery-evals evals run --model claude-haiku-4-5 --limit 5
```

Five pairs at Haiku is ~$0.0005 per iteration. Iterate fast.
```

- [ ] **Step 2: Commit**

```bash
git add docs/how_evals_work.md
git commit -m "docs: add eval harness walkthrough (methodology, format, how to add pairs)"
```

---

### Task 21: CI — `ci.yml` (lint, types, unit tests)

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the workflow**

`.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  lint-types-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Ruff check
        run: ruff check src tests

      - name: Ruff format check
        run: ruff format --check src tests

      - name: Mypy strict
        run: mypy src

      - name: Pytest (unit tests only — bq and live tests are gated)
        run: pytest -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add ruff + mypy + pytest workflow on push/PR (Python 3.11 + 3.12)"
```

---

### Task 22: CI — `evals.yml` (run evals, update badge)

**Files:**
- Create: `.github/workflows/evals.yml`

This workflow runs on every `main` push, executes the eval harness against real BQ + real Anthropic, and commits the updated `badge.json` back to the repo. Requires GitHub repo secrets:
- `GCP_SA_KEY` — service account JSON (paste the entire JSON)
- `BIGQUERY_PROJECT` — your project id
- `ANTHROPIC_API_KEY`

- [ ] **Step 1: Write the workflow**

`.github/workflows/evals.yml`:
```yaml
name: Evals

on:
  push:
    branches: [main]
  workflow_dispatch:  # manual trigger

jobs:
  run-evals:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Set up GCP credentials
        env:
          GCP_SA_KEY: ${{ secrets.GCP_SA_KEY }}
        run: |
          mkdir -p ~/.config/gcloud
          echo "$GCP_SA_KEY" > ~/.config/gcloud/sa.json
          echo "GOOGLE_APPLICATION_CREDENTIALS=$HOME/.config/gcloud/sa.json" >> $GITHUB_ENV

      - name: Run evals
        env:
          BIGQUERY_PROJECT: ${{ secrets.BIGQUERY_PROJECT }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          mkdir -p evals
          mcp-bigquery-evals evals run \
            --model claude-haiku-4-5 \
            --golden src/mcp_bigquery_evals/evals/golden.yaml \
            --report evals/latest.json

      - name: Commit updated badge
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          if git diff --quiet evals/badge.json; then
            echo "Badge unchanged; nothing to commit."
          else
            git add evals/badge.json evals/latest.json
            git commit -m "evals: update badge from CI run [skip ci]"
            git push
          fi
```

- [ ] **Step 2: Add `evals/` to `.gitignore` exclusions**

Make sure the existing `.gitignore` does NOT exclude `evals/badge.json` — that file MUST be committed by CI for shields.io to fetch it. The existing `.gitignore` from Plan A doesn't ignore `evals/`, so this should be fine. Just verify.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/evals.yml
git commit -m "ci: add evals workflow that runs harness and commits updated badge"
```

> **Engineer note:** The badge URL in the README points to `https://raw.githubusercontent.com/Umarfarook1/mcp-bigquery-evals/main/evals/badge.json`. After the first eval run lands the file, shields.io will start serving the badge. Until then, the badge in the README will show "invalid" — that's expected and resolves on the first eval CI run.

---

### Task 23: PyPI publish prep (version + classifiers + build verification)

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update version + add classifiers**

In `pyproject.toml`:
```toml
[project]
name = "mcp-bigquery-evals"
version = "0.1.0"  # FIRST PUBLIC RELEASE
description = "An MCP server for BigQuery exploration with cost guardrails and a built-in NL→SQL eval harness."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "Umarfarook Gurramkonda", email = "umarfarook0yt@gmail.com" }]
keywords = ["mcp", "bigquery", "llm", "nl2sql", "claude", "evals"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Database",
    "Topic :: Software Development :: Libraries :: Python Modules",
]

[project.urls]
Homepage = "https://github.com/Umarfarook1/mcp-bigquery-evals"
Repository = "https://github.com/Umarfarook1/mcp-bigquery-evals"
Issues = "https://github.com/Umarfarook1/mcp-bigquery-evals/issues"
```

(Keep all other sections — dependencies, build-system, tool configs — unchanged.)

- [ ] **Step 2: Build and verify the artifact**

```bash
source .venv/Scripts/activate
pip install --upgrade build twine
python -m build
ls dist/
```

Expected output: `mcp_bigquery_evals-0.1.0-py3-none-any.whl` and `mcp_bigquery_evals-0.1.0.tar.gz`.

Verify the package metadata:
```bash
twine check dist/*
```

Expected: `Checking dist/mcp_bigquery_evals-0.1.0-py3-none-any.whl: PASSED`.

Test install in a temp venv:
```bash
python -m venv /tmp/testvenv
source /tmp/testvenv/Scripts/activate
pip install dist/mcp_bigquery_evals-0.1.0-py3-none-any.whl
mcp-bigquery-evals --help
```

Expected: help text prints. Then deactivate and clean up.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "release: bump to 0.1.0 with PyPI metadata (URLs, keywords, classifiers)"
```

---

### Task 24: PyPI publish (manual step; documented)

**Files:**
- (Manual action; no files committed)

- [ ] **Step 1: Create a PyPI account** (if you don't have one)

Visit https://pypi.org/account/register/ and verify your email.

- [ ] **Step 2: Create a per-project API token**

After registering and uploading the first version manually with username/password, go to https://pypi.org/manage/account/token/ → "Add API token" → scope it to the `mcp-bigquery-evals` project. Copy the token (starts with `pypi-`).

- [ ] **Step 3: Upload to PyPI**

```bash
twine upload dist/* --username __token__ --password <pypi-token>
```

Expected: progress bar, then `View at: https://pypi.org/project/mcp-bigquery-evals/0.1.0/`.

- [ ] **Step 4: Verify zero-install works**

In a fresh terminal (not in this venv):
```bash
uvx mcp-bigquery-evals --help
```

Expected: help text. If `uvx` errors with "no such package", wait 30 seconds for PyPI to propagate.

- [ ] **Step 5: Tag the release**

```bash
git tag -a v0.1.0 -m "v0.1.0: first public release"
git push origin main --tags
```

> **Engineer note:** This task involves a PyPI account action you should perform yourself (creating an account, generating a token, deciding on the username). Don't have a subagent paste your PyPI credentials anywhere. Run the `twine upload` command interactively.

---

### Task 25: PR to `awesome-mcp-servers` (manual step; documented)

**Files:**
- (Manual action)

- [ ] **Step 1: Fork `awesome-mcp-servers`**

Visit https://github.com/punkpeye/awesome-mcp-servers and click Fork.

- [ ] **Step 2: Add an entry**

In the forked repo, edit `README.md`. Find the `Databases` section and add:

```markdown
- [mcp-bigquery-evals](https://github.com/Umarfarook1/mcp-bigquery-evals) - BigQuery MCP server with mandatory dry-run cost guardrails and a built-in NL→SQL eval harness with live accuracy badge.
```

(Place it alphabetically among other database MCPs.)

- [ ] **Step 3: Open a PR**

Title: `Add mcp-bigquery-evals (BigQuery + cost guardrails + evals)`

Body:
```
Adds [mcp-bigquery-evals](https://github.com/Umarfarook1/mcp-bigquery-evals).

What makes it different from existing BigQuery MCPs:
- Mandatory dry-run cost cap on every run_query (returns structured error, agent can self-correct)
- Built-in NL→SQL eval harness with result-set-equivalence methodology
- Live accuracy badge in the README, updated on every main merge
- Read-only by design (no write operations)

Quickstart and screenshots are in the README.
```

- [ ] **Step 4: Wait for review**

Maintainer will likely ask for minor edits. Address feedback.

---

### Task 26: Two blog post outlines

**Files:**
- Create: `docs/blog/2026-05-XX-bigquery-mcp-evals.md`
- Create: `docs/blog/2026-05-XX-no-explain-query.md`

Outlines, not full posts. You'll flesh them out and publish on your blog.

- [ ] **Step 1: Write outline 1**

`docs/blog/2026-05-XX-bigquery-mcp-evals.md`:
```markdown
# I built a BigQuery MCP server with built-in evals — here's what I learned

## Outline

### Hook
- "Most AI agents that touch warehouses fail in three ways: cost, correctness, and unfounded confidence. Here's how I tried to fix all three in a single weekend project."

### What I built
- mcp-bigquery-evals
- 7 read-only tools, mandatory dry-run cost caps, in-the-box result-set-equivalence eval harness
- Live in Claude Desktop in 5 minutes

### Three design decisions worth talking about

1. **Why the cost cap is mandatory, not advisory**
   - Real story: an agent ran a `SELECT *` against a billion-row table during testing
   - Solution: mandatory dry-run before every execute, refuse if estimate > cap
   - Show the structured error response and how the agent self-corrects

2. **Why I built the eval harness on day 1, not as a v2 nice-to-have**
   - Without measurable accuracy, "the agent is good now" is a vibe
   - Result-set equivalence > LLM-as-judge (link to Hamel Husain post)
   - Show the badge in the README updating on each commit

3. **Why I dropped explain_query**
   - Tease the next post

### What surprised me
- How much faster the FakeBigQueryClient (sqlite-backed) made development
- How much the cost cap caught — even my own queries during testing
- The eval methodology debate is more interesting than the implementation

### What's next
- Standalone NL2SQL leaderboard (Project 2 of my five)
- Voice-driven version (Project 3)
- Link to the project portfolio plan

### Links
- Repo
- PyPI
- The eval methodology doc
```

- [ ] **Step 2: Write outline 2**

`docs/blog/2026-05-XX-no-explain-query.md`:
```markdown
# Why I dropped `explain_query` from my MCP server

## Outline

### Hook
- "I had `explain_query` in my MCP tool list for two days before I realized it was a circular design smell."

### The setup
- I was building a BigQuery MCP server for Claude Desktop
- Initial tool list included `explain_query(sql) -> str` — call Claude, ask it to summarize what the SQL does in plain English
- Idea: let the agent verify its own SQL intent before running it

### The realization
- The MCP server's only consumer is Claude
- I was about to put a Claude call inside a server that's only ever called by Claude
- The agent already has the SQL it just generated; it can summarize itself

### Why this matters as a general principle
- LLM-inside-LLM-tool is a code smell
- Server should be deterministic; reasoning belongs in the agent
- Two reasons:
  1. Cost: every call to the tool now incurs an extra LLM round-trip
  2. Reliability: the server now has an external dependency that can rate-limit, time out, or change behavior independently

### When IS putting an LLM inside a tool actually right?
- When the tool's consumer is NOT an LLM (e.g., a CLI used by humans)
- When the LLM is doing work the consumer can't do (e.g., embeddings, image gen)
- When the LLM call is structurally different from the consumer's reasoning (e.g., specialized fine-tune)

### What I do instead
- Tools return structured data
- The agent reasons about the data
- I get a deterministic, testable, debuggable server

### Generalization
- Every MCP server should ask: "would my consumer (an LLM) want me to do this work for them, or would they rather have the data and decide for themselves?"
- Default to the latter

### Links
- Repo
- The previous post
- MCP best practices doc (TBD; consider writing one)
```

- [ ] **Step 3: Commit**

```bash
git add docs/blog/
git commit -m "docs: add blog post outlines for v1.0 launch"
```

---

## Plan B Acceptance

After Task 26, the following are true:

1. `RealBigQueryClient` works end-to-end against real BigQuery (verified by `pytest -m bq`)
2. Eval harness runs against real BQ + real Anthropic (verified by `pytest -m live`)
3. Live accuracy badge in the README, updated by CI on every main merge
4. Package published to PyPI; `uvx mcp-bigquery-evals` works on a clean machine
5. PR opened to `awesome-mcp-servers`
6. Two blog post outlines committed (ready to flesh out and publish on Substack/Medium/personal blog)
7. CI green on `main`
8. Git tag `v0.1.0` exists locally and on origin

## What's NOT in Plan B (deferred to v1.1+)

- Global daily cost limit (`MCP_BIGQUERY_GLOBAL_DAILY_LIMIT_USD` env var)
- Query history (read-only `list_recent_queries` tool)
- Result caching
- Multi-project support per server instance
- Translation of bare-ref SQL with three-part identifiers
- Project 2 (standalone `nl2sql-evals` package extraction)

## Order-flexibility notes

Tasks T1-T8 (Group 1: carry-over fixes + RealBigQueryClient) are sequential and must come first. Within Group 2 (T9-T14: eval harness against fake), the order is also strict because each task depends on the prior one. Group 3 (T15+: real BQ + release) requires GCP credentials.

If you stop after T14, you have:
- A working MCP server with both real and fake BQ implementations
- A working eval harness end-to-end against the fake (with mock model)
- All Plan A carry-overs fixed

You can resume at T15+ once GCP is set up. The badge in the README will show "invalid" until T22 lands its first run, but everything else is functional.
