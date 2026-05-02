# mcp-bigquery-evals - Plan A (Core MCP Server) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working stdio MCP server with all 7 read-only BigQuery tools, fully tested against an in-memory `FakeBigQueryClient`. No GCP credentials required.

**Architecture:** `BigQueryClient` is a `Protocol` with two future implementations (real, fake). Plan A delivers the fake plus the entire MCP layer - tool handlers, server registration, stdio entrypoint, CLI. After Plan A, you can launch the server in Claude Desktop and exercise every tool against fixture data.

**Tech Stack:** Python 3.11+, `mcp` (official Python SDK), `pydantic`, `rapidfuzz`, `pyyaml`, `pytest`, `pytest-asyncio`, `ruff`, `mypy`. SQLite (stdlib) is used inside `FakeBigQueryClient` to execute SQL against fixture data.

**Phase B (separate plan, written after Plan A is shipped):** RealBigQueryClient, eval harness, CI workflows, README, PyPI publish.

---

## File Structure (created across all Plan A tasks)

```
mcp-bigquery-evals/
├── pyproject.toml                                  # Task 1
├── LICENSE                                         # Task 1
├── README.md                                       # Task 1 (placeholder)
├── src/mcp_bigquery_evals/
│   ├── __init__.py                                 # Task 1
│   ├── __main__.py                                 # Task 18
│   ├── cli.py                                      # Task 18
│   ├── server.py                                   # Task 17
│   ├── bq/
│   │   ├── __init__.py                             # Task 2
│   │   ├── types.py                                # Task 2 (dataclasses)
│   │   ├── protocol.py                             # Task 3 (BigQueryClient Protocol)
│   │   └── fake.py                                 # Tasks 5, 6, 7
│   ├── guardrails.py                               # Task 9
│   ├── schema_search.py                            # Task 8
│   └── tools/
│       ├── __init__.py                             # Task 10
│       ├── list_datasets.py                        # Task 10
│       ├── list_tables.py                          # Task 11
│       ├── describe_table.py                       # Task 12
│       ├── sample_table.py                         # Task 13
│       ├── search_schema.py                        # Task 14
│       ├── estimate_cost.py                        # Task 15
│       └── run_query.py                            # Task 16
└── tests/
    ├── __init__.py                                 # Task 1
    ├── unit/
    │   ├── __init__.py                             # Task 2
    │   ├── test_types.py                           # Task 2
    │   ├── test_fake_client.py                     # Tasks 5, 6, 7
    │   ├── test_schema_search.py                   # Task 8
    │   ├── test_guardrails.py                      # Task 9
    │   └── test_tools/
    │       ├── __init__.py                         # Task 10
    │       ├── test_list_datasets.py               # Task 10
    │       ├── test_list_tables.py                 # Task 11
    │       ├── test_describe_table.py              # Task 12
    │       ├── test_sample_table.py                # Task 13
    │       ├── test_search_schema.py               # Task 14
    │       ├── test_estimate_cost.py               # Task 15
    │       └── test_run_query.py                   # Task 16
    ├── integration/
    │   └── test_server_smoke.py                    # Task 19
    └── fixtures/
        └── fake_warehouse.yaml                     # Task 4
```

**Single-responsibility rule applied:** one MCP tool = one file under `tools/`. One concrete BQ client = one file under `bq/`. Each file is small enough to hold in your head.

---

### Task 1: Repo scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `LICENSE`
- Create: `README.md`
- Create: `src/mcp_bigquery_evals/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "mcp-bigquery-evals"
version = "0.1.0"
description = "An MCP server for BigQuery exploration with cost guardrails and a built-in NL2SQL eval harness."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "Umarfarook Gurramkonda", email = "umarfarook0yt@gmail.com" }]
classifiers = [
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
]
dependencies = [
    "mcp>=1.0.0",
    "pydantic>=2.0",
    "rapidfuzz>=3.0",
    "pyyaml>=6.0",
    "structlog>=24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.5",
    "mypy>=1.10",
]
bq = [
    "google-cloud-bigquery>=3.0",  # only needed for RealBigQueryClient (Plan B)
]

[project.scripts]
mcp-bigquery-evals = "mcp_bigquery_evals.cli:main"

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N"]

[tool.mypy]
python_version = "3.11"
strict = true
files = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Write `LICENSE`** (standard MIT)

```
MIT License

Copyright (c) 2026 Umarfarook Gurramkonda

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: Write `README.md` placeholder**

```markdown
# mcp-bigquery-evals

An MCP server for BigQuery exploration with cost guardrails and a built-in NL→SQL eval harness.

Status: in active development. Full quickstart will land with v1.0.

See `docs/superpowers/specs/2026-05-02-bq-nl2sql-mcp-design.md` for the design.
```

- [ ] **Step 4: Write empty `__init__.py` files**

`src/mcp_bigquery_evals/__init__.py`:
```python
__version__ = "0.1.0"
```

`tests/__init__.py`:
```python
```

- [ ] **Step 5: Install dev deps and verify**

Run:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pytest --version
ruff --version
mypy --version
```
Expected: all three print version numbers without error.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml LICENSE README.md src/ tests/
git commit -m "scaffold: package skeleton, pyproject, MIT license"
```

---

### Task 2: Domain types (dataclasses)

**Files:**
- Create: `src/mcp_bigquery_evals/bq/__init__.py`
- Create: `src/mcp_bigquery_evals/bq/types.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/test_types.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_types.py`:
```python
from mcp_bigquery_evals.bq.types import (
    Column,
    Dataset,
    DryRunResult,
    QueryResult,
    Table,
)


def test_dataset_minimal_fields():
    d = Dataset(id="analytics", location="US", description=None)
    assert d.id == "analytics"
    assert d.location == "US"
    assert d.description is None


def test_table_with_metadata():
    t = Table(id="analytics.users", row_count=1000, size_bytes=50_000)
    assert t.id == "analytics.users"
    assert t.row_count == 1000
    assert t.size_bytes == 50_000


def test_column_with_description():
    c = Column(name="user_id", type="STRING", description="primary key")
    assert c.name == "user_id"
    assert c.type == "STRING"
    assert c.description == "primary key"


def test_dry_run_result():
    r = DryRunResult(bytes_scanned=1_000_000, estimated_usd=0.000005)
    assert r.bytes_scanned == 1_000_000
    assert r.estimated_usd == 0.000005


def test_query_result():
    r = QueryResult(
        rows=[{"a": 1}, {"a": 2}],
        bytes_scanned=2048,
        cost_usd=0.00001,
        ms=120,
    )
    assert len(r.rows) == 2
    assert r.bytes_scanned == 2048
    assert r.ms == 120
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_types.py -v`
Expected: ImportError or ModuleNotFoundError on `mcp_bigquery_evals.bq.types`.

