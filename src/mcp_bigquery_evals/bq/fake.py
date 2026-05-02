from __future__ import annotations

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

    def sample_rows(self, table_id: str, n: int) -> list[dict[str, object]]:
        raise NotImplementedError  # Task 6

    def dry_run(self, sql: str) -> DryRunResult:
        raise NotImplementedError  # Task 7

    def execute(self, sql: str) -> QueryResult:
        raise NotImplementedError  # Task 7


def _estimate_size_bytes(columns: list[Column], rows: list[dict[str, Any]]) -> int:
    """Crude size estimate: 32 bytes per cell, for unit-test purposes only."""
    return len(columns) * len(rows) * 32
