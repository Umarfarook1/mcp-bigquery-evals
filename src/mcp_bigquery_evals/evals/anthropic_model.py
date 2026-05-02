"""Anthropic Messages API adapter for the eval runner.

Wraps anthropic.Anthropic into the ModelFn signature expected by runner.run_evals.
The `anthropic` import is deferred to runtime so unit tests of the CLI parser
don't require the SDK to be importable.
"""

from __future__ import annotations

import os
import re
from typing import Any


def make_anthropic_model(model_id: str = "claude-haiku-4-5") -> Any:
    """Returns a function with signature (prompt, gold_sql) -> predicted_sql.

    Reads ANTHROPIC_API_KEY from env. Raises RuntimeError if missing.
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY env var is required for the eval runner")

    client = anthropic.Anthropic(api_key=api_key)

    def call(prompt: dict[str, str], _gold_sql: str) -> str:
        response = client.messages.create(
            model=model_id,
            max_tokens=2048,
            system=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}],
        )
        text = "".join(block.text for block in response.content if hasattr(block, "text"))
        sql = _strip_markdown_fences(text).strip()
        if not sql:
            raise RuntimeError(
                f"Model {model_id!r} returned no text content after stripping markdown fences"
            )
        return sql

    return call


def _strip_markdown_fences(text: str) -> str:
    """Remove ```sql ... ``` or ``` ... ``` fences if the model wrapped its output."""
    text = re.sub(r"^```(?:sql)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    return text
