from mcp_bigquery_evals.bq.protocol import BigQueryClient
from mcp_bigquery_evals.guardrails import DEFAULT_MAX_BYTES_SCANNED, check_cost_cap


def run_query(
    client: BigQueryClient,
    sql: str,
    max_bytes_scanned: int = DEFAULT_MAX_BYTES_SCANNED,
) -> dict[str, object]:
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
