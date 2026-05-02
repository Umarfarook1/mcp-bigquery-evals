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
) -> dict[str, object] | None:
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
