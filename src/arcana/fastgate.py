"""FastGate prototype for conservative sparse ARCANA admission."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from fractions import Fraction
from typing import Any, Mapping

import numpy as np

from arcana._validation import (
    expect_calibration_profile_id,
    expect_datetime_string,
    expect_enum,
    expect_int_min,
    expect_non_empty_string,
    expect_number_min,
    expect_number_range,
    expect_risk_model_version,
    expect_sha256,
    fail,
)
from arcana.errors import ArcanaValidationError, CalibrationLevel, FastGateMode, PositiveVectorMethod, ReasonCode, Verdict
from arcana.loss import evaluate_loss_bounds
from arcana.matrices import PropagationMatrix, SpectralBounds, TolerancePolicy, spectral_bounds, spectral_radius
from arcana._numerics import NUMERICAL_CONTRACT_VERSION, nonnegative_difference_upper, outward_float, verified_collatz_bounds
from arcana.model import AutonomyBudget, DecisionHorizon, DecisionResult, FastGateContext, LossBounds


DEFAULT_MAX_CHANGED_ENTRIES = 16
DEFAULT_MAX_DELTA_DENSITY = 0.25

_CALIBRATION_RANK = {
    CalibrationLevel.A0: 0,
    CalibrationLevel.A1: 1,
    CalibrationLevel.A2: 2,
    CalibrationLevel.A3: 3,
}


@dataclass(frozen=True)
class SparseDeltaEntry:
    row: int
    column: int
    value: float


@dataclass(frozen=True)
class SparseMatrixDelta:
    delta_hash: str
    graph_hash: str
    decision_horizon: DecisionHorizon
    entries: tuple[SparseDeltaEntry, ...]
    additive: bool = True


@dataclass(frozen=True)
class PositiveVector:
    values: tuple[float, ...]
    node_order: tuple[str, ...]
    graph_hash: str
    method: PositiveVectorMethod
    epsilon: float | None = None
    irreducible_declared: bool = False
    scc_decomposition_declared: bool = False
    affected_component_closure_valid: bool = False
    component_local_closure_valid: bool = False


@dataclass(frozen=True)
class FastGateCacheBinding:
    risk_model_version: str
    calibration_profile_id: str
    decision_horizon_id: str
    decision_horizon_duration_seconds: int
    graph_hash: str
    delta_hash: str
    threshold: float
    positive_vector_method: PositiveVectorMethod | None
    expires_at: str
    abs_tolerance: float = 1e-12
    rel_tolerance: float = 1e-12
    evidence_hash: str | None = None
    evidence_source_id: str | None = None


@dataclass(frozen=True)
class FastGateRequest:
    mode: FastGateMode
    risk_model_version: str
    calibration_profile_id: str
    calibration_level: CalibrationLevel
    required_calibration_level: CalibrationLevel
    decision_horizon: DecisionHorizon
    decision_time: str
    graph_hash: str
    before_upper: PropagationMatrix
    delta_upper: SparseMatrixDelta
    threshold: float
    autonomy_budget: AutonomyBudget
    positive_vector: PositiveVector | None = None
    tolerance_policy: TolerancePolicy = field(default_factory=TolerancePolicy)
    exact_recompute_available: bool = True
    exact_recompute_on_uncertain: bool = True
    reducible_graph_declared: bool = False
    cache_binding: FastGateCacheBinding | None = None
    evidence_hash: str | None = None
    evidence_source_id: str | None = None
    loss_in_scope: bool = False
    loss_bounds: LossBounds | None = None
    requested_external_requests: int = 0
    requested_memory_writes: int = 0
    requested_output_bytes: int = 0
    max_changed_entries: int = DEFAULT_MAX_CHANGED_ENTRIES
    max_delta_density: float = DEFAULT_MAX_DELTA_DENSITY


@dataclass(frozen=True)
class FastGateEvaluation:
    decision: DecisionResult
    fastgate: FastGateContext
    after_upper: PropagationMatrix | None = None

    @property
    def allowed(self) -> bool:
        return self.decision.verdict in {Verdict.ALLOW_BOUNDED_AUTONOMY, Verdict.ALLOW_WITH_CONTROLS}


def compute_sparse_delta_hash(
    *,
    graph_hash: str,
    decision_horizon: DecisionHorizon,
    entries: Sequence[SparseDeltaEntry],
    additive: bool = True,
) -> str:
    """Hash the canonical, domain-separated public sparse-delta contract."""

    normalized_graph_hash = expect_sha256(graph_hash, ("DeltaK_upper", "graph_hash"), ReasonCode.DENY_GRAPH_HASH_MISMATCH)
    normalized_horizon = _validate_horizon(decision_horizon)
    if not isinstance(additive, bool):
        fail("sparse_delta_additive_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "additive must be boolean", ("DeltaK_upper", "additive"))
    if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence):
        fail("sparse_delta_entries_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "entries must be a sequence", ("DeltaK_upper", "entries"))

    normalized_entries: list[dict[str, int | float]] = []
    seen: set[tuple[int, int]] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, SparseDeltaEntry):
            fail("sparse_delta_entry_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "delta entry must be SparseDeltaEntry", ("DeltaK_upper", "entries", index))
        row = expect_int_min(entry.row, 0, ("DeltaK_upper", "entries", index, "row"), ReasonCode.DENY_MODEL_INPUT_INVALID)
        column = expect_int_min(entry.column, 0, ("DeltaK_upper", "entries", index, "column"), ReasonCode.DENY_MODEL_INPUT_INVALID)
        key = (row, column)
        if key in seen:
            fail("sparse_delta_entry_duplicate", ReasonCode.DENY_MODEL_INPUT_INVALID, "delta entries must not repeat row,column", ("DeltaK_upper", "entries", index))
        seen.add(key)
        normalized_entries.append(
            {
                "row": row,
                "column": column,
                "value": expect_number_min(entry.value, 0, ("DeltaK_upper", "entries", index, "value"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            }
        )

    payload = {
        "schema_version": "arcana.fastgate.sparse_delta_hash.v0.1",
        "graph_hash": normalized_graph_hash,
        "decision_horizon": {
            "id": normalized_horizon.id,
            "duration_seconds": normalized_horizon.duration_seconds,
            "context": normalized_horizon.context,
        },
        "additive": additive,
        "entries": sorted(normalized_entries, key=lambda item: (int(item["row"]), int(item["column"]))),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def evaluate_fastgate(request: FastGateRequest) -> FastGateEvaluation:
    if not isinstance(request, FastGateRequest):
        return _evaluation(
            _deny(ReasonCode.DENY_MODEL_INPUT_INVALID, "fastgate_request_invalid", "request must be FastGateRequest"),
            FastGateContext(mode=FastGateMode.OBSERVE_ONLY),
        )
    try:
        return _evaluate_fastgate_checked(request)
    except ArcanaValidationError as exc:
        issue = exc.primary_issue
        return _evaluation(
            _deny(issue.reason_code, issue.code, issue.message, {"validation_path": issue.path_text}),
            FastGateContext(mode=FastGateMode.OBSERVE_ONLY),
        )


def _evaluate_fastgate_checked(request: FastGateRequest) -> FastGateEvaluation:
    mode = _validate_mode(request.mode)
    risk_model_version = expect_risk_model_version(request.risk_model_version, ("risk_model_version",))
    calibration_profile_id = expect_calibration_profile_id(request.calibration_profile_id, ("calibration_profile_id",))
    calibration_level = _validate_calibration_level(request.calibration_level, ("calibration_level",))
    required_calibration_level = _validate_calibration_level(request.required_calibration_level, ("required_calibration_level",))

    decision_horizon = _validate_horizon(request.decision_horizon)
    decision_time = _parse_datetime(
        expect_datetime_string(request.decision_time, ("decision_time",), ReasonCode.DENY_CONTEXT_STALE),
        ("decision_time",),
        ReasonCode.DENY_CONTEXT_STALE,
    )
    graph_hash = expect_sha256(request.graph_hash, ("graph_hash",), ReasonCode.DENY_GRAPH_HASH_MISMATCH)
    threshold = expect_number_range(request.threshold, 0, 1, ("threshold",), ReasonCode.DENY_MODEL_INPUT_INVALID)
    tolerance_policy = _validate_tolerance_policy(request.tolerance_policy)
    before_upper = _validate_before_matrix(request.before_upper, graph_hash)
    delta_matrix = _validate_sparse_delta(
        request.delta_upper,
        before_upper,
        graph_hash,
        decision_horizon,
        request.max_changed_entries,
        request.max_delta_density,
    )
    evidence_hash = _validate_optional_hash(request.evidence_hash, ("evidence_hash",))
    evidence_source_id = _validate_optional_source_id(request.evidence_source_id, ("evidence_source_id",))
    if mode is not FastGateMode.OBSERVE_ONLY and evidence_hash is None:
        return _evaluation(
            _deny(
                ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
                "fastgate_evidence_hash_missing",
                "FastGate admission requires a hash-bound evidence reference",
            ),
            FastGateContext(mode=FastGateMode.OBSERVE_ONLY),
        )
    cache_failure = _cache_failure(
        request.cache_binding,
        decision_time,
        risk_model_version,
        calibration_profile_id,
        decision_horizon,
        graph_hash,
        request.delta_upper.delta_hash,
        threshold,
        request.positive_vector.method if request.positive_vector is not None else None,
        tolerance_policy,
        evidence_hash,
        evidence_source_id,
    )
    if cache_failure is not None:
        return _evaluation(cache_failure, FastGateContext(mode=FastGateMode.OBSERVE_ONLY))

    budget_precondition_failure = _budget_precondition_failure(request.autonomy_budget, decision_time, request)
    if budget_precondition_failure is not None:
        return _evaluation(budget_precondition_failure, FastGateContext(mode=FastGateMode.OBSERVE_ONLY))

    loss_precondition_failure = _loss_failure(request.loss_in_scope, request.loss_bounds, {})
    if loss_precondition_failure is not None:
        return _evaluation(loss_precondition_failure, FastGateContext(mode=FastGateMode.OBSERVE_ONLY))

    after_values = before_upper.values.copy()
    for row, column in zip(*np.nonzero(delta_matrix), strict=True):
        try:
            after_values[row, column] = outward_float(
                Fraction(float(before_upper.values[row, column])) + Fraction(float(delta_matrix[row, column])),
                upper=True,
            )
        except ArcanaValidationError as exc:
            if exc.code == "spectral_bound_unrepresentable":
                fail("fastgate_after_entry_unrepresentable", ReasonCode.DENY_MODEL_INPUT_INVALID,
                     "outward-rounded matrix update exceeds binary64 range; reduce the delta or deny admission",
                     ("K_after_upper", int(row), int(column)))
            raise
    after_upper = PropagationMatrix.from_values(
        after_values,
        node_order=before_upper.node_order,
        graph_hash=graph_hash,
        path=("K_after_upper",),
    )
    before_bounds = spectral_bounds(before_upper)
    rho_before = before_bounds.upper

    if mode is FastGateMode.OBSERVE_ONLY:
        return _evaluation(
            _result(
                Verdict.OBSERVE_ONLY,
                (ReasonCode.REQUIRE_OBSERVE_ONLY,),
                metrics={"issue_code": "fastgate_observe_only", "rho_before_upper": rho_before,
                         "numerical_contract_version": NUMERICAL_CONTRACT_VERSION},
                caveats=("FastGate observe_only mode does not support admission.",),
            ),
            FastGateContext(mode=FastGateMode.OBSERVE_ONLY),
            after_upper,
        )

    if calibration_level is CalibrationLevel.A0:
        return _evaluation(
            _result(
                Verdict.OBSERVE_ONLY,
                (ReasonCode.REQUIRE_OBSERVE_ONLY, ReasonCode.INFO_A0_NON_CERTIFIABLE),
                metrics={
                    "issue_code": "fastgate_a0_observe_only",
                    "numerical_contract_version": NUMERICAL_CONTRACT_VERSION,
                    "calibration_level": calibration_level.value,
                    "rho_before_upper": rho_before,
                },
                caveats=("A0 calibration cannot support FastGate admission.",),
            ),
            FastGateContext(mode=FastGateMode.OBSERVE_ONLY),
            after_upper,
        )

    if _CALIBRATION_RANK[calibration_level] < _CALIBRATION_RANK[required_calibration_level]:
        return _evaluation(
            _deny(
                ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
                "fastgate_calibration_level_too_weak",
                "calibration level is weaker than required for FastGate",
                {
                    "calibration_level": calibration_level.value,
                    "required_calibration_level": required_calibration_level.value,
                },
            ),
            FastGateContext(mode=FastGateMode.OBSERVE_ONLY),
            after_upper,
        )

    if mode is FastGateMode.EXACT_RECOMPUTE:
        return _exact_recompute_evaluation(request, after_upper, before_bounds, threshold, tolerance_policy, decision_time)

    if mode is FastGateMode.PERRON_COLLATZ_BOUND:
        vector_failure = _positive_vector_failure(request.positive_vector, after_upper, graph_hash, request.reducible_graph_declared)
        if vector_failure is not None:
            return _evaluation(vector_failure, FastGateContext(mode=FastGateMode.OBSERVE_ONLY), after_upper)
        positive_vector = request.positive_vector
        assert positive_vector is not None
        if positive_vector.method is PositiveVectorMethod.FALLBACK_EXACT:
            if not request.exact_recompute_available:
                return _evaluation(
                    _deny(
                        ReasonCode.DENY_FASTGATE_UNCERTAIN,
                        "fastgate_exact_fallback_unavailable",
                        "fallback_exact requires exact recompute availability",
                    ),
                    FastGateContext(mode=FastGateMode.OBSERVE_ONLY),
                    after_upper,
                )
            return _exact_recompute_evaluation(request, after_upper, before_bounds, threshold, tolerance_policy, decision_time)
        bound = _collatz_bound(after_upper, positive_vector)
        fastgate_context = FastGateContext(
            mode=FastGateMode.PERRON_COLLATZ_BOUND,
            positive_vector_method=positive_vector.method,
            upper_bound=bound,
        )
        metrics = {
            "numerical_contract_version": NUMERICAL_CONTRACT_VERSION,
            "rho_before_upper": rho_before,
            "rho_before_lower": before_bounds.lower,
            "fastgate_upper_bound": bound,
            "rho_threshold": threshold,
            "rho_margin": tolerance_policy.margin(threshold),
            "delta_rho_upper_bound": nonnegative_difference_upper(bound, before_bounds.lower),
        }
        budget_failure = _budget_failure(request.autonomy_budget, decision_time, metrics["delta_rho_upper_bound"], request)
        if budget_failure is not None:
            return _evaluation(budget_failure, fastgate_context, after_upper)
        if not tolerance_policy.below_threshold_with_margin(bound, threshold):
            if request.exact_recompute_available and request.exact_recompute_on_uncertain:
                return _exact_recompute_evaluation(request, after_upper, before_bounds, threshold, tolerance_policy, decision_time)
            return _evaluation(
                _deny(
                    ReasonCode.DENY_FASTGATE_UNCERTAIN,
                    "fastgate_upper_bound_margin_insufficient",
                    "FastGate upper bound does not clear threshold with declared margin",
                    metrics,
                ),
                fastgate_context,
                after_upper,
            )
        loss_failure = _loss_failure(request.loss_in_scope, request.loss_bounds, metrics)
        if loss_failure is not None:
            return _evaluation(loss_failure, fastgate_context, after_upper)
        return _evaluation(
            _result(
                Verdict.ALLOW_BOUNDED_AUTONOMY,
                (ReasonCode.ALLOW_BOUNDED_AUTONOMY,),
                metrics=metrics,
            ),
            fastgate_context,
            after_upper,
        )

    return _evaluation(
        _deny(ReasonCode.DENY_FASTGATE_VECTOR_INVALID, "fastgate_mode_invalid", "unsupported FastGate mode"),
        FastGateContext(mode=FastGateMode.OBSERVE_ONLY),
        after_upper,
    )


def _exact_recompute_evaluation(
    request: FastGateRequest,
    after_upper: PropagationMatrix,
    before_bounds: SpectralBounds,
    threshold: float,
    tolerance_policy: TolerancePolicy,
    decision_time: datetime,
) -> FastGateEvaluation:
    if not request.exact_recompute_available:
        return _evaluation(
            _deny(
                ReasonCode.DENY_FASTGATE_UNCERTAIN,
                "fastgate_exact_recompute_unavailable",
                "exact recompute was requested but is unavailable",
            ),
            FastGateContext(mode=FastGateMode.OBSERVE_ONLY),
            after_upper,
        )
    rho_after = spectral_radius(after_upper)
    metrics = {
        "numerical_contract_version": NUMERICAL_CONTRACT_VERSION,
        "rho_before_upper": before_bounds.upper,
        "rho_before_lower": before_bounds.lower,
        "rho_after_upper": rho_after,
        "rho_threshold": threshold,
        "rho_margin": tolerance_policy.margin(threshold),
        "delta_rho_upper": nonnegative_difference_upper(rho_after, before_bounds.lower),
    }
    fastgate_context = FastGateContext(mode=FastGateMode.EXACT_RECOMPUTE)
    budget_failure = _budget_failure(request.autonomy_budget, decision_time, metrics["delta_rho_upper"], request)
    if budget_failure is not None:
        return _evaluation(budget_failure, fastgate_context, after_upper)
    if not tolerance_policy.below_threshold_with_margin(rho_after, threshold):
        return _evaluation(
            _deny(
                ReasonCode.DENY_RHO_UPPER_BOUND,
                "fastgate_exact_rho_upper_bound_exceeded",
                "exact recompute rho_after_upper does not clear threshold with margin",
                metrics,
            ),
            fastgate_context,
            after_upper,
        )
    loss_failure = _loss_failure(request.loss_in_scope, request.loss_bounds, metrics)
    if loss_failure is not None:
        return _evaluation(loss_failure, fastgate_context, after_upper)
    return _evaluation(
        _result(
            Verdict.ALLOW_BOUNDED_AUTONOMY,
            (ReasonCode.ALLOW_BOUNDED_AUTONOMY,),
            metrics=metrics,
        ),
        fastgate_context,
        after_upper,
    )


def _validate_mode(mode: FastGateMode) -> FastGateMode:
    if isinstance(mode, FastGateMode):
        return mode
    return expect_enum(FastGateMode, mode, ("fastgate", "mode"), ReasonCode.DENY_FASTGATE_VECTOR_INVALID)


def _validate_calibration_level(level: CalibrationLevel, path: tuple[str | int, ...]) -> CalibrationLevel:
    if isinstance(level, CalibrationLevel):
        return level
    return expect_enum(CalibrationLevel, level, path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT)


def _validate_horizon(horizon: DecisionHorizon) -> DecisionHorizon:
    if not isinstance(horizon, DecisionHorizon):
        fail("decision_horizon_invalid", ReasonCode.DENY_DECISION_HORIZON_MISMATCH, "decision_horizon must be DecisionHorizon", ("decision_horizon",))
    return DecisionHorizon(
        id=expect_non_empty_string(horizon.id, ("decision_horizon", "id"), ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
        duration_seconds=expect_int_min(horizon.duration_seconds, 1, ("decision_horizon", "duration_seconds"), ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
        context=expect_non_empty_string(horizon.context, ("decision_horizon", "context"), ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
    )


def _validate_tolerance_policy(policy: TolerancePolicy) -> TolerancePolicy:
    if not isinstance(policy, TolerancePolicy):
        fail("tolerance_policy_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "tolerance_policy must be TolerancePolicy", ("tolerance_policy",))
    return TolerancePolicy(abs_tolerance=policy.abs_tolerance, rel_tolerance=policy.rel_tolerance)


def _validate_before_matrix(matrix: PropagationMatrix, graph_hash: str) -> PropagationMatrix:
    if not isinstance(matrix, PropagationMatrix):
        fail("fastgate_before_matrix_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "before_upper must be PropagationMatrix", ("K_before_upper",))
    if not matrix.node_order:
        fail("fastgate_before_matrix_node_order_missing", ReasonCode.DENY_MODEL_INPUT_INVALID, "before_upper requires node_order", ("K_before_upper", "node_order"))
    if matrix.graph_hash is None:
        fail("fastgate_before_matrix_graph_hash_missing", ReasonCode.DENY_GRAPH_HASH_MISMATCH, "before_upper requires graph_hash", ("K_before_upper", "graph_hash"))
    if matrix.graph_hash != graph_hash:
        fail("fastgate_before_matrix_graph_hash_mismatch", ReasonCode.DENY_GRAPH_HASH_MISMATCH, "before_upper graph_hash does not match request", ("K_before_upper", "graph_hash"))
    return PropagationMatrix.from_values(matrix.values, node_order=matrix.node_order, graph_hash=matrix.graph_hash, path=("K_before_upper",))


def _validate_sparse_delta(
    delta: SparseMatrixDelta,
    before_upper: PropagationMatrix,
    graph_hash: str,
    decision_horizon: DecisionHorizon,
    max_changed_entries: int,
    max_delta_density: float,
) -> np.ndarray:
    if not isinstance(delta, SparseMatrixDelta):
        fail("sparse_delta_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "delta_upper must be SparseMatrixDelta", ("DeltaK_upper",))
    declared_delta_hash = expect_sha256(delta.delta_hash, ("DeltaK_upper", "delta_hash"), ReasonCode.DENY_MODEL_INPUT_INVALID)
    delta_graph_hash = expect_sha256(delta.graph_hash, ("DeltaK_upper", "graph_hash"), ReasonCode.DENY_GRAPH_HASH_MISMATCH)
    if delta_graph_hash != graph_hash:
        fail("sparse_delta_graph_hash_mismatch", ReasonCode.DENY_GRAPH_HASH_MISMATCH, "delta graph_hash does not match request", ("DeltaK_upper", "graph_hash"))
    if not _same_horizon(_validate_horizon(delta.decision_horizon), decision_horizon):
        fail("sparse_delta_horizon_mismatch", ReasonCode.DENY_DECISION_HORIZON_MISMATCH, "delta decision horizon does not match request", ("DeltaK_upper", "decision_horizon"))
    if not isinstance(delta.additive, bool) or not delta.additive:
        fail("sparse_delta_not_additive", ReasonCode.DENY_MODEL_INPUT_INVALID, "public v0.1 FastGate supports additive deltas only", ("DeltaK_upper", "additive"))
    max_entries = expect_int_min(max_changed_entries, 1, ("max_changed_entries",), ReasonCode.DENY_MODEL_INPUT_INVALID)
    density = expect_number_min(max_delta_density, 0, ("max_delta_density",), ReasonCode.DENY_MODEL_INPUT_INVALID)
    if density <= 0 or density > 1:
        fail("sparse_delta_density_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "max_delta_density must be in (0, 1]", ("max_delta_density",))
    if not isinstance(delta.entries, tuple):
        fail("sparse_delta_entries_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "entries must be a tuple", ("DeltaK_upper", "entries"))
    matrix_size = before_upper.size
    if len(delta.entries) > max_entries:
        fail("sparse_delta_entry_limit_exceeded", ReasonCode.DENY_MODEL_INPUT_INVALID, "delta changed entries exceed max_changed_entries", ("DeltaK_upper", "entries"))
    if matrix_size > 0 and len(delta.entries) / float(matrix_size * matrix_size) > density:
        fail("sparse_delta_density_exceeded", ReasonCode.DENY_MODEL_INPUT_INVALID, "delta density exceeds max_delta_density", ("DeltaK_upper", "entries"))
    dense = np.zeros_like(before_upper.values, dtype=float)
    seen: set[tuple[int, int]] = set()
    for index, entry in enumerate(delta.entries):
        if not isinstance(entry, SparseDeltaEntry):
            fail("sparse_delta_entry_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "delta entry must be SparseDeltaEntry", ("DeltaK_upper", "entries", index))
        row = _validate_index(entry.row, matrix_size, ("DeltaK_upper", "entries", index, "row"))
        column = _validate_index(entry.column, matrix_size, ("DeltaK_upper", "entries", index, "column"))
        key = (row, column)
        if key in seen:
            fail("sparse_delta_entry_duplicate", ReasonCode.DENY_MODEL_INPUT_INVALID, "delta entries must not repeat row,column", ("DeltaK_upper", "entries", index))
        seen.add(key)
        dense[row, column] = expect_number_min(entry.value, 0, ("DeltaK_upper", "entries", index, "value"), ReasonCode.DENY_MODEL_INPUT_INVALID)
    computed_delta_hash = compute_sparse_delta_hash(
        graph_hash=delta_graph_hash,
        decision_horizon=decision_horizon,
        entries=delta.entries,
        additive=delta.additive,
    )
    if not hmac.compare_digest(declared_delta_hash, computed_delta_hash):
        fail(
            "sparse_delta_hash_mismatch",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "delta_hash does not match canonical sparse-delta content",
            ("DeltaK_upper", "delta_hash"),
        )
    dense.setflags(write=False)
    return dense


def _validate_index(value: int, matrix_size: int, path: tuple[str | int, ...]) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        fail("sparse_delta_index_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "delta index must be integer", path)
    if value < 0 or value >= matrix_size:
        fail("sparse_delta_index_out_of_range", ReasonCode.DENY_MODEL_INPUT_INVALID, "delta index is outside matrix size", path)
    return value


def _cache_failure(
    cache: FastGateCacheBinding | None,
    decision_time: datetime,
    risk_model_version: str,
    calibration_profile_id: str,
    decision_horizon: DecisionHorizon,
    graph_hash: str,
    delta_hash: str,
    threshold: float,
    positive_vector_method: PositiveVectorMethod | None,
    tolerance_policy: TolerancePolicy,
    evidence_hash: str | None,
    evidence_source_id: str | None,
) -> DecisionResult | None:
    if cache is None:
        return None
    if not isinstance(cache, FastGateCacheBinding):
        return _deny(ReasonCode.DENY_CONTEXT_STALE, "fastgate_cache_invalid", "cache_binding must be FastGateCacheBinding")
    expires_at = _parse_datetime(
        expect_datetime_string(cache.expires_at, ("cache_binding", "expires_at"), ReasonCode.DENY_CONTEXT_STALE),
        ("cache_binding", "expires_at"),
        ReasonCode.DENY_CONTEXT_STALE,
    )
    if decision_time >= expires_at:
        return _deny(
            ReasonCode.DENY_CONTEXT_STALE,
            "fastgate_cache_expired",
            "FastGate cache binding is expired",
            {"cache_expires_at": cache.expires_at},
        )
    checks: tuple[tuple[str, Any, Any, ReasonCode], ...] = (
        ("risk_model_version", cache.risk_model_version, risk_model_version, ReasonCode.DENY_RISK_MODEL_UNSUPPORTED),
        ("calibration_profile_id", cache.calibration_profile_id, calibration_profile_id, ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
        ("decision_horizon_id", cache.decision_horizon_id, decision_horizon.id, ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
        ("decision_horizon_duration_seconds", cache.decision_horizon_duration_seconds, decision_horizon.duration_seconds, ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
        ("graph_hash", cache.graph_hash, graph_hash, ReasonCode.DENY_GRAPH_HASH_MISMATCH),
        ("delta_hash", cache.delta_hash, delta_hash, ReasonCode.DENY_MODEL_INPUT_INVALID),
        ("threshold", cache.threshold, threshold, ReasonCode.DENY_CONTEXT_STALE),
        ("positive_vector_method", cache.positive_vector_method, positive_vector_method, ReasonCode.DENY_FASTGATE_VECTOR_INVALID),
        ("abs_tolerance", cache.abs_tolerance, tolerance_policy.abs_tolerance, ReasonCode.DENY_CONTEXT_STALE),
        ("rel_tolerance", cache.rel_tolerance, tolerance_policy.rel_tolerance, ReasonCode.DENY_CONTEXT_STALE),
    )
    for key, cached, current, reason_code in checks:
        if cached != current:
            return _deny(
                reason_code,
                f"fastgate_cache_{key}_mismatch",
                f"FastGate cache {key} does not match current request",
                {"cache_key": key},
            )
    cache_evidence_hash = _validate_optional_hash(cache.evidence_hash, ("cache_binding", "evidence_hash"))
    request_evidence_hash = _validate_optional_hash(evidence_hash, ("evidence_hash",))
    cache_evidence_source_id = _validate_optional_source_id(cache.evidence_source_id, ("cache_binding", "evidence_source_id"))
    request_evidence_source_id = _validate_optional_source_id(evidence_source_id, ("evidence_source_id",))
    if request_evidence_hash is None:
        return _deny(
            ReasonCode.DENY_CONTEXT_STALE,
            "fastgate_cache_evidence_binding_missing",
            "FastGate cache reuse requires a current evidence_hash",
        )
    if cache_evidence_hash is None:
        return _deny(
            ReasonCode.DENY_CONTEXT_STALE,
            "fastgate_cache_evidence_binding_missing",
            "FastGate cache binding requires evidence_hash",
        )
    if cache_evidence_hash != request_evidence_hash:
        return _deny(
            ReasonCode.DENY_CONTEXT_STALE,
            "fastgate_cache_evidence_hash_mismatch",
            "FastGate cache evidence_hash does not match current request",
            {"cache_key": "evidence_hash"},
        )
    if cache_evidence_source_id != request_evidence_source_id:
        return _deny(
            ReasonCode.DENY_CONTEXT_STALE,
            "fastgate_cache_evidence_source_id_mismatch",
            "FastGate cache evidence_source_id does not match current request",
            {"cache_key": "evidence_source_id"},
        )
    return None


def _positive_vector_failure(
    vector: PositiveVector | None,
    after_upper: PropagationMatrix,
    graph_hash: str,
    reducible_graph_declared: bool,
) -> DecisionResult | None:
    if vector is None:
        return _deny(ReasonCode.DENY_FASTGATE_VECTOR_INVALID, "fastgate_positive_vector_missing", "perron_collatz_bound requires a positive vector")
    if not isinstance(vector, PositiveVector):
        return _deny(ReasonCode.DENY_FASTGATE_VECTOR_INVALID, "fastgate_positive_vector_invalid", "positive_vector must be PositiveVector")
    if vector.graph_hash != graph_hash:
        return _deny(
            ReasonCode.DENY_GRAPH_HASH_MISMATCH,
            "fastgate_positive_vector_graph_hash_mismatch",
            "positive vector graph_hash does not match request",
        )
    if vector.node_order != after_upper.node_order:
        return _deny(
            ReasonCode.DENY_FASTGATE_VECTOR_INVALID,
            "fastgate_positive_vector_node_order_mismatch",
            "positive vector node_order does not match matrix node_order",
        )
    if len(vector.values) != after_upper.size:
        return _deny(
            ReasonCode.DENY_FASTGATE_VECTOR_INVALID,
            "fastgate_positive_vector_size_mismatch",
            "positive vector length must match matrix size",
        )
    method = vector.method if isinstance(vector.method, PositiveVectorMethod) else None
    if method is None:
        return _deny(ReasonCode.DENY_FASTGATE_VECTOR_INVALID, "fastgate_positive_vector_method_invalid", "positive vector method is invalid")
    if method is PositiveVectorMethod.IRREDUCIBLE_PERRON_VECTOR:
        if reducible_graph_declared or not vector.irreducible_declared or not _is_irreducible_nonnegative_matrix(after_upper):
            return _deny(
                ReasonCode.DENY_FASTGATE_VECTOR_INVALID,
                "fastgate_reducible_graph_handling_missing",
                "irreducible_perron_vector requires irreducibility declaration and non-reducible graph handling",
            )
    elif method is PositiveVectorMethod.SCC_DECOMPOSITION:
        if not vector.scc_decomposition_declared or not vector.affected_component_closure_valid:
            return _deny(
                ReasonCode.DENY_FASTGATE_VECTOR_INVALID,
                "fastgate_scc_closure_invalid",
                "scc_decomposition requires declared components and affected-component closure",
            )
    elif method is PositiveVectorMethod.EPSILON_FLOOR:
        if vector.epsilon is None:
            return _deny(ReasonCode.DENY_FASTGATE_VECTOR_INVALID, "fastgate_epsilon_missing", "epsilon_floor requires epsilon")
        expect_number_min(vector.epsilon, 0, ("positive_vector", "epsilon"), ReasonCode.DENY_FASTGATE_VECTOR_INVALID)
        if vector.epsilon <= 0:
            return _deny(ReasonCode.DENY_FASTGATE_VECTOR_INVALID, "fastgate_epsilon_invalid", "epsilon must be > 0")
    elif method is PositiveVectorMethod.COMPONENT_LOCAL_GATE:
        if not vector.component_local_closure_valid:
            return _deny(
                ReasonCode.DENY_FASTGATE_VECTOR_INVALID,
                "fastgate_component_local_closure_invalid",
                "component_local_gate requires valid affected-component closure",
            )
    elif method is PositiveVectorMethod.FALLBACK_EXACT:
        return None
    else:
        return _deny(ReasonCode.DENY_FASTGATE_VECTOR_INVALID, "fastgate_positive_vector_method_invalid", "unsupported positive vector method")
    for index, raw_value in enumerate(vector.values):
        value = expect_number_min(raw_value, 0, ("positive_vector", "values", index), ReasonCode.DENY_FASTGATE_VECTOR_INVALID)
        if method is PositiveVectorMethod.EPSILON_FLOOR:
            continue
        if value <= 0:
            return _deny(
                ReasonCode.DENY_FASTGATE_VECTOR_INVALID,
                "fastgate_positive_vector_entry_nonpositive",
                "positive vector entries must be > 0",
                {"vector_index": index},
            )
    return None


def _collatz_bound(matrix: PropagationMatrix, vector: PositiveVector) -> float:
    values = np.array(vector.values, dtype=float)
    if vector.method is PositiveVectorMethod.EPSILON_FLOOR:
        assert vector.epsilon is not None
        values = np.maximum(values, vector.epsilon)
    if np.any(values <= 0):
        fail("fastgate_positive_vector_entry_nonpositive", ReasonCode.DENY_FASTGATE_VECTOR_INVALID, "positive vector entries must be > 0", ("positive_vector", "values"))
    try:
        return verified_collatz_bounds(matrix.values, values).upper
    except ArcanaValidationError as exc:
        if exc.code == "spectral_bound_unrepresentable":
            fail("fastgate_collatz_bound_nonfinite", ReasonCode.DENY_FASTGATE_UNCERTAIN,
                 "verified Collatz bound exceeds binary64 range; deny or recompute", ("fastgate", "upper_bound"))
        raise


def _validate_optional_hash(value: str | None, path: tuple[str | int, ...]) -> str | None:
    if value is None:
        return None
    return expect_sha256(value, path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT)


def _validate_optional_source_id(value: str | None, path: tuple[str | int, ...]) -> str | None:
    if value is None:
        return None
    return expect_non_empty_string(value, path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT)


def _is_irreducible_nonnegative_matrix(matrix: PropagationMatrix) -> bool:
    adjacency = matrix.values > 0
    size = matrix.size
    if size <= 1:
        return True
    reachability = adjacency.copy()
    np.fill_diagonal(reachability, True)
    for pivot in range(size):
        reachability |= reachability[:, [pivot]] & reachability[[pivot], :]
    return bool(np.all(reachability))


def _budget_precondition_failure(
    budget: AutonomyBudget,
    decision_time: datetime,
    request: FastGateRequest,
) -> DecisionResult | None:
    if not isinstance(budget, AutonomyBudget):
        return _deny(ReasonCode.DENY_BUDGET_EXHAUSTED, "fastgate_budget_invalid", "autonomy_budget must be AutonomyBudget")
    expires_at = _parse_datetime(
        expect_datetime_string(budget.expires_at, ("autonomy_budget", "expires_at"), ReasonCode.DENY_BUDGET_EXHAUSTED),
        ("autonomy_budget", "expires_at"),
        ReasonCode.DENY_BUDGET_EXHAUSTED,
    )
    if decision_time >= expires_at:
        return _deny(
            ReasonCode.DENY_BUDGET_EXHAUSTED,
            "fastgate_budget_expired",
            "autonomy budget has expired",
            {"budget_expires_at": budget.expires_at},
        )
    counters_declared = budget.max_delta_rho_upper is not None
    for budget_field, request_field, allowed, requested in (
        ("max_external_requests", "requested_external_requests", budget.max_external_requests, request.requested_external_requests),
        ("max_memory_writes", "requested_memory_writes", budget.max_memory_writes, request.requested_memory_writes),
        ("max_output_bytes", "requested_output_bytes", budget.max_output_bytes, request.requested_output_bytes),
    ):
        requested_count = expect_int_min(requested, 0, (request_field,), ReasonCode.DENY_BUDGET_EXHAUSTED)
        if allowed is None:
            if requested_count > 0:
                return _deny(
                    ReasonCode.DENY_BUDGET_EXHAUSTED,
                    f"fastgate_budget_{request_field}_missing",
                    f"{request_field} is requested but no matching budget counter is declared",
                    {request_field: requested_count},
                )
            continue
        counters_declared = True
        allowed_count = expect_int_min(allowed, 0, ("autonomy_budget", budget_field), ReasonCode.DENY_BUDGET_EXHAUSTED)
        if requested_count > allowed_count:
            return _deny(
                ReasonCode.DENY_BUDGET_EXHAUSTED,
                f"fastgate_budget_{request_field}_exceeded",
                f"{request_field} exceeds autonomy budget",
                {request_field: requested_count, budget_field: allowed_count},
            )
    if not counters_declared:
        return _deny(
            ReasonCode.DENY_BUDGET_EXHAUSTED,
            "fastgate_budget_empty",
            "at least one FastGate budget counter is required",
        )
    return None


def _budget_failure(
    budget: AutonomyBudget,
    decision_time: datetime,
    delta_rho_upper: float,
    request: FastGateRequest,
) -> DecisionResult | None:
    precondition_failure = _budget_precondition_failure(budget, decision_time, request)
    if precondition_failure is not None:
        return precondition_failure
    if budget.max_delta_rho_upper is not None:
        max_delta = expect_number_min(budget.max_delta_rho_upper, 0, ("autonomy_budget", "max_delta_rho_upper"), ReasonCode.DENY_BUDGET_EXHAUSTED)
        if delta_rho_upper > max_delta:
            return _deny(
                ReasonCode.DENY_BUDGET_EXHAUSTED,
                "fastgate_budget_delta_rho_exceeded",
                "delta_rho_upper exceeds FastGate budget",
                {"delta_rho_upper": delta_rho_upper, "max_delta_rho_upper": max_delta},
            )
    return None


def _loss_failure(loss_in_scope: bool, loss_bounds: LossBounds | None, metrics: Mapping[str, Any]) -> DecisionResult | None:
    loss_result = evaluate_loss_bounds(loss_bounds, loss_in_scope=loss_in_scope)
    if loss_result.passed:
        return None
    return _deny(
        loss_result.reason_code or ReasonCode.DENY_LOSS_MODEL_INVALID,
        loss_result.issue_code or "fastgate_loss_failed",
        "loss constraints failed for FastGate request",
        {**metrics, **loss_result.metrics},
    )


def _parse_datetime(value: str, path: tuple[str | int, ...], reason_code: ReasonCode) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        fail("datetime_invalid", reason_code, "expected RFC3339-compatible date-time", path)
    if parsed.tzinfo is None:
        fail("datetime_timezone_missing", reason_code, "date-time must include timezone offset", path)
    return parsed


def _same_horizon(left: DecisionHorizon, right: DecisionHorizon) -> bool:
    return left.id == right.id and left.duration_seconds == right.duration_seconds and left.context == right.context


def _deny(reason_code: ReasonCode, issue_code: str, message: str, metrics: Mapping[str, Any] | None = None) -> DecisionResult:
    return _result(
        Verdict.DENY,
        (reason_code,),
        metrics={**(metrics or {}), "issue_code": issue_code},
        caveats=(message,),
    )


def _result(
    verdict: Verdict,
    reason_codes: Sequence[ReasonCode],
    *,
    metrics: Mapping[str, Any] | None = None,
    caveats: Sequence[str] = (),
) -> DecisionResult:
    return DecisionResult(
        verdict=verdict,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        metrics=dict(metrics or {}),
        caveats=tuple(caveats),
    )


def _evaluation(decision: DecisionResult, fastgate: FastGateContext, after_upper: PropagationMatrix | None = None) -> FastGateEvaluation:
    return FastGateEvaluation(decision=decision, fastgate=fastgate, after_upper=after_upper)


__all__ = [
    "DEFAULT_MAX_CHANGED_ENTRIES",
    "DEFAULT_MAX_DELTA_DENSITY",
    "FastGateCacheBinding",
    "FastGateContext",
    "FastGateEvaluation",
    "FastGateMode",
    "FastGateRequest",
    "PositiveVector",
    "PositiveVectorMethod",
    "SparseDeltaEntry",
    "SparseMatrixDelta",
    "compute_sparse_delta_hash",
    "evaluate_fastgate",
]
