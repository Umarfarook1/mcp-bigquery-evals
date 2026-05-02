"""Domain exceptions for BigQueryClient implementations.

Real-world BigQuery API errors get translated into BigQueryError instances
so the tool layer has a stable error contract regardless of which BQ client
implementation is in use.
"""

from __future__ import annotations

from typing import Literal

ErrorCode = Literal[
    "invalid_sql",
    "table_not_found",
    "permission_denied",
    "unauthenticated",
    "rate_limited",
    "query_timeout",
    "unknown",
]


class BigQueryError(Exception):
    """A structured error from a BigQueryClient method.

    Attributes:
        code: One of "invalid_sql", "table_not_found", "permission_denied",
              "unauthenticated", "rate_limited", "query_timeout", "unknown".
              Stable identifiers safe for an LLM agent to switch on.
        message: Human-readable description (safe to surface to the agent).
        details: Optional dict of extra fields.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code: ErrorCode = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"error": self.code, "message": self.message}
        if self.details:
            result["details"] = self.details
        return result


def translate_bq_exception(exc: BaseException) -> BigQueryError:
    """Map a google.api_core.exceptions.* exception to a BigQueryError.

    Falls back to BigQueryError(code="unknown") for anything we don't recognize.
    """
    if isinstance(exc, BigQueryError):
        return exc  # already translated; pass through unchanged

    try:
        from google.api_core import exceptions as gerr
    except ImportError:
        return BigQueryError(code="unknown", message=str(exc))

    if isinstance(exc, gerr.BadRequest):
        return BigQueryError(
            code="invalid_sql",
            message=_first_error_message(exc) or str(exc),
        )
    if isinstance(exc, gerr.NotFound):
        return BigQueryError(
            code="table_not_found",
            message=_first_error_message(exc) or str(exc),
        )
    if isinstance(exc, gerr.Unauthenticated):
        return BigQueryError(
            code="unauthenticated",
            message=_first_error_message(exc) or str(exc),
        )
    if isinstance(exc, (gerr.PermissionDenied, gerr.Forbidden)):
        return BigQueryError(
            code="permission_denied",
            message=_first_error_message(exc) or str(exc),
        )
    if isinstance(exc, gerr.DeadlineExceeded):
        return BigQueryError(
            code="query_timeout",
            message=_first_error_message(exc) or str(exc),
        )
    # TooManyRequests covers ResourceExhausted (subclass) + plain quota errors.
    if isinstance(exc, gerr.TooManyRequests):
        return BigQueryError(
            code="rate_limited",
            message=_first_error_message(exc) or str(exc),
        )
    return BigQueryError(code="unknown", message=str(exc))


def _first_error_message(exc: BaseException) -> str | None:
    """Some BQ exceptions carry a list of structured errors; return the first message if present."""
    errors = getattr(exc, "errors", None)
    if not errors or not isinstance(errors, list):
        return None
    first = errors[0]
    if isinstance(first, dict):
        msg = first.get("message")
        if isinstance(msg, str):
            return msg
    return None
