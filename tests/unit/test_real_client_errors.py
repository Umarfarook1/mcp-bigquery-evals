from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mcp_bigquery_evals.bq.errors import BigQueryError, translate_bq_exception
from mcp_bigquery_evals.bq.real import RealBigQueryClient


def test_translate_bad_request_returns_invalid_sql() -> None:
    from google.api_core import exceptions as gerr

    exc = gerr.BadRequest("Syntax error: Expected end of input but got keyword FROM")
    err = translate_bq_exception(exc)
    assert err.code == "invalid_sql"
    assert "Syntax error" in err.message


def test_translate_not_found_returns_table_not_found() -> None:
    from google.api_core import exceptions as gerr

    exc = gerr.NotFound("Not found: Table myproj:analytics.foo")
    err = translate_bq_exception(exc)
    assert err.code == "table_not_found"


def test_translate_permission_denied() -> None:
    from google.api_core import exceptions as gerr

    exc = gerr.PermissionDenied("Access denied")
    err = translate_bq_exception(exc)
    assert err.code == "permission_denied"


def test_translate_rate_limited_too_many() -> None:
    from google.api_core import exceptions as gerr

    exc = gerr.TooManyRequests("Quota exceeded")
    err = translate_bq_exception(exc)
    assert err.code == "rate_limited"


def test_translate_rate_limited_resource_exhausted() -> None:
    from google.api_core import exceptions as gerr

    exc = gerr.ResourceExhausted("Resource exhausted")
    err = translate_bq_exception(exc)
    assert err.code == "rate_limited"


def test_translate_unknown_falls_back() -> None:
    err = translate_bq_exception(RuntimeError("something weird"))
    assert err.code == "unknown"
    assert "something weird" in err.message


def test_to_dict_shape() -> None:
    err = BigQueryError(
        code="invalid_sql",
        message="bad",
        details={"sql": "SELECT * FRM"},
    )
    d = err.to_dict()
    assert d["error"] == "invalid_sql"
    assert d["message"] == "bad"
    assert d["sql"] == "SELECT * FRM"


def test_to_dict_no_details() -> None:
    err = BigQueryError(code="x", message="y")
    d = err.to_dict()
    assert d == {"error": "x", "message": "y"}


def test_first_error_message_extracts_from_errors_list() -> None:
    from google.api_core import exceptions as gerr

    exc = gerr.BadRequest(
        "Outer message",
        errors=[{"message": "Inner specific error", "reason": "invalidQuery"}],
    )
    err = translate_bq_exception(exc)
    assert err.message == "Inner specific error"


# ---- Integration with RealBigQueryClient ----


def test_dry_run_translates_bad_request_to_bigquery_error() -> None:
    from google.api_core import exceptions as gerr

    mock_bq = MagicMock()
    mock_bq.query.side_effect = gerr.BadRequest("Syntax error near token 'FRM'")
    client = RealBigQueryClient(project="myproj", _client=mock_bq)

    with pytest.raises(BigQueryError) as exc_info:
        client.dry_run("SELECT * FRM users")
    assert exc_info.value.code == "invalid_sql"


def test_dry_run_translates_not_found() -> None:
    from google.api_core import exceptions as gerr

    mock_bq = MagicMock()
    mock_bq.query.side_effect = gerr.NotFound("Not found: Table x")
    client = RealBigQueryClient(project="myproj", _client=mock_bq)

    with pytest.raises(BigQueryError) as exc_info:
        client.dry_run("SELECT * FROM x")
    assert exc_info.value.code == "table_not_found"


def test_execute_translates_not_found_to_bigquery_error() -> None:
    from google.api_core import exceptions as gerr

    mock_bq = MagicMock()
    mock_bq.query.side_effect = gerr.NotFound("Not found: Table myproj:bogus")
    client = RealBigQueryClient(project="myproj", _client=mock_bq)

    with pytest.raises(BigQueryError) as exc_info:
        client.execute("SELECT 1 FROM `bogus`")
    assert exc_info.value.code == "table_not_found"


def test_execute_translates_permission_denied() -> None:
    from google.api_core import exceptions as gerr

    mock_bq = MagicMock()
    mock_bq.query.side_effect = gerr.PermissionDenied("Access denied")
    client = RealBigQueryClient(project="myproj", _client=mock_bq)

    with pytest.raises(BigQueryError) as exc_info:
        client.execute("SELECT 1")
    assert exc_info.value.code == "permission_denied"


def test_get_table_translates_not_found() -> None:
    from google.api_core import exceptions as gerr

    mock_bq = MagicMock()
    mock_bq.get_table.side_effect = gerr.NotFound("Not found")
    client = RealBigQueryClient(project="myproj", _client=mock_bq)

    with pytest.raises(BigQueryError) as exc_info:
        client.get_table("analytics.nonexistent")
    assert exc_info.value.code == "table_not_found"


def test_sample_rows_translates_not_found() -> None:
    from google.api_core import exceptions as gerr

    mock_bq = MagicMock()
    mock_bq.list_rows.side_effect = gerr.NotFound("Not found")
    client = RealBigQueryClient(project="myproj", _client=mock_bq)

    with pytest.raises(BigQueryError) as exc_info:
        client.sample_rows("analytics.nonexistent", n=5)
    assert exc_info.value.code == "table_not_found"


# ---- Tool-layer integration ----


def test_run_query_returns_dict_for_bigquery_error() -> None:
    """When dry_run raises BigQueryError, run_query should return its to_dict() shape."""
    from mcp_bigquery_evals.tools.run_query import run_query

    bad_client = MagicMock()
    bad_client.dry_run.side_effect = BigQueryError(code="invalid_sql", message="bad syntax")
    result = run_query(bad_client, "SELECT * FRM users")
    assert result["error"] == "invalid_sql"
    assert result["message"] == "bad syntax"


def test_run_query_returns_dict_for_bigquery_error_at_execute_step() -> None:
    """If dry_run succeeds but execute raises BigQueryError, run_query unwraps it."""
    from mcp_bigquery_evals.bq.types import DryRunResult
    from mcp_bigquery_evals.tools.run_query import run_query

    bad_client = MagicMock()
    bad_client.dry_run.return_value = DryRunResult(bytes_scanned=1000, estimated_usd=0.0001)
    bad_client.execute.side_effect = BigQueryError(code="rate_limited", message="quota")
    result = run_query(bad_client, "SELECT 1")
    assert result["error"] == "rate_limited"


def test_estimate_cost_returns_dict_for_bigquery_error() -> None:
    from mcp_bigquery_evals.tools.estimate_cost import estimate_cost

    bad_client = MagicMock()
    bad_client.dry_run.side_effect = BigQueryError(code="invalid_sql", message="bad")
    result = estimate_cost(bad_client, "INVALID")
    assert result["error"] == "invalid_sql"
