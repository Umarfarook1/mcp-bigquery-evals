from typing import TypedDict

from rapidfuzz import fuzz

from mcp_bigquery_evals.bq.protocol import BigQueryClient


class SchemaHit(TypedDict):
    table: str
    column: str
    similarity: int


def search_schema(
    client: BigQueryClient,
    term: str,
    limit: int = 10,
) -> list[SchemaHit]:
    """Fuzzy-match `term` against all column names across all tables.

    Returns up to `limit` hits as [{table, column, similarity}], sorted desc.
    Similarity is rapidfuzz's WRatio (0-100).
    """
    hits: list[SchemaHit] = []
    for dataset in client.list_datasets():
        for table in client.list_tables(dataset.id):
            schema = client.get_table(table.id)
            for col in schema.columns:
                score = fuzz.WRatio(term, col.name)
                hits.append(
                    SchemaHit(
                        table=table.id, column=col.name, similarity=int(score)
                    )
                )
    hits.sort(key=lambda h: h["similarity"], reverse=True)
    return hits[:limit]
