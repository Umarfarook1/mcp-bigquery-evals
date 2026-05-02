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

    def list_datasets(self) -> list[Dataset]: ...

    def list_tables(self, dataset_id: str) -> list[Table]: ...

    def get_table(self, table_id: str) -> TableSchema: ...

    def sample_rows(self, table_id: str, n: int) -> list[dict[str, object]]: ...

    def dry_run(self, sql: str) -> DryRunResult: ...

    def execute(self, sql: str, dry_run_result: DryRunResult | None = None) -> QueryResult:
        """Execute SQL. If dry_run_result is provided, use it for cost fields without
        a second dry-run call. If None, the implementation may dry-run internally
        (or compute cost from execution metadata, e.g. job.total_bytes_processed).
        """
        ...

    def close(self) -> None:
        """Release any held resources (network connections, sqlite handles, etc.).

        Implementations must make this idempotent - calling close() twice is a no-op.
        """
        ...
