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
    """Returned by describe_table — table metadata + column list."""

    table: Table
    columns: list[Column]


@dataclass(frozen=True, slots=True)
class DryRunResult:
    bytes_scanned: int
    estimated_usd: float


@dataclass(frozen=True, slots=True)
class QueryResult:
    rows: list[dict[str, object]]
    bytes_scanned: int
    cost_usd: float
    ms: int
