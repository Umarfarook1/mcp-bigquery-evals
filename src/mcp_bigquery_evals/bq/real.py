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

from google.api_core.exceptions import (
    GoogleAPICallError,
    NotFound,
    PermissionDenied,
    Unauthenticated,
)
from google.cloud import bigquery

from mcp_bigquery_evals.bq.errors import translate_bq_exception
from mcp_bigquery_evals.bq.types import (
    Column,
    Dataset,
    DryRunResult,
    QueryResult,
    Table,
    TableSchema,
)

# BigQuery on-demand pricing: $5 per TB scanned.
_USD_PER_BYTE = 5.0 / (1024**4)


class RealBigQueryClient:
    """Production BigQueryClient backed by google-cloud-bigquery."""

    def __init__(self, project: str, _client: Any | None = None) -> None:
        # _client kwarg is for testing; production callers leave it None.
        self._project = project
        self._client: Any = _client if _client is not None else bigquery.Client(project=project)

    def _assert_open(self) -> None:
        if self._client is None:
            raise RuntimeError("RealBigQueryClient has been closed; create a new instance.")

    # ---- BigQueryClient Protocol ----

    def list_datasets(self) -> list[Dataset]:
        self._assert_open()
        try:
            items = list(self._client.list_datasets())
        except (NotFound, PermissionDenied, Unauthenticated):
            return []
        # Other exceptions (ServiceUnavailable, network errors) propagate

        result: list[Dataset] = []
        for ds_item in items:
            # TODO(perf): N+1 — each get_dataset is a serial round trip
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
        self._assert_open()
        try:
            items = list(self._client.list_tables(dataset_id))
        except (NotFound, PermissionDenied, Unauthenticated):
            # Treat missing/inaccessible datasets as empty — schema-traversal callers
            # can't distinguish "missing" from "empty" anyway; [] is least-surprising.
            return []
        # Other exceptions (ServiceUnavailable, network errors) propagate to caller
        result: list[Table] = []
        for t_item in items:
            # TODO(perf): N+1 — each get_table is a serial round trip; consider concurrent fetch.
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
        self._assert_open()
        try:
            t = self._client.get_table(table_id)
        except GoogleAPICallError as exc:
            raise translate_bq_exception(exc) from exc
        columns = [
            Column(
                name=field.name,
                type=field.field_type,
                description=getattr(field, "description", None),
            )
            for field in (t.schema or [])
        ]
        return TableSchema(
            table=Table(
                id=table_id,
                row_count=int(getattr(t, "num_rows", 0) or 0),
                size_bytes=int(getattr(t, "num_bytes", 0) or 0),
            ),
            columns=columns,
        )

    def sample_rows(self, table_id: str, n: int) -> list[dict[str, object]]:
        self._assert_open()
        n = max(0, n)
        try:
            rows_iter = self._client.list_rows(table_id, max_results=n)
            return [dict(row.items()) for row in rows_iter]
        except GoogleAPICallError as exc:
            raise translate_bq_exception(exc) from exc

    def dry_run(self, sql: str) -> DryRunResult:
        self._assert_open()
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        try:
            job = self._client.query(sql, job_config=job_config)
        except GoogleAPICallError as exc:
            raise translate_bq_exception(exc) from exc
        bytes_scanned = int(job.total_bytes_processed or 0)
        return DryRunResult(
            bytes_scanned=bytes_scanned,
            estimated_usd=bytes_scanned * _USD_PER_BYTE,
        )

    def execute(self, sql: str, dry_run_result: DryRunResult | None = None) -> QueryResult:
        self._assert_open()
        import time as _time

        start = _time.perf_counter()
        try:
            job = self._client.query(sql)
            rows = [dict(row.items()) for row in job.result()]
        except GoogleAPICallError as exc:
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

    def close(self) -> None:
        client = getattr(self, "_client", None)
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
            self._client = None

    def __del__(self) -> None:
        # Best-effort cleanup; safe even if __init__ raised before _client was set.
        client = getattr(self, "_client", None)
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
