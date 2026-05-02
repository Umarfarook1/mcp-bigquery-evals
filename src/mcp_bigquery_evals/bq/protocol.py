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

    def sample_rows(self, table_id: str, n: int) -> list[dict[str, object]]:
        ...

    def dry_run(self, sql: str) -> DryRunResult:
        ...

    def execute(self, sql: str) -> QueryResult:
        ...
