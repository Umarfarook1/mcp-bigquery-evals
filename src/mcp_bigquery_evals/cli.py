from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mcp-bigquery-evals")
    sub = parser.add_subparsers(dest="cmd")

    serve = sub.add_parser("serve", help="Run the MCP server over stdio.")
    serve.set_defaults(func=_cmd_serve)

    evals = sub.add_parser("evals", help="Run the NL2SQL eval harness.")
    evals.set_defaults(func=_cmd_evals_help)
    evals_sub = evals.add_subparsers(dest="evals_cmd")

    run = evals_sub.add_parser("run", help="Execute the eval suite against a model.")
    run.add_argument("--model", default="claude-haiku-4-5", help="Anthropic model id.")
    run.add_argument(
        "--golden",
        type=Path,
        default=Path("src/mcp_bigquery_evals/evals/golden.yaml"),
        help="Path to the golden NL-to-SQL pairs file.",
    )
    run.add_argument("--limit", type=int, default=None, help="Run only N pairs.")
    run.add_argument(
        "--report",
        type=Path,
        default=Path("evals/last_report.json"),
        help="Where to write the JSON report.",
    )
    run.set_defaults(func=_cmd_evals_run)

    args = parser.parse_args(argv)
    func: Callable[[argparse.Namespace], int] = getattr(args, "func", _cmd_serve)
    return func(args)


def _cmd_serve(_args: argparse.Namespace) -> int:
    from mcp_bigquery_evals.server import build_server

    server = build_server()
    server.run()
    return 0


def _cmd_evals_help(_args: argparse.Namespace) -> int:
    print(
        "usage: mcp-bigquery-evals evals run"
        " [--model X] [--golden PATH] [--limit N] [--report PATH]",
        file=sys.stderr,
    )
    print("hint: try `mcp-bigquery-evals evals run --help`", file=sys.stderr)
    return 1


def _cmd_evals_run(args: argparse.Namespace) -> int:
    # Load .env if present (best-effort; missing is fine if env vars are set externally)
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    from mcp_bigquery_evals.evals.anthropic_model import make_anthropic_model
    from mcp_bigquery_evals.evals.runner import run_evals
    from mcp_bigquery_evals.server import build_client

    try:
        client = build_client()
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    try:
        model_fn = make_anthropic_model(model_id=args.model)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print(
        f"Running evals: model={args.model} golden={args.golden} limit={args.limit}",
        file=sys.stderr,
    )

    try:
        report = run_evals(
            client=client,
            golden_path=args.golden,
            model_fn=model_fn,
            limit=args.limit,
        )
    except FileNotFoundError as e:
        print(f"error: golden file not found: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"error: invalid golden file: {e}", file=sys.stderr)
        return 2

    # Print summary to stderr
    print(
        f"\nResults: accuracy={report.accuracy:.1%} ({report.passes}/{report.total}) "
        f"gold_errors={report.gold_errors} "
        f"avg_bytes={report.avg_bytes_scanned} avg_ms={report.avg_latency_ms} "
        f"cost_usd={report.total_cost_usd:.4f}",
        file=sys.stderr,
    )

    # Write JSON report + shields.io badge
    from mcp_bigquery_evals.evals.report import write_badge, write_report

    write_report(report, args.report, model_id=args.model)
    print(f"Wrote report to {args.report.resolve()}", file=sys.stderr)

    badge_path = args.report.parent / "badge.json"
    write_badge(report, badge_path, model_id=args.model)
    print(f"Wrote badge to {badge_path.resolve()}", file=sys.stderr)

    # Exit code: 0 on any success, 1 if all pairs failed (signal a problem), 2 already handled above
    return 0 if report.total == 0 or report.passes > 0 else 1
