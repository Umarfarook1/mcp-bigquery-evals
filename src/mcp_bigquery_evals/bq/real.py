"""RealBigQueryClient — wraps google-cloud-bigquery.

Auth precedence:
1. GOOGLE_APPLICATION_CREDENTIALS env var → service-account JSON
2. Application Default Credentials (gcloud auth application-default login)

The wrapper exists to:
- Translate google.cloud.bigquery types into our domain types (bq/types.py)
- Translate google.api_core.exceptions into structured returns (Task 6)
- Keep the BigQueryClient Protocol surface stable across fake and real impls.
"""

from __future__ import annotations

from typing import Any

from google.cloud import bigquery

from mcp_bigquery_evals.bq.types import (
    Dataset,
    DryRunResult,
    QueryResult,
    Table,
    TableSchema,
)


class RealBigQueryClient:
    """Production BigQueryClient backed by google-cloud-bigquery."""

    def __init__(self, project: str, _client: Any | None = None) -> None:
        # _client kwarg is for testing; production callers leave it None.
        self._project = project
        self._client: Any = _client if _client is not None else bigquery.Client(project=project)

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
        try:
            items = list(self._client.list_tables(dataset_id))
        except Exception:
            # Treat missing/inaccessible datasets as empty (T6 will refine error contract)
            return []
        result: list[Table] = []
        for t_item in items:
            t = self._client.get_table(f"{dataset_id}.{t_item.table_id}")
            result.append(
                Table(
                    id=f"{dataset_id}.{t_item.table_id}",
                    row_count=int(getattr(t, "num_rows", 0) or 0),
                    size_bytes=int(getattr(t, "num_bytes", 0) or 0),
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
            self._client = None
