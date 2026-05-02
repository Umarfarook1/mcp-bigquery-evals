"""JSON report + shields.io badge writer for eval runs."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp_bigquery_evals.evals.runner import EvalReport


def write_report(report: EvalReport, out: Path, model_id: str) -> None:
    """Write the full eval report as JSON. Includes model id and UTC timestamp."""
    out.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "model": model_id,
        "generated_at": datetime.now(UTC).isoformat(),
        **asdict(report),
    }
    out.write_text(json.dumps(payload, indent=2, default=str))


def write_badge(report: EvalReport, out: Path, model_id: str) -> None:
    """Write a shields.io endpoint JSON file (https://shields.io/badges/endpoint-badge).

    The README references this file at a known URL; shields.io fetches it
    and renders a colored badge. CI updates this file on every main merge.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    pct = int(round(report.accuracy * 100))
    payload = {
        "schemaVersion": 1,
        "label": f"{model_id} accuracy",
        "message": f"{pct}%",
        "color": _color_for_accuracy(report.accuracy),
    }
    out.write_text(json.dumps(payload))


def _color_for_accuracy(acc: float) -> str:
    """Color thresholds for the badge."""
    if acc < 0.40:
        return "red"
    if acc < 0.60:
        return "orange"
    if acc < 0.75:
        return "yellow"
    if acc < 0.90:
        return "green"
    return "brightgreen"