- [ ] **Step 3: Write the dataclasses**

`src/mcp_bigquery_evals/bq/__init__.py`:
```python
```

`src/mcp_bigquery_evals/bq/types.py`:
```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Dataset:
    id: str
    location: str
    description: str | None


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    type: str
    description: str | None


@dataclass(frozen=True, slots=True)
class Table:
    id: str
    row_count: int
    size_bytes: int


@dataclass(frozen=True, slots=True)
class TableSchema:
    """Returned by describe_table - table metadata + column list."""

    table: Table
    columns: list[Column]


@dataclass(frozen=True, slots=True)
class DryRunResult:
    bytes_scanned: int
    estimated_usd: float


@dataclass(frozen=True, slots=True)
class QueryResult:
    rows: list[dict]
    bytes_scanned: int
    cost_usd: float
    ms: int
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_types.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/bq/ tests/unit/
git commit -m "bq: add domain dataclasses (Dataset, Table, Column, TableSchema, DryRunResult, QueryResult)"
```

---

### Task 3: BigQueryClient Protocol

**Files:**
- Create: `src/mcp_bigquery_evals/bq/protocol.py`

- [ ] **Step 1: Write the Protocol**

`src/mcp_bigquery_evals/bq/protocol.py`:
```python
from typing import Protocol, runtime_checkable

from mcp_bigquery_evals.bq.types import (
    Dataset,
    DryRunResult,
    QueryResult,
    Table,
    TableSchema,
)


@runtime_checkable
class BigQueryClient(Protocol):
    """The single seam between the MCP server and BigQuery.

    Two implementations: RealBigQueryClient (google-cloud-bigquery, Plan B)
    and FakeBigQueryClient (in-memory, yaml-loaded).
    """

    def list_datasets(self) -> list[Dataset]:
        ...

    def list_tables(self, dataset_id: str) -> list[Table]:
        ...

    def get_table(self, table_id: str) -> TableSchema:
        ...

    def sample_rows(self, table_id: str, n: int) -> list[dict]:
        ...

    def dry_run(self, sql: str) -> DryRunResult:
        ...

    def execute(self, sql: str) -> QueryResult:
        ...
```

- [ ] **Step 2: Quick type-check verification**

Run: `mypy src/mcp_bigquery_evals/bq/protocol.py`
Expected: `Success: no issues found in 1 source file`.

