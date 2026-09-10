"""Verified bounds for nonnegative binary64 matrices.

Candidate vectors are numerical heuristics. Only exact rational Collatz ratios
and outward-rounded endpoints are used as certificates. See NUMERICAL_CONTRACT.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, localcontext
from fractions import Fraction
import math

import numpy as np

from arcana._validation import fail
from arcana.errors import ReasonCode

NUMERICAL_CONTRACT_VERSION = "arcana.numerical.v1"


@dataclass(frozen=True)
class SpectralBounds:
    lower: float
    upper: float


def outward_float(value: Fraction, *, upper: bool) -> float:
    """Convert a nonnegative rational without rounding in the unsafe direction."""
    try:
        result = float(value)
    except OverflowError:
        result = math.inf
    if not math.isfinite(result):
        fail("spectral_bound_unrepresentable", ReasonCode.DENY_MODEL_INPUT_INVALID,
             "verified bound exceeds binary64 range; rescale the model or deny admission",
             ("spectral_bounds",))
    represented = Fraction(result)
    if upper and represented < value:
        result = math.nextafter(result, math.inf)
    elif not upper and represented > value:
        result = math.nextafter(result, -math.inf)
    if not math.isfinite(result):
        fail("spectral_bound_unrepresentable", ReasonCode.DENY_MODEL_INPUT_INVALID,
             "outward-rounded bound exceeds binary64 range; deny admission",
             ("spectral_bounds",))
    return result


def nonnegative_difference_upper(after_upper: float, before_lower: float) -> float:
    return outward_float(max(Fraction(0), Fraction(after_upper) - Fraction(before_lower)), upper=True)


def _ratios(rows: list[list[Fraction]], vector: list[Fraction]) -> tuple[Fraction, Fraction]:
    ratios = [sum((a * x for a, x in zip(row, vector, strict=True)), Fraction(0)) / vector[i]
              for i, row in enumerate(rows)]
    return min(ratios), max(ratios)


def verified_collatz_bounds(values: np.ndarray, vector: np.ndarray) -> SpectralBounds:
    if vector.shape != (values.shape[0],):
        fail("collatz_vector_dimension_invalid", ReasonCode.DENY_FASTGATE_VECTOR_INVALID,
             "positive vector length must match matrix dimension", ("positive_vector",))
    if not np.all(np.isfinite(vector)) or np.any(vector <= 0):
        fail("collatz_vector_nonpositive_or_nonfinite", ReasonCode.DENY_FASTGATE_VECTOR_INVALID,
             "Collatz certificate requires finite strictly positive entries", ("positive_vector",))
    rows = [[Fraction(float(a)) for a in row] for row in values]
    lower, upper = _ratios(rows, [Fraction(float(x)) for x in vector])
    return SpectralBounds(outward_float(lower, upper=False), outward_float(upper, upper=True))


def _components(values: np.ndarray) -> list[list[int]]:
    """Iterative Kosaraju decomposition; off-block edges do not change eigenvalues."""
    adjacency = [np.flatnonzero(row).tolist() for row in values]
    reverse: list[list[int]] = [[] for _ in adjacency]
    for source, targets in enumerate(adjacency):
        for target in targets:
            reverse[target].append(source)
    seen: set[int] = set()
    order: list[int] = []
    for root in range(len(adjacency)):
        if root in seen:
            continue
        seen.add(root)
        stack = [(root, iter(adjacency[root]))]
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                order.append(node)
                stack.pop()
            elif child not in seen:
                seen.add(child)
                stack.append((child, iter(adjacency[child])))
    seen.clear()
    components: list[list[int]] = []
    for root in reversed(order):
        if root in seen:
            continue
        seen.add(root)
        pending = [root]
        component = []
        while pending:
            node = pending.pop()
            component.append(node)
            for child in reverse[node]:
                if child not in seen:
                    seen.add(child)
                    pending.append(child)
        components.append(component)
    return components


def _block_bounds(values: np.ndarray) -> tuple[Fraction, Fraction]:
    rows = [[Fraction(float(a)) for a in row] for row in values]
    lower, upper = _ratios(rows, [Fraction(1)] * len(rows))
    relative_target = Fraction(1, 10**14)

    def tight() -> bool:
        return upper - lower <= upper * relative_target

    if tight():
        return lower, upper

    # LAPACK is only a candidate generator, never the source of a bound.
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        try:
            eigenvalues, eigenvectors = np.linalg.eig(values / np.max(values))
        except np.linalg.LinAlgError:
            candidate = None
        else:
            candidate = np.abs(eigenvectors[:, int(np.argmax(eigenvalues.real))])
    if candidate is not None and np.all(np.isfinite(candidate)) and np.all(candidate > 0):
        lo, hi = _ratios(rows, [Fraction(float(x)) for x in candidate])
        lower, upper = max(lower, lo), min(upper, hi)
        if tight():
            return lower, upper

    # Decimal keeps candidate generation away from binary64 overflow/underflow.
    # Convergence is optional: every accepted endpoint is verified with Fraction.
    with localcontext(Context(prec=80, Emin=-999999, Emax=999999)):
        decimal_rows = [[Decimal.from_float(float(a)) for a in row] for row in values]
        vector = [Decimal(1)] * len(rows)
        for iteration in range(128):
            product = [sum((a * x for a, x in zip(row, vector, strict=True)), Decimal(0))
                       for row in decimal_rows]
            vector = [(x * y).sqrt() for x, y in zip(vector, product, strict=True)]
            scale = max(vector)
            vector = [x / scale for x in vector]
            if iteration % 8 == 0 or iteration == 127:
                lo, hi = _ratios(rows, [Fraction(x) for x in vector])
                lower, upper = max(lower, lo), min(upper, hi)
                if tight():
                    break
    return lower, upper


def verified_spectral_bounds(values: np.ndarray) -> SpectralBounds:
    lower = upper = Fraction(0)
    for component in _components(values):
        if len(component) == 1:
            lo = hi = Fraction(float(values[component[0], component[0]]))
        else:
            lo, hi = _block_bounds(values[np.ix_(component, component)])
        lower, upper = max(lower, lo), max(upper, hi)
    return SpectralBounds(outward_float(lower, upper=False), outward_float(upper, upper=True))
