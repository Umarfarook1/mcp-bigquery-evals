"""Eval runner orchestrator.

Loads golden pairs, calls a model callback for each, executes gold + predicted SQL,
compares results, accumulates per-pair + aggregate metrics.

The model callback signature is `(prompt: dict[str, str], gold_sql: str) -> str`.
The gold_sql is passed only so test mocks can return it; production callbacks
should ignore it and call the actual model with the prompt.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from mcp_bigquery_evals.bq.errors import BigQueryError
from mcp_bigquery_evals.bq.protocol import BigQueryClient
from mcp_bigquery_evals.bq.types import DryRunResult, QueryResult
from mcp_bigquery_evals.evals.compare import results_equal
from mcp_bigquery_evals.evals.prompt import build_prompt

ModelFn = Callable[[dict[str, str], str], str]


@dataclass
class PairResult:
    id: int
    nl: str
    dataset: str
    gold_sql: str
    predicted_sql: str | None
    passed: bool
    error: str | None
    bytes_scanned: int
    cost_usd: float
    latency_ms: int


@dataclass
class EvalReport:
    accuracy: float
    total: int
    passes: int
    avg_bytes_scanned: int
    avg_latency_ms: int
    total_cost_usd: float
    per_pair: list[PairResult] = field(default_factory=list)


def run_evals(
    client: BigQueryClient,
    golden_path: Path,
    model_fn: ModelFn,
    limit: int | None = None,
) -> EvalReport:
    pairs = _load_pairs(golden_path)
    if limit is not None:
        pairs = pairs[:limit]

    per_pair: list[PairResult] = []

    for pair in pairs:
        per_pair.append(_evaluate_one(client, pair, model_fn))

    passes = sum(1 for r in per_pair if r.passed)
    total = len(per_pair)
    return EvalReport(
        accuracy=passes / total if total else 0.0,
        total=total,
        passes=passes,
        avg_bytes_scanned=int(sum(r.bytes_scanned for r in per_pair) / total) if total else 0,
        avg_latency_ms=int(sum(r.latency_ms for r in per_pair) / total) if total else 0,
        total_cost_usd=sum(r.cost_usd for r in per_pair),
        per_pair=per_pair,
    )


def report_to_dict(report: EvalReport) -> dict[str, Any]:
    return asdict(report)


# ---- Internals ----


def _load_pairs(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(data.get("golden_pairs", []))


def _evaluate_one(
    client: BigQueryClient,
    pair: dict[str, Any],
    model_fn: ModelFn,
) -> PairResult:
    pair_id = int(pair["id"])
    dataset = str(pair["dataset"])
    nl = str(pair["nl"])
    gold_sql = str(pair["gold_sql"]).strip()

    predicted_sql: str | None = None
    error: str | None = None
    passed = False
    bytes_scanned = 0
    cost_usd = 0.0

    start = time.perf_counter()

    try:
        prompt = build_prompt(client, dataset_id=dataset, nl=nl)
        predicted_sql = model_fn(prompt, gold_sql).strip()

        # Execute both queries against the BigQueryClient.
        # Errors at this stage = pair fails (invalid predicted SQL counts as wrong, not as a crash).
        try:
            gold_result = _execute(client, gold_sql)
        except (BigQueryError, ValueError) as exec_err:
            error = f"gold execution failed: {exec_err}"
            return _finalize_pair(
                pair_id,
                nl,
                dataset,
                gold_sql,
                predicted_sql,
                passed=False,
                error=error,
                bytes_scanned=0,
                cost_usd=0.0,
                latency_ms=int((time.perf_counter() - start) * 1000),
            )

        try:
            predicted_result = _execute(client, predicted_sql)
        except (BigQueryError, ValueError) as exec_err:
            error = f"predicted execution failed: {exec_err}"
            return _finalize_pair(
                pair_id,
                nl,
                dataset,
                gold_sql,
                predicted_sql,
                passed=False,
                error=error,
                bytes_scanned=0,
                cost_usd=0.0,
                latency_ms=int((time.perf_counter() - start) * 1000),
            )

        passed = results_equal(gold_result.rows, predicted_result.rows)
        bytes_scanned = predicted_result.bytes_scanned
        cost_usd = predicted_result.cost_usd
    except Exception as e:
        error = f"runner_error: {e}"
        passed = False

    latency_ms = int((time.perf_counter() - start) * 1000)

    return _finalize_pair(
        pair_id,
        nl,
        dataset,
        gold_sql,
        predicted_sql,
        passed=passed,
        error=error,
        bytes_scanned=bytes_scanned,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
    )


def _execute(client: BigQueryClient, sql: str) -> QueryResult:
    """Dry-run then execute, threading the dry-run result through to avoid double-dry-run."""
    dr: DryRunResult = client.dry_run(sql)
    return client.execute(sql, dry_run_result=dr)


def _finalize_pair(
    pair_id: int,
    nl: str,
    dataset: str,
    gold_sql: str,
    predicted_sql: str | None,
    passed: bool,
    error: str | None,
    bytes_scanned: int,
    cost_usd: float,
    latency_ms: int,
) -> PairResult:
    return PairResult(
        id=pair_id,
        nl=nl,
        dataset=dataset,
        gold_sql=gold_sql,
        predicted_sql=predicted_sql,
        passed=passed,
        error=error,
        bytes_scanned=bytes_scanned,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
    )
