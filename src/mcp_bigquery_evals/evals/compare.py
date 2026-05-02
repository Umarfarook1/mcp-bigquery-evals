"""Result-set equivalence comparison.

Spider/BIRD-style: two result sets are equal iff they match as multisets of rows,
where rows are compared as sorted-by-column-name tuples and floats use a tolerance.
NULLs compare equal to NULL. Column-set mismatch fails (the model added or removed
a column). BQ ARRAY (list) and STRUCT (dict) values are supported. Decimal values
(BQ NUMERIC/BIGNUMERIC) use the same float tolerance as plain floats. bool and int
are treated as distinct types even though Python's `True == 1` would suggest otherwise.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from decimal import Decimal
from math import isclose, isnan
from typing import Any

_FLOAT_REL_TOL = 1e-6
_FLOAT_ABS_TOL = 1e-9


def results_equal(
    a: list[dict[str, Any]],
    b: list[dict[str, Any]],
) -> bool:
    """Returns True iff `a` and `b` are equal result sets under multiset semantics."""
    if len(a) != len(b):
        return False
    if not a and not b:
        return True

    # Column sets must match
    cols_a = set(a[0].keys())
    cols_b = set(b[0].keys())
    if cols_a != cols_b:
        return False

    # Sort columns within each row, then build tuples for multiset comparison.
    cols = sorted(cols_a)
    rows_a = [_normalize_row(row, cols) for row in a]
    rows_b = [_normalize_row(row, cols) for row in b]

    # If any row contains a float, Decimal, or nested structure, fall back to
    # manual comparison (Counter can't tolerance-match or hash lists/dicts).
    if any(_has_numeric(row) for row in rows_a + rows_b):
        return _multiset_equal_with_float_tolerance(rows_a, rows_b)
    return Counter(rows_a) == Counter(rows_b)


def _to_hashable(v: Any) -> Any:
    """Recursively convert lists and dicts to hashable equivalents."""
    if isinstance(v, list):
        return tuple(_to_hashable(item) for item in v)
    if isinstance(v, dict):
        return tuple(sorted((k, _to_hashable(val)) for k, val in v.items()))
    return v


def _normalize_row(row: dict[str, Any], cols: list[str]) -> tuple[Any, ...]:
    return tuple(_to_hashable(row.get(c)) for c in cols)


def _flatten(value: Any) -> Iterable[Any]:
    """Yield all leaf values from a nested tuple.

    Decimals/floats inside structs or arrays trigger the slow path too.
    """
    if isinstance(value, tuple):
        for item in value:
            yield from _flatten(item)
    else:
        yield value


def _has_numeric(row: tuple[Any, ...]) -> bool:
    return any(isinstance(v, (float, Decimal, bool)) for v in _flatten(row))


def _multiset_equal_with_float_tolerance(
    rows_a: list[tuple[Any, ...]],
    rows_b: list[tuple[Any, ...]],
) -> bool:
    """O(n²) fallback for rows containing floats, Decimals, or nested structures.

    Practical limit: ~1000 rows per result set (~0.5s in worst case).
    Eval pairs producing larger result sets should add LIMIT.
    """
    matched = [False] * len(rows_b)
    for ra in rows_a:
        found = False
        for j, rb in enumerate(rows_b):
            if matched[j]:
                continue
            if _row_equal(ra, rb):
                matched[j] = True
                found = True
                break
        if not found:
            return False
    return all(matched)


def _row_equal(a: tuple[Any, ...], b: tuple[Any, ...]) -> bool:
    if len(a) != len(b):
        return False
    for va, vb in zip(a, b, strict=True):
        if not _value_equal(va, vb):
            return False
    return True


def _value_equal(va: Any, vb: Any) -> bool:
    """Compare two values with NULL/NaN/Decimal/float/bool semantics."""
    if va is None and vb is None:
        return True
    if va is None or vb is None:
        return False
    # bool must not compare equal to int (Python's True == 1 is misleading for evals)
    if (isinstance(va, bool) or isinstance(vb, bool)) and type(va) is not type(vb):
        return False
    # Recursive: tuples (originally lists/structs)
    if isinstance(va, tuple) and isinstance(vb, tuple):
        return _row_equal(va, vb)
    # NaN equality
    if isinstance(va, float) and isinstance(vb, float):
        if isnan(va) and isnan(vb):
            return True
    # Float / Decimal tolerance
    if isinstance(va, (float, Decimal)) or isinstance(vb, (float, Decimal)):
        try:
            return isclose(float(va), float(vb), rel_tol=_FLOAT_REL_TOL, abs_tol=_FLOAT_ABS_TOL)
        except (TypeError, ValueError):
            return False
    return bool(va == vb)
