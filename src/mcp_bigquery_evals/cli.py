from __future__ import annotations

import argparse
import sys
from collections.abc import Callable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mcp-bigquery-evals")
    sub = parser.add_subparsers(dest="cmd")

    serve = sub.add_parser("serve", help="Run the MCP server over stdio.")
    serve.set_defaults(func=_cmd_serve)

    # 'evals run' subcommand is added in Plan B; stub it here so the help text is honest.
    evals = sub.add_parser("evals", help="(Plan B) Run the NL2SQL eval harness.")
    evals.set_defaults(func=_cmd_evals_stub)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        # Default action when no subcommand: serve.
        return _cmd_serve(args)
    func: Callable[[argparse.Namespace], int] = args.func  # set via set_defaults; not in stub
    return func(args)


def _cmd_serve(_args: argparse.Namespace) -> int:
    from mcp_bigquery_evals.server import build_server

    server = build_server()
    server.run()  # FastMCP runs over stdio by default
    return 0


def _cmd_evals_stub(_args: argparse.Namespace) -> int:
    print("evals subcommand not yet implemented (Plan B).", file=sys.stderr)
    return 1
