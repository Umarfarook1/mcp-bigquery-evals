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

    def sample_rows(self, table_id: str, n: int) -> list[dict[str, object]]:
        if table_id not in self._rows:
            raise KeyError(table_id)
        n = max(0, n)
        return list(self._rows[table_id][:n])

    def dry_run(self, sql: str) -> DryRunResult:
        # Estimate: sum of size_bytes for every table referenced in the SQL.
        bytes_scanned = sum(
            self._tables[tid].table.size_bytes
            for tid in self._tables
            if _table_referenced(sql, tid)
        )
        return DryRunResult(
            bytes_scanned=bytes_scanned,
            estimated_usd=bytes_scanned * _USD_PER_BYTE,
        )

    def execute(self, sql: str) -> QueryResult:
        translated = self._bq_to_sqlite(sql)
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

    def _bq_to_sqlite(self, sql: str) -> str:
        """Translate the small subset of BQ syntax we need for fixture-backed tests:
        - `dataset.table` backticked references → dataset__table
        - bare dataset.table references (matching a known table) → dataset__table

        Bare-ref translation only matches IDs in self._tables to avoid touching
        alias.column references like `u.country`.
        """
        # 1. Backticked: `analytics.users` → analytics__users
        sql = re.sub(
            r"`([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)`",
            r"\1__\2",
            sql,
        )
        # 2. Bare refs: only translate IDs we know about, with word-boundary anchors
        for tid in self._tables:
            pattern = rf"(?<![A-Za-z0-9_`]){re.escape(tid)}(?![A-Za-z0-9_])"
            sql = re.sub(pattern, _sqlite_name(tid), sql)
        return sql

    def close(self) -> None:
        self._conn.close()

    def __del__(self) -> None:
        # Best-effort cleanup; safe even if __init__ raised before _conn was set.
        conn = getattr(self, "_conn", None)
        if conn is not None:
            conn.close()


# ---- Helpers ----


def _estimate_size_bytes(columns: list[Column], rows: list[dict[str, Any]]) -> int:
    """Crude estimate: 32 bytes per cell."""
    return len(columns) * len(rows) * 32


def _sqlite_name(table_id: str) -> str:
    return table_id.replace(".", "__")


def _table_referenced(sql: str, table_id: str) -> bool:
    """Loose check: does this BQ table_id appear as a token (not as a substring) in SQL?

    Uses negative-lookbehind/lookahead to enforce word-boundary semantics so that
    `analytics.users` does NOT match inside `analytics.users_extended`. Backtick is
    not in [A-Za-z0-9_] so it acts as a boundary naturally.
    """
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(table_id)}(?![A-Za-z0-9_])"
    return re.search(pattern, sql) is not None
