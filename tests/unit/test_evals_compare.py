from decimal import Decimal

from mcp_bigquery_evals.evals.compare import results_equal


def test_equal_simple() -> None:
    a = [{"n": 5}]
    b = [{"n": 5}]
    assert results_equal(a, b)


def test_different_rows() -> None:
    a = [{"n": 5}]
    b = [{"n": 6}]
    assert not results_equal(a, b)


def test_order_independent() -> None:
    a = [{"id": 1}, {"id": 2}, {"id": 3}]
    b = [{"id": 3}, {"id": 1}, {"id": 2}]
    assert results_equal(a, b)


def test_multiset_semantics() -> None:
    a = [{"n": 1}, {"n": 1}, {"n": 2}]
    b = [{"n": 1}, {"n": 2}, {"n": 2}]
    assert not results_equal(a, b)


def test_float_tolerance() -> None:
    a = [{"x": 1.0000001}]
    b = [{"x": 1.0}]
    assert results_equal(a, b)


def test_float_outside_tolerance() -> None:
    a = [{"x": 1.5}]
    b = [{"x": 1.0}]
    assert not results_equal(a, b)


def test_null_equality() -> None:
    a = [{"x": None}, {"x": 1}]
    b = [{"x": 1}, {"x": None}]
    assert results_equal(a, b)


def test_null_vs_zero_not_equal() -> None:
    a = [{"x": None}]
    b = [{"x": 0}]
    assert not results_equal(a, b)


def test_column_subset_mismatch() -> None:
    a = [{"n": 5}]
    b = [{"n": 5, "extra": "noise"}]
    assert not results_equal(a, b)


def test_empty_results() -> None:
    assert results_equal([], [])


def test_empty_vs_nonempty() -> None:
    assert not results_equal([], [{"n": 1}])


def test_string_equality() -> None:
    a = [{"name": "alice"}]
    b = [{"name": "alice"}]
    assert results_equal(a, b)


def test_int_vs_float_with_same_value() -> None:
    """1 and 1.0 should compare equal under float tolerance."""
    a = [{"n": 1}]
    b = [{"n": 1.0}]
    assert results_equal(a, b)


def test_multiple_columns_with_floats() -> None:
    """Multi-column rows where one column is float, one is string."""
    a = [{"name": "alice", "score": 1.0000001}, {"name": "bob", "score": 2.5}]
    b = [{"name": "bob", "score": 2.5}, {"name": "alice", "score": 1.0}]
    assert results_equal(a, b)


def test_nan_equals_nan() -> None:
    """Two queries that both compute AVG over all-NULLs both produce NaN; should compare equal."""
    a = [{"x": float("nan")}]
    b = [{"x": float("nan")}]
    assert results_equal(a, b)


def test_null_vs_nan_not_equal() -> None:
    """NULL is not NaN."""
    a = [{"x": None}]
    b = [{"x": float("nan")}]
    assert not results_equal(a, b)


def test_array_column_equal() -> None:
    """BQ ARRAY columns come back as Python lists; comparator must handle them without crashing."""
    a = [{"arr": [1, 2, 3]}]
    b = [{"arr": [1, 2, 3]}]
    assert results_equal(a, b)


def test_array_column_different_order_not_equal() -> None:
    """Within a single ARRAY value, order matters (BQ arrays are ordered)."""
    a = [{"arr": [1, 2, 3]}]
    b = [{"arr": [3, 2, 1]}]
    assert not results_equal(a, b)


def test_struct_column_equal() -> None:
    """BQ STRUCT columns come back as Python dicts; comparator must handle them without crashing."""
    a = [{"s": {"name": "alice", "age": 30}}]
    b = [{"s": {"age": 30, "name": "alice"}}]  # different key insertion order; should still match
    assert results_equal(a, b)


def test_decimal_within_tolerance_equal() -> None:
    """BQ NUMERIC columns come back as Decimal; should use the same tolerance as floats."""
    a = [{"x": Decimal("1.0000005")}]
    b = [{"x": Decimal("1.0")}]
    assert results_equal(a, b)


def test_decimal_outside_tolerance_not_equal() -> None:
    a = [{"x": Decimal("1.5")}]
    b = [{"x": Decimal("1.0")}]
    assert not results_equal(a, b)


def test_decimal_compared_with_float_uses_tolerance() -> None:
    """Mixed Decimal/float should compare under tolerance."""
    a = [{"x": Decimal("1.0")}]
    b = [{"x": 1.0000001}]
    assert results_equal(a, b)


def test_bool_not_equal_to_int() -> None:
    """True == 1 in Python is misleading for evals; the comparator should distinguish."""
    a = [{"flag": True}]
    b = [{"flag": 1}]
    assert not results_equal(a, b)


def test_bool_equal_to_bool() -> None:
    """Same-type bool comparison still works."""
    a = [{"flag": True}]
    b = [{"flag": True}]
    assert results_equal(a, b)
