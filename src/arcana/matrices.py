"""Propagation matrix validation and spectral calculations for ARCANA."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

import numpy as np

from arcana._validation import expect_non_empty_string, expect_number_min, expect_number_range, expect_sha256, fail
from arcana.errors import ReasonCode
from arcana.model import RhoInterval
from arcana._numerics import SpectralBounds, outward_float, verified_spectral_bounds

MatrixInput = Sequence[Sequence[float]] | np.ndarray


@dataclass(frozen=True)
class TolerancePolicy:
    abs_tolerance: float = 1e-12
    rel_tolerance: float = 1e-12

    def __post_init__(self) -> None:
        expect_number_min(self.abs_tolerance, 0, ("abs_tolerance",), ReasonCode.DENY_MODEL_INPUT_INVALID)
        expect_number_min(self.rel_tolerance, 0, ("rel_tolerance",), ReasonCode.DENY_MODEL_INPUT_INVALID)

    def margin(self, threshold: float) -> float:
        threshold_value = expect_number_range(threshold, 0, 1, ("threshold",), ReasonCode.DENY_MODEL_INPUT_INVALID)
        return outward_float(max(Fraction(self.abs_tolerance), Fraction(self.rel_tolerance) * Fraction(threshold_value)), upper=True)

    def below_threshold_with_margin(self, value: float, threshold: float) -> bool:
        value_checked = expect_number_min(value, 0, ("value",), ReasonCode.DENY_MODEL_INPUT_INVALID)
        threshold_checked = expect_number_range(threshold, 0, 1, ("threshold",), ReasonCode.DENY_MODEL_INPUT_INVALID)
        return Fraction(value_checked) + Fraction(self.margin(threshold_checked)) < Fraction(threshold_checked)


@dataclass(frozen=True)
class PropagationMatrix:
    values: np.ndarray
    node_order: tuple[str, ...] = ()
    graph_hash: str | None = None

    def __post_init__(self) -> None:
        matrix = _validate_nonnegative_square_matrix(self.values, ("matrix",))
        omitted_order = isinstance(self.node_order, tuple) and len(self.node_order) == 0
        node_order = () if omitted_order else _validate_node_order(self.node_order, matrix.shape[0], ("matrix",))
        graph_hash = expect_sha256(self.graph_hash, ("matrix", "graph_hash"), ReasonCode.DENY_GRAPH_HASH_MISMATCH) if self.graph_hash is not None else None
        # A bytes backing store prevents setflags(write=True), unlike an owning array.
        immutable = np.frombuffer(matrix.tobytes(), dtype=np.float64).reshape(matrix.shape)
        object.__setattr__(self, "values", immutable)
        object.__setattr__(self, "node_order", node_order)
        object.__setattr__(self, "graph_hash", graph_hash)

    @classmethod
    def from_values(
        cls,
        values: MatrixInput,
        *,
        node_order: Sequence[str] | None = None,
        graph_hash: str | None = None,
        path: tuple[str | int, ...] = ("matrix",),
    ) -> "PropagationMatrix":
        matrix = _validate_nonnegative_square_matrix(values, path)
        normalized_node_order = _validate_node_order(node_order, matrix.shape[0], path) if node_order is not None else ()
        normalized_graph_hash = expect_sha256(graph_hash, (*path, "graph_hash"), ReasonCode.DENY_GRAPH_HASH_MISMATCH) if graph_hash is not None else None
        matrix.setflags(write=False)
        return cls(values=matrix, node_order=normalized_node_order, graph_hash=normalized_graph_hash)

    @property
    def size(self) -> int:
        return int(self.values.shape[0])

    def spectral_radius(self) -> float:
        return spectral_radius(self)


@dataclass(frozen=True)
class MatrixBundle:
    lower: PropagationMatrix
    mean: PropagationMatrix
    upper: PropagationMatrix

    def __post_init__(self) -> None:
        self.validate_interval_order()

    def validated_snapshot(self) -> "MatrixBundle":
        members = []
        for name in ("lower", "mean", "upper"):
            member = getattr(self, name)
            if not isinstance(member, PropagationMatrix):
                fail("matrix_bundle_member_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID,
                     "each bundle member must be PropagationMatrix", ("matrix_bundle", name))
            members.append(PropagationMatrix(member.values, member.node_order, member.graph_hash))
        return MatrixBundle(*members)

    @classmethod
    def from_values(
        cls,
        lower: MatrixInput,
        mean: MatrixInput,
        upper: MatrixInput,
        *,
        node_order: Sequence[str] | None = None,
        graph_hash: str | None = None,
    ) -> "MatrixBundle":
        bundle = cls(
            lower=PropagationMatrix.from_values(lower, node_order=node_order, graph_hash=graph_hash, path=("K_lower",)),
            mean=PropagationMatrix.from_values(mean, node_order=node_order, graph_hash=graph_hash, path=("K_mean",)),
            upper=PropagationMatrix.from_values(upper, node_order=node_order, graph_hash=graph_hash, path=("K_upper",)),
        )
        bundle.validate_interval_order()
        return bundle

    def validate_interval_order(self) -> None:
        for name in ("lower", "mean", "upper"):
            member = getattr(self, name)
            if not isinstance(member, PropagationMatrix):
                fail("matrix_bundle_member_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID,
                     "each bundle member must be PropagationMatrix", ("matrix_bundle", name))
        if self.lower.values.shape != self.mean.values.shape or self.mean.values.shape != self.upper.values.shape:
            fail("matrix_interval_shape_mismatch", ReasonCode.DENY_MODEL_INPUT_INVALID, "K_lower, K_mean, and K_upper must have the same shape", ("matrix_bundle",))
        if self.lower.node_order != self.mean.node_order or self.mean.node_order != self.upper.node_order:
            fail("matrix_interval_node_order_mismatch", ReasonCode.DENY_MODEL_INPUT_INVALID, "matrix node ordering must match across interval", ("matrix_bundle", "node_order"))
        if self.lower.graph_hash != self.mean.graph_hash or self.mean.graph_hash != self.upper.graph_hash:
            fail("matrix_interval_graph_hash_mismatch", ReasonCode.DENY_GRAPH_HASH_MISMATCH, "matrix graph hashes must match across interval", ("matrix_bundle", "graph_hash"))
        if not np.all(self.lower.values <= self.mean.values):
            fail("matrix_interval_order_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "expected K_lower <= K_mean elementwise", ("matrix_bundle", "K_lower"))
        if not np.all(self.mean.values <= self.upper.values):
            fail("matrix_interval_order_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "expected K_mean <= K_upper elementwise", ("matrix_bundle", "K_upper"))

    def spectral_radii(self, threshold: float) -> RhoInterval:
        snapshot = self.validated_snapshot()
        lower = spectral_bounds(snapshot.lower).lower
        mean = spectral_bounds(snapshot.mean)
        upper = spectral_bounds(snapshot.upper).upper
        return RhoInterval(
            lower=lower,
            mean=min(upper, max(lower, mean.lower + (mean.upper - mean.lower) / 2)),
            upper=upper,
            threshold=expect_number_range(threshold, 0, 1, ("threshold",), ReasonCode.DENY_MODEL_INPUT_INVALID),
        )


def spectral_radius(matrix: PropagationMatrix | MatrixInput) -> float:
    """Return a verified upper endpoint, not an unchecked eigenvalue estimate."""
    return spectral_bounds(matrix).upper


def spectral_bounds(matrix: PropagationMatrix | MatrixInput) -> SpectralBounds:
    values = _validate_nonnegative_square_matrix(matrix.values if isinstance(matrix, PropagationMatrix) else matrix, ("matrix",))
    return verified_spectral_bounds(values)


def _validate_nonnegative_square_matrix(values: Any, path: tuple[str | int, ...]) -> np.ndarray:
    raw = _normalize_raw_matrix(values, path)
    if raw.ndim != 2:
        fail("matrix_rank_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "matrix must be two-dimensional", path)
    rows, cols = raw.shape
    if rows == 0 or cols == 0:
        fail("matrix_empty", ReasonCode.DENY_MODEL_INPUT_INVALID, "matrix must be non-empty", path)
    if rows != cols:
        fail("matrix_not_square", ReasonCode.DENY_MODEL_INPUT_INVALID, "matrix must be square", path)
    if raw.dtype.kind not in {"i", "u", "f"}:
        fail("matrix_value_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "matrix entries must be real numeric values", path)
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        matrix = raw.astype(float, copy=True)
    if not np.all(np.isfinite(matrix)):
        fail("matrix_value_nonfinite", ReasonCode.DENY_MODEL_INPUT_INVALID, "matrix entries must be finite", path)
    if np.any(matrix < 0):
        fail("matrix_value_negative", ReasonCode.DENY_MODEL_INPUT_INVALID, "matrix entries must be nonnegative", path)
    if np.any((raw != 0) & (matrix == 0)):
        fail("matrix_value_underflow", ReasonCode.DENY_MODEL_INPUT_INVALID, "matrix conversion would erase a nonzero entry; provide binary64 values explicitly", path)
    return matrix


def _normalize_raw_matrix(values: Any, path: tuple[str | int, ...]) -> np.ndarray:
    if isinstance(values, np.ndarray):
        return values
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        fail("matrix_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "matrix must be a sequence of rows", path)
    rows: list[list[float]] = []
    expected_cols: int | None = None
    for row_index, row in enumerate(values):
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
            fail("matrix_row_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "matrix row must be a sequence", (*path, row_index))
        if expected_cols is None:
            expected_cols = len(row)
        elif len(row) != expected_cols:
            fail("matrix_row_width_mismatch", ReasonCode.DENY_MODEL_INPUT_INVALID, "all matrix rows must have the same width", (*path, row_index))
        normalized_row: list[float] = []
        for col_index, value in enumerate(row):
            if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
                fail("matrix_value_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "matrix entries must be real numeric values", (*path, row_index, col_index))
            try:
                converted = float(value)
            except OverflowError:
                fail("matrix_value_nonfinite", ReasonCode.DENY_MODEL_INPUT_INVALID, "matrix entry exceeds binary64 range", (*path, row_index, col_index))
            if value != 0 and converted == 0:
                fail("matrix_value_underflow", ReasonCode.DENY_MODEL_INPUT_INVALID, "matrix conversion would erase a nonzero entry", (*path, row_index, col_index))
            normalized_row.append(converted)
        rows.append(normalized_row)
    return np.array(rows, dtype=float)


def _validate_node_order(node_order: Sequence[str], matrix_size: int, path: tuple[str | int, ...]) -> tuple[str, ...]:
    if not isinstance(node_order, Sequence) or isinstance(node_order, (str, bytes)):
        fail("matrix_node_order_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "node_order must be a sequence of node IDs", (*path, "node_order"))
    if len(node_order) != matrix_size:
        fail("matrix_node_order_size_mismatch", ReasonCode.DENY_MODEL_INPUT_INVALID, "node_order length must match matrix size", (*path, "node_order"))
    normalized: list[str] = []
    for index, node_id in enumerate(node_order):
        normalized.append(expect_non_empty_string(node_id, (*path, "node_order", index), ReasonCode.DENY_MODEL_INPUT_INVALID))
    if len(normalized) != len(set(normalized)):
        fail("matrix_node_order_not_unique", ReasonCode.DENY_MODEL_INPUT_INVALID, "node_order entries must be unique", (*path, "node_order"))
    return tuple(normalized)


__all__ = [
    "MatrixBundle",
    "MatrixInput",
    "PropagationMatrix",
    "TolerancePolicy",
    "spectral_radius",
    "spectral_bounds",
    "SpectralBounds",
]
