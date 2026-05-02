"""Result-set equivalence comparison.

Spider/BIRD-style: two result sets are equal iff they match as multisets of rows,
where rows are compared as sorted-by-column-name tuples and floats use a tolerance.
NULLs compare equal to NULL. Column-set mismatch fails (the model added or removed
a column).
"""

from __future__ import annotations

from collections import Counter
from math import isclose
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
    cols_a = set(a[0].keys()) if a else set()
    cols_b = set(b[0].keys()) if b else set()
    if cols_a != cols_b:
        return False

    # Sort columns within each row, then build tuples for multiset comparison.
    cols = sorted(cols_a)
    rows_a = [_normalize_row(row, cols) for row in a]
    rows_b = [_normalize_row(row, cols) for row in b]

    # If any row contains a float, fall back to manual comparison (Counter can't tolerance-match).
    if any(_has_float(row) for row in rows_a + rows_b):
        return _multiset_equal_with_float_tolerance(rows_a, rows_b)
    return Counter(rows_a) == Counter(rows_b)


def _normalize_row(row: dict[str, Any], cols: list[str]) -> tuple[Any, ...]:
    return tuple(row.get(c) for c in cols)


def _has_float(row: tuple[Any, ...]) -> bool:
    return any(isinstance(v, float) for v in row)


def _multiset_equal_with_float_tolerance(
    rows_a: list[tuple[Any, ...]],
    rows_b: list[tuple[Any, ...]],
) -> bool:
    """O(n^2) fallback for float-containing rows. Acceptable for eval result sets (small)."""
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
        if va is None and vb is None:
            continue
        if va is None or vb is None:
            return False
        if isinstance(va, float) or isinstance(vb, float):
            if not isclose(float(va), float(vb), rel_tol=_FLOAT_REL_TOL, abs_tol=_FLOAT_ABS_TOL):
                return False
        else:
            if va != vb:
                return False
    return True
