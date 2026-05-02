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