(No runtime tests for the Protocol itself - it's structural; correctness is verified by the FakeBigQueryClient tests in Tasks 5–7 which assert `isinstance(client, BigQueryClient)`.)

- [ ] **Step 3: Commit**

```bash
git add src/mcp_bigquery_evals/bq/protocol.py
git commit -m "bq: add BigQueryClient Protocol (single seam between server and BQ)"
```

---

### Task 4: Test fixture YAML

**Files:**
- Create: `tests/fixtures/__init__.py`
- Create: `tests/fixtures/fake_warehouse.yaml`

- [ ] **Step 1: Write the fixture**

`tests/fixtures/__init__.py`:
```python
```

`tests/fixtures/fake_warehouse.yaml`:
```yaml
# Fake BigQuery warehouse used by FakeBigQueryClient in unit tests.
# Two datasets, three tables total. Small but covers list/describe/sample/query paths.
datasets:
  - id: analytics
    location: US
    description: User and event data for the demo product.
  - id: ops
    location: US
    description: Operational metrics.

tables:
  - id: analytics.users
    description: One row per registered user.
    columns:
      - { name: user_id, type: STRING, description: Primary key. }
      - { name: email, type: STRING, description: Login email. }
      - { name: signup_date, type: DATE, description: Date the user signed up. }
      - { name: country, type: STRING, description: ISO country code. }
    rows:
      - { user_id: u1, email: alice@example.com, signup_date: '2026-01-15', country: US }
      - { user_id: u2, email: bob@example.com,   signup_date: '2026-02-03', country: US }
      - { user_id: u3, email: carol@example.com, signup_date: '2026-02-20', country: IN }
      - { user_id: u4, email: dave@example.com,  signup_date: '2026-03-10', country: GB }
      - { user_id: u5, email: eve@example.com,   signup_date: '2026-04-01', country: IN }

  - id: analytics.events
    description: One row per user event (page view, click, etc.).
    columns:
      - { name: event_id, type: STRING, description: Unique event id. }
      - { name: user_id, type: STRING, description: FK to analytics.users.user_id. }
      - { name: event_type, type: STRING, description: e.g. page_view, click. }
      - { name: ts, type: TIMESTAMP, description: Event timestamp. }
    rows:
      - { event_id: e1, user_id: u1, event_type: page_view, ts: '2026-04-20T10:00:00' }
      - { event_id: e2, user_id: u1, event_type: click,     ts: '2026-04-20T10:01:00' }
      - { event_id: e3, user_id: u2, event_type: page_view, ts: '2026-04-21T11:00:00' }
      - { event_id: e4, user_id: u3, event_type: page_view, ts: '2026-04-22T09:30:00' }
      - { event_id: e5, user_id: u3, event_type: click,     ts: '2026-04-22T09:31:00' }
      - { event_id: e6, user_id: u5, event_type: page_view, ts: '2026-04-25T14:00:00' }

  - id: ops.daily_metrics
    description: One row per day with platform-wide metrics.
    columns:
      - { name: date, type: DATE, description: Metric day. }
      - { name: dau, type: INT64, description: Daily active users. }
      - { name: revenue_usd, type: FLOAT64, description: Daily revenue in USD. }
    rows:
      - { date: '2026-04-20', dau: 1234, revenue_usd: 456.78 }
      - { date: '2026-04-21', dau: 1300, revenue_usd: 512.10 }
      - { date: '2026-04-22', dau: 1450, revenue_usd: 599.25 }
```

- [ ] **Step 2: Commit**

```bash
git add tests/fixtures/
git commit -m "tests: add fake_warehouse.yaml fixture (2 datasets, 3 tables)"
```

---

### Task 5: FakeBigQueryClient - discovery methods

**Files:**
- Create: `src/mcp_bigquery_evals/bq/fake.py`
- Create: `tests/unit/test_fake_client.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_fake_client.py`:
```python
from pathlib import Path

import pytest

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.bq.protocol import BigQueryClient

FIXTURE = Path(__file__).parent.parent / "fixtures" / "fake_warehouse.yaml"


@pytest.fixture
def client() -> FakeBigQueryClient:
    return FakeBigQueryClient.from_yaml(FIXTURE)


def test_implements_protocol(client: FakeBigQueryClient):
    assert isinstance(client, BigQueryClient)


def test_list_datasets(client: FakeBigQueryClient):
    datasets = client.list_datasets()
    ids = [d.id for d in datasets]
    assert ids == ["analytics", "ops"]
    analytics = next(d for d in datasets if d.id == "analytics")
    assert analytics.location == "US"
    assert "User and event data" in (analytics.description or "")


def test_list_tables(client: FakeBigQueryClient):
    tables = client.list_tables("analytics")
    ids = [t.id for t in tables]
    assert ids == ["analytics.users", "analytics.events"]


def test_list_tables_unknown_dataset_returns_empty(client: FakeBigQueryClient):
    assert client.list_tables("nonexistent") == []


def test_get_table_returns_schema(client: FakeBigQueryClient):
    schema = client.get_table("analytics.users")
    assert schema.table.id == "analytics.users"
    col_names = [c.name for c in schema.columns]
    assert col_names == ["user_id", "email", "signup_date", "country"]
    assert schema.table.row_count == 5


def test_get_table_unknown_raises(client: FakeBigQueryClient):
    with pytest.raises(KeyError):
        client.get_table("analytics.nonexistent")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_fake_client.py -v`
Expected: ImportError on `mcp_bigquery_evals.bq.fake`.

- [ ] **Step 3: Implement `FakeBigQueryClient` discovery methods**

`src/mcp_bigquery_evals/bq/fake.py`:
```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mcp_bigquery_evals.bq.types import (
    Column,
    Dataset,
    QueryResult,
    Table,
    TableSchema,
    DryRunResult,
)


class FakeBigQueryClient:
    """In-memory BigQueryClient for unit tests and credential-free local dev.

    Loads schema + rows from a yaml fixture; executes SQL via sqlite under the hood.
    """

    def __init__(
        self,
        datasets: list[Dataset],
        tables: dict[str, TableSchema],
        rows: dict[str, list[dict[str, Any]]],
    ) -> None:
        self._datasets = datasets
        self._tables = tables
        self._rows = rows

    @classmethod
    def from_yaml(cls, path: Path) -> FakeBigQueryClient:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        datasets = [
            Dataset(id=d["id"], location=d["location"], description=d.get("description"))
            for d in data["datasets"]
        ]
        tables: dict[str, TableSchema] = {}
        rows: dict[str, list[dict[str, Any]]] = {}
        for t in data["tables"]:
            cols = [
                Column(name=c["name"], type=c["type"], description=c.get("description"))
                for c in t["columns"]
            ]
            t_rows = list(t.get("rows", []))
            tbl = Table(
                id=t["id"],
                row_count=len(t_rows),
                size_bytes=_estimate_size_bytes(cols, t_rows),
            )
            tables[t["id"]] = TableSchema(table=tbl, columns=cols)
            rows[t["id"]] = t_rows
        return cls(datasets=datasets, tables=tables, rows=rows)

    # ---- BigQueryClient Protocol ----

    def list_datasets(self) -> list[Dataset]:
        return list(self._datasets)

    def list_tables(self, dataset_id: str) -> list[Table]:
        prefix = f"{dataset_id}."
        return [s.table for tid, s in self._tables.items() if tid.startswith(prefix)]

    def get_table(self, table_id: str) -> TableSchema:
        if table_id not in self._tables:
            raise KeyError(table_id)
        return self._tables[table_id]

    def sample_rows(self, table_id: str, n: int) -> list[dict]:
        raise NotImplementedError  # Task 6

    def dry_run(self, sql: str) -> DryRunResult:
        raise NotImplementedError  # Task 7

    def execute(self, sql: str) -> QueryResult:
        raise NotImplementedError  # Task 7


def _estimate_size_bytes(columns: list[Column], rows: list[dict[str, Any]]) -> int:
    """Crude size estimate: 32 bytes per cell, for unit-test purposes only."""
    return len(columns) * len(rows) * 32
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_fake_client.py -v`
Expected: 6 passed (the `test_implements_protocol` test plus 5 discovery tests).

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/bq/fake.py tests/unit/test_fake_client.py
git commit -m "bq: add FakeBigQueryClient discovery methods (list_datasets/tables, get_table)"
```

---

### Task 6: FakeBigQueryClient - sample_rows

**Files:**
- Modify: `src/mcp_bigquery_evals/bq/fake.py` (replace `sample_rows` body)
- Modify: `tests/unit/test_fake_client.py` (append tests)

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/test_fake_client.py`:
```python
def test_sample_rows_returns_n(client: FakeBigQueryClient):
    rows = client.sample_rows("analytics.users", n=3)
    assert len(rows) == 3
    assert {"user_id", "email", "signup_date", "country"} <= set(rows[0].keys())


def test_sample_rows_caps_at_total(client: FakeBigQueryClient):
    rows = client.sample_rows("analytics.users", n=999)
    assert len(rows) == 5  # only 5 rows in fixture


def test_sample_rows_unknown_table_raises(client: FakeBigQueryClient):
    with pytest.raises(KeyError):
        client.sample_rows("analytics.nonexistent", n=1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_fake_client.py -v -k sample`
Expected: 3 fails with NotImplementedError.

- [ ] **Step 3: Implement `sample_rows`**

In `src/mcp_bigquery_evals/bq/fake.py`, replace the `sample_rows` body:
```python
    def sample_rows(self, table_id: str, n: int) -> list[dict]:
        if table_id not in self._rows:
            raise KeyError(table_id)
        return list(self._rows[table_id][:n])
```

(Note: returns the *first* n rows rather than a random sample. Deterministic tests > true randomness for unit tests. The Real client can do `TABLESAMPLE` for true sampling.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_fake_client.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/bq/fake.py tests/unit/test_fake_client.py
git commit -m "bq: implement FakeBigQueryClient.sample_rows (deterministic head)"
```

---

### Task 7: FakeBigQueryClient - dry_run + execute (sqlite backend)

**Files:**
- Modify: `src/mcp_bigquery_evals/bq/fake.py` (sqlite backend + dry_run + execute)
- Modify: `tests/unit/test_fake_client.py` (append tests)

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/test_fake_client.py`:
```python
def test_execute_select_count(client: FakeBigQueryClient):
    r = client.execute("SELECT COUNT(*) AS n FROM `analytics.users`")
    assert r.rows == [{"n": 5}]
    assert r.bytes_scanned > 0
    assert r.cost_usd >= 0
    assert r.ms >= 0


def test_execute_select_filter(client: FakeBigQueryClient):
    r = client.execute(
        "SELECT user_id FROM `analytics.users` WHERE country = 'IN' ORDER BY user_id"
    )
    assert r.rows == [{"user_id": "u3"}, {"user_id": "u5"}]


def test_execute_join(client: FakeBigQueryClient):
    r = client.execute(
        "SELECT u.country, COUNT(*) AS events "
        "FROM `analytics.users` u "
        "JOIN `analytics.events` e ON u.user_id = e.user_id "
        "GROUP BY u.country "
        "ORDER BY u.country"
    )
    assert r.rows == [
        {"country": "IN", "events": 3},
        {"country": "US", "events": 3},
    ]


def test_dry_run_returns_estimate(client: FakeBigQueryClient):
    r = client.dry_run("SELECT * FROM `analytics.users`")
    assert r.bytes_scanned > 0
    assert r.estimated_usd >= 0


def test_execute_invalid_sql_raises(client: FakeBigQueryClient):
    with pytest.raises(ValueError):
        client.execute("NOT A QUERY")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_fake_client.py -v -k "execute or dry_run"`
Expected: 5 fails with NotImplementedError or sqlite errors.

- [ ] **Step 3: Implement sqlite backend, dry_run, execute**

Replace the entire body of `src/mcp_bigquery_evals/bq/fake.py` with:
```python
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import Any

import yaml

from mcp_bigquery_evals.bq.types import (
    Column,
    Dataset,
    DryRunResult,
    QueryResult,
    Table,
    TableSchema,
)

# BigQuery on-demand pricing: $5 per TB scanned. We estimate using the same rate
# in the fake so cost numbers in tests match the production formula.
_USD_PER_BYTE = 5.0 / (1024**4)


class FakeBigQueryClient:
    """In-memory BigQueryClient backed by sqlite for SQL execution."""

    def __init__(
        self,
        datasets: list[Dataset],
        tables: dict[str, TableSchema],
        rows: dict[str, list[dict[str, Any]]],
    ) -> None:
        self._datasets = datasets
        self._tables = tables
        self._rows = rows
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row
        self._load_into_sqlite()

    # ---- Construction ----

    @classmethod
    def from_yaml(cls, path: Path) -> FakeBigQueryClient:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        datasets = [
            Dataset(id=d["id"], location=d["location"], description=d.get("description"))
            for d in data["datasets"]
        ]
        tables: dict[str, TableSchema] = {}
        rows: dict[str, list[dict[str, Any]]] = {}
        for t in data["tables"]:
            cols = [
                Column(name=c["name"], type=c["type"], description=c.get("description"))
                for c in t["columns"]
            ]
            t_rows = list(t.get("rows", []))
            tbl = Table(
                id=t["id"],
                row_count=len(t_rows),
                size_bytes=_estimate_size_bytes(cols, t_rows),
            )
            tables[t["id"]] = TableSchema(table=tbl, columns=cols)
            rows[t["id"]] = t_rows
        return cls(datasets=datasets, tables=tables, rows=rows)

    def _load_into_sqlite(self) -> None:
        """Create one sqlite table per BQ table; sqlite identifier = BQ table_id with '.' → '__'."""
        cur = self._conn.cursor()
        for tid, schema in self._tables.items():
            sqlite_name = _sqlite_name(tid)
            cols_sql = ", ".join(f'"{c.name}"' for c in schema.columns)
            cur.execute(f'CREATE TABLE "{sqlite_name}" ({cols_sql})')
            for row in self._rows.get(tid, []):
                placeholders = ", ".join("?" for _ in schema.columns)
                values = [row.get(c.name) for c in schema.columns]
                cur.execute(
                    f'INSERT INTO "{sqlite_name}" ({cols_sql}) VALUES ({placeholders})',
                    values,
                )
        self._conn.commit()

    # ---- BigQueryClient Protocol ----

    def list_datasets(self) -> list[Dataset]:
        return list(self._datasets)

    def list_tables(self, dataset_id: str) -> list[Table]:
        prefix = f"{dataset_id}."
        return [s.table for tid, s in self._tables.items() if tid.startswith(prefix)]

    def get_table(self, table_id: str) -> TableSchema:
        if table_id not in self._tables:
            raise KeyError(table_id)
        return self._tables[table_id]

    def sample_rows(self, table_id: str, n: int) -> list[dict]:
        if table_id not in self._rows:
            raise KeyError(table_id)
        return list(self._rows[table_id][:n])

    def dry_run(self, sql: str) -> DryRunResult:
        # Estimate: sum of size_bytes for every table referenced in the SQL.
        bytes_scanned = sum(
            self._tables[tid].table.size_bytes
            for tid in self._tables
            if _table_referenced(sql, tid)
        )
        return DryRunResult(bytes_scanned=bytes_scanned, estimated_usd=bytes_scanned * _USD_PER_BYTE)

    def execute(self, sql: str) -> QueryResult:
        translated = _bq_to_sqlite(sql)
        start = time.perf_counter()
        try:
            cur = self._conn.execute(translated)
            rows = [dict(r) for r in cur.fetchall()]
        except sqlite3.Error as e:
            raise ValueError(f"SQL execution failed: {e}") from e
        ms = int((time.perf_counter() - start) * 1000)
        dr = self.dry_run(sql)
        return QueryResult(
            rows=rows,
            bytes_scanned=dr.bytes_scanned,
            cost_usd=dr.estimated_usd,
            ms=ms,
        )


# ---- Helpers ----

def _estimate_size_bytes(columns: list[Column], rows: list[dict[str, Any]]) -> int:
    """Crude estimate: 32 bytes per cell."""
    return len(columns) * len(rows) * 32


def _sqlite_name(table_id: str) -> str:
    return table_id.replace(".", "__")


def _table_referenced(sql: str, table_id: str) -> bool:
    """Loose check: BQ identifier with backticks or bare appears in SQL."""
    pattern = rf"`?{re.escape(table_id)}`?"
    return re.search(pattern, sql) is not None


def _bq_to_sqlite(sql: str) -> str:
    """Translate the small subset of BQ syntax we need for fixture-backed tests:
    - `dataset.table` backticked references → dataset__table
    - bare dataset.table references         → dataset__table
    """
    # Backticked: `analytics.users` → analytics__users (no quotes - sqlite identifier)
    sql = re.sub(
        r"`([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)`",
        r"\1__\2",
        sql,
    )
    # Bare: analytics.users → analytics__users (don't touch column refs like u.country)
    # We only translate identifiers we know about.
    return sql
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_fake_client.py -v`
Expected: 14 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/bq/fake.py tests/unit/test_fake_client.py
git commit -m "bq: implement FakeBigQueryClient.dry_run and .execute via sqlite backend"
```

---

### Task 8: Schema search helper (rapidfuzz)

**Files:**
- Create: `src/mcp_bigquery_evals/schema_search.py`
- Create: `tests/unit/test_schema_search.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_schema_search.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_schema_search.py -v`
Expected: ImportError on `mcp_bigquery_evals.schema_search`.

- [ ] **Step 3: Implement `search_schema`**

`src/mcp_bigquery_evals/schema_search.py`:
```python
from rapidfuzz import fuzz

from mcp_bigquery_evals.bq.protocol import BigQueryClient


def search_schema(
    client: BigQueryClient,
    term: str,
    limit: int = 10,
) -> list[dict]:
    """Fuzzy-match `term` against all column names across all tables.

    Returns up to `limit` hits as [{table, column, similarity}], sorted desc.
    Similarity is rapidfuzz's WRatio (0-100).
    """
    hits: list[dict] = []
    for dataset in client.list_datasets():
        for table in client.list_tables(dataset.id):
            schema = client.get_table(table.id)
            for col in schema.columns:
                score = fuzz.WRatio(term, col.name)
                hits.append(
                    {"table": table.id, "column": col.name, "similarity": int(score)}
                )
    hits.sort(key=lambda h: h["similarity"], reverse=True)
    return hits[:limit]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_schema_search.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/schema_search.py tests/unit/test_schema_search.py
git commit -m "search: add fuzzy schema-search helper (rapidfuzz WRatio)"
```

---

### Task 9: Cost guardrail logic

**Files:**
- Create: `src/mcp_bigquery_evals/guardrails.py`
- Create: `tests/unit/test_guardrails.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_guardrails.py`:
```python
from mcp_bigquery_evals.bq.types import DryRunResult
from mcp_bigquery_evals.guardrails import check_cost_cap, format_bytes


def test_format_bytes_units():
    assert format_bytes(0) == "0 B"
    assert format_bytes(500) == "500 B"
    assert format_bytes(2048) == "2.0 KB"
    assert format_bytes(5 * 1024 * 1024) == "5.0 MB"
    assert format_bytes(int(1.5 * 1024 * 1024 * 1024)) == "1.5 GB"


def test_check_cost_cap_under_limit_returns_none():
    dr = DryRunResult(bytes_scanned=1_000_000, estimated_usd=0.000005)
    assert check_cost_cap(dr, max_bytes_scanned=100_000_000) is None


def test_check_cost_cap_over_limit_returns_error_dict():
    dr = DryRunResult(bytes_scanned=1_500_000_000, estimated_usd=0.0075)
    err = check_cost_cap(dr, max_bytes_scanned=100_000_000)
    assert err is not None
    assert err["error"] == "cost_cap_exceeded"
    assert err["would_scan"] == "1.4 GB"
    assert err["cap"] == "95.4 MB"
    assert err["estimated_usd"] == 0.0075
    assert "narrow your WHERE clause" in err["hint"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_guardrails.py -v`
Expected: ImportError on `mcp_bigquery_evals.guardrails`.

- [ ] **Step 3: Implement `guardrails.py`**

`src/mcp_bigquery_evals/guardrails.py`:
```python
from mcp_bigquery_evals.bq.types import DryRunResult

DEFAULT_MAX_BYTES_SCANNED = 100 * 1024 * 1024  # 100 MB


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    for unit, divisor in (("KB", 1024), ("MB", 1024**2), ("GB", 1024**3), ("TB", 1024**4)):
        scaled = n / divisor
        if scaled < 1024:
            return f"{scaled:.1f} {unit}"
    return f"{n / (1024**5):.1f} PB"


def check_cost_cap(
    dr: DryRunResult,
    max_bytes_scanned: int,
) -> dict | None:
    """Returns None if under cap; structured error dict if over.

    The dict shape is the contract returned by run_query when refusing.
    """
    if dr.bytes_scanned <= max_bytes_scanned:
        return None
    return {
        "error": "cost_cap_exceeded",
        "would_scan": format_bytes(dr.bytes_scanned),
        "cap": format_bytes(max_bytes_scanned),
        "estimated_usd": dr.estimated_usd,
        "hint": (
            "narrow your WHERE clause or pass "
            f"max_bytes_scanned={dr.bytes_scanned} to override"
        ),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_guardrails.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/guardrails.py tests/unit/test_guardrails.py
git commit -m "guardrails: add cost cap check + byte formatting"
```

---

### Task 10: Tool - list_datasets

**Files:**
- Create: `src/mcp_bigquery_evals/tools/__init__.py`
- Create: `src/mcp_bigquery_evals/tools/list_datasets.py`
- Create: `tests/unit/test_tools/__init__.py`
- Create: `tests/unit/test_tools/test_list_datasets.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_tools/__init__.py`:
```python
```

`tests/unit/test_tools/test_list_datasets.py`:
```python
from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.list_datasets import list_datasets

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_list_datasets_returns_serializable_dicts():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = list_datasets(client)
    assert result == [
        {"id": "analytics", "location": "US", "description": "User and event data for the demo product."},
        {"id": "ops", "location": "US", "description": "Operational metrics."},
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_tools/test_list_datasets.py -v`
Expected: ImportError on `mcp_bigquery_evals.tools.list_datasets`.

- [ ] **Step 3: Implement the tool**

`src/mcp_bigquery_evals/tools/__init__.py`:
```python
```

`src/mcp_bigquery_evals/tools/list_datasets.py`:
```python
from mcp_bigquery_evals.bq.protocol import BigQueryClient


def list_datasets(client: BigQueryClient) -> list[dict]:
    """MCP tool: list all datasets in the configured project."""
    return [
        {"id": d.id, "location": d.location, "description": d.description}
        for d in client.list_datasets()
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_tools/test_list_datasets.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/tools/ tests/unit/test_tools/
git commit -m "tools: add list_datasets"
```

---

### Task 11: Tool - list_tables

**Files:**
- Create: `src/mcp_bigquery_evals/tools/list_tables.py`
- Create: `tests/unit/test_tools/test_list_tables.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_tools/test_list_tables.py`:
```python
from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.list_tables import list_tables

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_list_tables_for_known_dataset():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = list_tables(client, "analytics")
    ids = [t["id"] for t in result]
    assert ids == ["analytics.users", "analytics.events"]
    users = next(t for t in result if t["id"] == "analytics.users")
    assert users["row_count"] == 5
    assert users["size_bytes"] > 0


def test_list_tables_for_unknown_dataset_returns_empty():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    assert list_tables(client, "nonexistent") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_tools/test_list_tables.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the tool**

`src/mcp_bigquery_evals/tools/list_tables.py`:
```python
from mcp_bigquery_evals.bq.protocol import BigQueryClient


def list_tables(client: BigQueryClient, dataset_id: str) -> list[dict]:
    """MCP tool: list all tables in a given dataset."""
    return [
        {"id": t.id, "row_count": t.row_count, "size_bytes": t.size_bytes}
        for t in client.list_tables(dataset_id)
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_tools/test_list_tables.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/tools/list_tables.py tests/unit/test_tools/test_list_tables.py
git commit -m "tools: add list_tables"
```

---

### Task 12: Tool - describe_table

**Files:**
- Create: `src/mcp_bigquery_evals/tools/describe_table.py`
- Create: `tests/unit/test_tools/test_describe_table.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_tools/test_describe_table.py`:
```python
from pathlib import Path

import pytest

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.describe_table import describe_table

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_describe_table_returns_columns_and_metadata():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = describe_table(client, "analytics.users")
    assert result["row_count"] == 5
    assert result["size_bytes"] > 0
    col_names = [c["name"] for c in result["columns"]]
    assert col_names == ["user_id", "email", "signup_date", "country"]
    assert result["columns"][0] == {
        "name": "user_id",
        "type": "STRING",
        "description": "Primary key.",
    }


def test_describe_table_unknown_returns_error_dict():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = describe_table(client, "analytics.nonexistent")
    assert result == {"error": "table_not_found", "table_id": "analytics.nonexistent"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_tools/test_describe_table.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the tool**

`src/mcp_bigquery_evals/tools/describe_table.py`:
```python
from mcp_bigquery_evals.bq.protocol import BigQueryClient


def describe_table(client: BigQueryClient, table_id: str) -> dict:
    """MCP tool: schema + metadata for a single table."""
    try:
        schema = client.get_table(table_id)
    except KeyError:
        return {"error": "table_not_found", "table_id": table_id}
    return {
        "row_count": schema.table.row_count,
        "size_bytes": schema.table.size_bytes,
        "columns": [
            {"name": c.name, "type": c.type, "description": c.description}
            for c in schema.columns
        ],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_tools/test_describe_table.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/tools/describe_table.py tests/unit/test_tools/test_describe_table.py
git commit -m "tools: add describe_table"
```

---

### Task 13: Tool - sample_table

**Files:**
- Create: `src/mcp_bigquery_evals/tools/sample_table.py`
- Create: `tests/unit/test_tools/test_sample_table.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_tools/test_sample_table.py`:
```python
from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.sample_table import sample_table

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_sample_table_default_n():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = sample_table(client, "analytics.users")
    assert len(result) == 5  # default n=5; fixture has 5 rows
    assert result[0]["user_id"] == "u1"


def test_sample_table_custom_n():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = sample_table(client, "analytics.events", n=2)
    assert len(result) == 2


def test_sample_table_unknown_returns_error_dict():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = sample_table(client, "analytics.nonexistent")
    assert result == {"error": "table_not_found", "table_id": "analytics.nonexistent"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_tools/test_sample_table.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the tool**

`src/mcp_bigquery_evals/tools/sample_table.py`:
```python
from mcp_bigquery_evals.bq.protocol import BigQueryClient


def sample_table(client: BigQueryClient, table_id: str, n: int = 5) -> list[dict] | dict:
    """MCP tool: return up to n sample rows from a table."""
    try:
        return client.sample_rows(table_id, n)
    except KeyError:
        return {"error": "table_not_found", "table_id": table_id}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_tools/test_sample_table.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/tools/sample_table.py tests/unit/test_tools/test_sample_table.py
git commit -m "tools: add sample_table"
```

---

### Task 14: Tool - search_schema

**Files:**
- Create: `src/mcp_bigquery_evals/tools/search_schema.py`
- Create: `tests/unit/test_tools/test_search_schema.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_tools/test_search_schema.py`:
```python
from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.search_schema import search_schema_tool

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_search_schema_finds_user_id():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = search_schema_tool(client, "userid")
    assert isinstance(result, list)
    top = result[0]
    assert top["table"] == "analytics.users"
    assert top["column"] == "user_id"
    assert top["similarity"] >= 80
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_tools/test_search_schema.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the tool**

`src/mcp_bigquery_evals/tools/search_schema.py`:
```python
from mcp_bigquery_evals.bq.protocol import BigQueryClient
from mcp_bigquery_evals.schema_search import search_schema


def search_schema_tool(client: BigQueryClient, term: str) -> list[dict]:
    """MCP tool: fuzzy-match a term against all column names; return top hits."""
    return search_schema(client, term)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_tools/test_search_schema.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/tools/search_schema.py tests/unit/test_tools/test_search_schema.py
git commit -m "tools: add search_schema (wraps schema_search helper)"
```

---

### Task 15: Tool - estimate_cost

**Files:**
- Create: `src/mcp_bigquery_evals/tools/estimate_cost.py`
- Create: `tests/unit/test_tools/test_estimate_cost.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_tools/test_estimate_cost.py`:
```python
from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.estimate_cost import estimate_cost

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_estimate_cost_returns_bytes_and_usd():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = estimate_cost(client, "SELECT * FROM `analytics.users`")
    assert "bytes_scanned" in result
    assert "estimated_usd" in result
    assert result["bytes_scanned"] > 0
    assert result["estimated_usd"] >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_tools/test_estimate_cost.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the tool**

`src/mcp_bigquery_evals/tools/estimate_cost.py`:
```python
from mcp_bigquery_evals.bq.protocol import BigQueryClient


def estimate_cost(client: BigQueryClient, sql: str) -> dict:
    """MCP tool: dry-run a query, return bytes_scanned and estimated_usd."""
    dr = client.dry_run(sql)
    return {"bytes_scanned": dr.bytes_scanned, "estimated_usd": dr.estimated_usd}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_tools/test_estimate_cost.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/tools/estimate_cost.py tests/unit/test_tools/test_estimate_cost.py
git commit -m "tools: add estimate_cost (dry-run wrapper)"
```

---

### Task 16: Tool - run_query (with cost cap)

**Files:**
- Create: `src/mcp_bigquery_evals/tools/run_query.py`
- Create: `tests/unit/test_tools/test_run_query.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_tools/test_run_query.py`:
```python
from pathlib import Path

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.tools.run_query import run_query

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "fake_warehouse.yaml"


def test_run_query_under_cap_returns_rows():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = run_query(client, "SELECT COUNT(*) AS n FROM `analytics.users`")
    assert "rows" in result
    assert result["rows"] == [{"n": 5}]
    assert result["bytes_scanned"] >= 0
    assert result["cost_usd"] >= 0
    assert "ms" in result


def test_run_query_over_cap_returns_error():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    # max_bytes_scanned=1 forces refusal even on tiny fake data
    result = run_query(
        client,
        "SELECT * FROM `analytics.users`",
        max_bytes_scanned=1,
    )
    assert result["error"] == "cost_cap_exceeded"
    assert "would_scan" in result
    assert "cap" in result
    assert "hint" in result


def test_run_query_invalid_sql_returns_error():
    client = FakeBigQueryClient.from_yaml(FIXTURE)
    result = run_query(client, "NOT A QUERY")
    assert result["error"] == "execution_failed"
    assert "message" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_tools/test_run_query.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the tool**

`src/mcp_bigquery_evals/tools/run_query.py`:
```python
from mcp_bigquery_evals.bq.protocol import BigQueryClient
from mcp_bigquery_evals.guardrails import DEFAULT_MAX_BYTES_SCANNED, check_cost_cap


def run_query(
    client: BigQueryClient,
    sql: str,
    max_bytes_scanned: int = DEFAULT_MAX_BYTES_SCANNED,
) -> dict:
    """MCP tool: dry-run, check cap, then execute. Returns rows or structured error."""
    dr = client.dry_run(sql)
    cap_err = check_cost_cap(dr, max_bytes_scanned=max_bytes_scanned)
    if cap_err is not None:
        return cap_err
    try:
        result = client.execute(sql)
    except ValueError as e:
        return {"error": "execution_failed", "message": str(e)}
    return {
        "rows": result.rows,
        "bytes_scanned": result.bytes_scanned,
        "cost_usd": result.cost_usd,
        "ms": result.ms,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_tools/test_run_query.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/tools/run_query.py tests/unit/test_tools/test_run_query.py
git commit -m "tools: add run_query (mandatory dry-run + cost cap + structured errors)"
```

---

### Task 17: MCP server registration

**Files:**
- Create: `src/mcp_bigquery_evals/server.py`
- Append: `tests/unit/test_tools/test_server.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_tools/test_server.py`:
```python
from mcp_bigquery_evals.server import build_server


def test_build_server_registers_seven_tools(monkeypatch, tmp_path):
    """Sanity check that all seven MCP tools are registered."""
    fixture = tmp_path / "fake.yaml"
    fixture.write_text("datasets: []\ntables: []\n")
    monkeypatch.setenv("MCP_BIGQUERY_FAKE_FIXTURE", str(fixture))

    server = build_server()
    tool_names = {t.name for t in server.list_tools_sync()}
    assert tool_names == {
        "list_datasets",
        "list_tables",
        "describe_table",
        "sample_table",
        "search_schema",
        "estimate_cost",
        "run_query",
    }
```

> **Implementation note for the engineer:** the `mcp` SDK API for listing registered tools may differ (e.g., `await server.list_tools()` rather than `list_tools_sync()`). Adapt the test to whatever the installed `mcp` version exposes. The assertion that matters is "exactly these 7 tool names are registered."

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_tools/test_server.py -v`
Expected: ImportError on `mcp_bigquery_evals.server`.

- [ ] **Step 3: Implement `server.py`**

`src/mcp_bigquery_evals/server.py`:
```python
from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_bigquery_evals.bq.fake import FakeBigQueryClient
from mcp_bigquery_evals.bq.protocol import BigQueryClient
from mcp_bigquery_evals.tools.describe_table import describe_table
from mcp_bigquery_evals.tools.estimate_cost import estimate_cost
from mcp_bigquery_evals.tools.list_datasets import list_datasets
from mcp_bigquery_evals.tools.list_tables import list_tables
from mcp_bigquery_evals.tools.run_query import run_query
from mcp_bigquery_evals.tools.sample_table import sample_table
from mcp_bigquery_evals.tools.search_schema import search_schema_tool


def build_client() -> BigQueryClient:
    """Wire up the BigQueryClient based on env vars.

    - MCP_BIGQUERY_FAKE_FIXTURE set → FakeBigQueryClient.from_yaml(...)
    - otherwise → RealBigQueryClient (Plan B; raises NotImplementedError for now)
    """
    fake_path = os.environ.get("MCP_BIGQUERY_FAKE_FIXTURE")
    if fake_path:
        return FakeBigQueryClient.from_yaml(Path(fake_path))
    raise NotImplementedError(
        "RealBigQueryClient not yet implemented (Plan B). "
        "Set MCP_BIGQUERY_FAKE_FIXTURE to use the fake client."
    )


def build_server() -> FastMCP:
    """Construct the MCP server with all 7 tools registered."""
    mcp = FastMCP("mcp-bigquery-evals")
    client = build_client()

    @mcp.tool(name="list_datasets")
    def _ld() -> list[dict]:
        """List all datasets in the configured BigQuery project."""
        return list_datasets(client)

    @mcp.tool(name="list_tables")
    def _lt(dataset_id: str) -> list[dict]:
        """List all tables in a given dataset."""
        return list_tables(client, dataset_id)

    @mcp.tool(name="describe_table")
    def _dt(table_id: str) -> dict:
        """Schema and metadata for a single table."""
        return describe_table(client, table_id)

    @mcp.tool(name="sample_table")
    def _st(table_id: str, n: int = 5) -> list[dict] | dict:
        """Return up to n sample rows from a table."""
        return sample_table(client, table_id, n)

    @mcp.tool(name="search_schema")
    def _ss(term: str) -> list[dict]:
        """Fuzzy-match a term against all column names; return top hits."""
        return search_schema_tool(client, term)

    @mcp.tool(name="estimate_cost")
    def _ec(sql: str) -> dict:
        """Dry-run a query; return bytes_scanned and estimated_usd."""
        return estimate_cost(client, sql)

    @mcp.tool(name="run_query")
    def _rq(sql: str, max_bytes_scanned: int = 100 * 1024 * 1024) -> dict:
        """Execute a SELECT after dry-run cap check; returns rows or structured error."""
        return run_query(client, sql, max_bytes_scanned=max_bytes_scanned)

    return mcp
```

> **Engineer note:** the `FastMCP` decorator pattern shown above may have a slightly different surface in your installed `mcp` version. The principle is fixed (one decorator per tool, MCP `name` argument matches the spec exactly so what Claude Desktop sees is `list_datasets`, `run_query`, etc.). Adapt syntax if the SDK has evolved.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_tools/test_server.py -v`
Expected: 1 passed (after adjusting the test if the `mcp` SDK surface differs).

- [ ] **Step 5: Commit**

```bash
git add src/mcp_bigquery_evals/server.py tests/unit/test_tools/test_server.py
git commit -m "server: register all 7 MCP tools; wire BigQueryClient via env"
```

---

### Task 18: CLI - argparse with `serve` subcommand

**Files:**
- Create: `src/mcp_bigquery_evals/cli.py`
- Create: `src/mcp_bigquery_evals/__main__.py`

- [ ] **Step 1: Write `cli.py`**

`src/mcp_bigquery_evals/cli.py`:
```python
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mcp-bigquery-evals")
    sub = parser.add_subparsers(dest="cmd")

    serve = sub.add_parser("serve", help="Run the MCP server over stdio.")
    serve.set_defaults(func=_cmd_serve)

    # 'evals run' subcommand is added in Plan B; stub it here so the help text is honest.
    evals = sub.add_parser("evals", help="(Plan B) Run the NL2SQL eval harness.")
    evals.set_defaults(func=_cmd_evals_stub)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        # Default action when no subcommand: serve.
        return _cmd_serve(args)
    return args.func(args)


def _cmd_serve(_args: argparse.Namespace) -> int:
    from mcp_bigquery_evals.server import build_server

    server = build_server()
    server.run()  # FastMCP runs over stdio by default
    return 0


def _cmd_evals_stub(_args: argparse.Namespace) -> int:
    print("evals subcommand not yet implemented (Plan B).", file=sys.stderr)
    return 1
```

- [ ] **Step 2: Write `__main__.py`**

`src/mcp_bigquery_evals/__main__.py`:
```python
from mcp_bigquery_evals.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Verify the CLI is reachable**

Run:
```bash
python -m mcp_bigquery_evals --help
```
Expected: argparse help output listing `serve` and `evals` subcommands.

- [ ] **Step 4: Commit**

```bash
git add src/mcp_bigquery_evals/cli.py src/mcp_bigquery_evals/__main__.py
git commit -m "cli: add argparse entrypoint with 'serve' subcommand (evals stubbed for Plan B)"
```

---

### Task 19: End-to-end smoke - launch server, list tools

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_server_smoke.py`

- [ ] **Step 1: Write the smoke test**

`tests/integration/__init__.py`:
```python
```

`tests/integration/test_server_smoke.py`:
```python
"""End-to-end smoke: build the server and exercise each tool against the fake fixture.

This bypasses the stdio transport and calls handlers directly via build_server().
A separate stdio-protocol test is deferred to Plan B's CI integration.
"""
from pathlib import Path

import pytest

from mcp_bigquery_evals.server import build_server

FIXTURE = Path(__file__).parent.parent / "fixtures" / "fake_warehouse.yaml"


@pytest.fixture(autouse=True)
def use_fake_fixture(monkeypatch):
    monkeypatch.setenv("MCP_BIGQUERY_FAKE_FIXTURE", str(FIXTURE))


def test_smoke_seven_tools_registered_and_callable():
    server = build_server()
    # Exact API depends on the installed `mcp` version. The acceptance criterion is:
    # all 7 tool names are registered AND each can be invoked with valid args
    # against the fake fixture without raising.
    tool_names = {t.name for t in server.list_tools_sync()}
    assert len(tool_names) == 7
```

> **Engineer note:** if the installed `mcp` SDK surfaces differently, expand this test to actually invoke each tool through the SDK's invocation API (e.g. `await server.call_tool("list_datasets", {})`) and assert each returns a non-error response. The minimum bar: every tool callable end-to-end against the fake.

- [ ] **Step 2: Run smoke test**

Run: `pytest tests/integration/test_server_smoke.py -v`
Expected: 1 passed.

- [ ] **Step 3: Run the FULL test suite**

Run: `pytest -v`
Expected: all tests pass; total ≈ 35–40 tests.

- [ ] **Step 4: Run lint + type-check**

Run:
```bash
ruff check src tests
mypy src
```
Expected: both clean.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/
git commit -m "tests: integration smoke - server builds and all 7 tools are registered"
```

- [ ] **Step 6: Tag the milestone**

```bash
git tag -a plan-a-complete -m "Plan A complete: working stdio MCP server tested against fake"
```

---

## Plan A Acceptance

After Task 19, the following are true:

1. `python -m mcp_bigquery_evals serve` launches a stdio MCP server
2. With `MCP_BIGQUERY_FAKE_FIXTURE=tests/fixtures/fake_warehouse.yaml` set, an MCP client (Claude Desktop, Inspector) sees and can invoke all 7 tools
3. Cost cap behavior works (try `run_query` with `max_bytes_scanned=1` → returns structured error)
4. `pytest -v` is green
5. `ruff check` and `mypy --strict` are clean
6. Repo is tagged `plan-a-complete`

## What's NOT in Plan A (deferred to Plan B)

- `RealBigQueryClient` - wraps `google-cloud-bigquery`; needs your GCP project
- Eval harness - `evals/golden.yaml`, runner, JSON report writer, `evals run` subcommand wired up
- CI workflows (`ci.yml`, `evals.yml`)
- README beyond the placeholder
- `claude_desktop_setup.md`, `architecture.md`, `how_evals_work.md` docs
- PyPI publish (version bump, build, twine upload)
- `awesome-mcp-servers` PR
- Blog posts

Plan B is written after Plan A is complete and you've had time to use the server locally - the friction you hit during local use will sharpen what Plan B prioritizes.
