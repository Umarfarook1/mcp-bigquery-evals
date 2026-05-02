"""Domain exceptions for BigQueryClient implementations.

Real-world BigQuery API errors get translated into BigQueryError instances
so the tool layer has a stable error contract regardless of which BQ client
implementation is in use.
"""

from __future__ import annotations


class BigQueryError(Exception):
    """A structured error from a BigQueryClient method.

    Attributes:
        code: One of "invalid_sql", "table_not_found", "permission_denied",
              "rate_limited", "unknown". Stable identifiers safe for an LLM agent
              to switch on.
        message: Human-readable description (safe to surface to the agent).
        details: Optional dict of extra fields.
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, object]:
        return {"error": self.code, "message": self.message, **self.details}


def translate_bq_exception(exc: BaseException) -> BigQueryError:
    """Map a google.api_core.exceptions.* exception to a BigQueryError.

    Falls back to BigQueryError(code="unknown") for anything we don't recognize.
    """
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
    if isinstance(exc, gerr.PermissionDenied):
        return BigQueryError(
            code="permission_denied",
            message=_first_error_message(exc) or str(exc),
        )
    if isinstance(exc, (gerr.TooManyRequests, gerr.ResourceExhausted)):
        return BigQueryError(
            code="rate_limited",
            message=_first_error_message(exc) or str(exc),
        )
    return BigQueryError(code="unknown", message=str(exc))


def _first_error_message(exc: BaseException) -> str | None:
    """BadRequest exceptions carry a list of structured errors; return the first message."""
    errors = getattr(exc, "errors", None)
    if errors and isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            msg = first.get("message")
            if isinstance(msg, str):
                return msg
    return None
