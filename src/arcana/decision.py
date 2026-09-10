"""Ordered decision evaluator for ARCANA."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Mapping

from arcana._validation import (
    expect_bool,
    expect_calibration_profile_id,
    expect_datetime_string,
    expect_int_min,
    expect_non_empty_string,
    expect_number_min,
    expect_number_range,
    expect_risk_model_version,
    expect_sha256,
    fail,
)
from arcana.calibration import (
    CalibrationProfile,
    CalibrationUncertainty,
    EdgeWeightPolicy,
    EvidenceWindow,
    validate_calibration_sources_for_level,
    validate_certification_status_for_level,
)
from arcana.errors import (
    ArcanaValidationError,
    CalibrationLevel,
    CertificationStatus,
    FastGateMode,
    PositiveVectorMethod,
    ReasonCode,
    ValidationIssue,
    Verdict,
)
from arcana.loss import LossBoundEvaluation, evaluate_loss_bounds
from arcana.matrices import MatrixBundle, TolerancePolicy
from arcana._numerics import NUMERICAL_CONTRACT_VERSION
from arcana.model import AutonomyBudget, DecisionHorizon, DecisionResult, FastGateContext, LossBounds, RiskContext


DEFAULT_SUPPORTED_RISK_MODEL_VERSIONS = ("arcana.risk.v0.2",)

_CALIBRATION_RANK = {
    CalibrationLevel.A0: 0,
    CalibrationLevel.A1: 1,
    CalibrationLevel.A2: 2,
    CalibrationLevel.A3: 3,
}


@dataclass(frozen=True)
class DistillationAssessment:
    evidence_sufficient: bool
    stable_operation: bool
    scope_bounded: bool
    invalidation_rules_declared: bool
    required_calibration_level: CalibrationLevel = CalibrationLevel.A2


@dataclass(frozen=True)
class DecisionEvaluationRequest:
    risk_model_version: str
    calibration_profile: CalibrationProfile
    decision_horizon: DecisionHorizon
    graph_hash: str
    matrix_bundle: MatrixBundle
    rho_threshold: float
    autonomy_budget: AutonomyBudget
    decision_time: str
    required_calibration_level: CalibrationLevel = CalibrationLevel.A1
    loss_in_scope: bool = False
    loss_bounds: LossBounds | None = None
    fastgate: FastGateContext | None = None
    fastgate_required: bool = False
    required_controls: Sequence[str] = ()
    available_controls: Sequence[str] = ()
    human_gate_required: bool = False
    scope_reduction_required: bool = False
    scope_reduction_available: bool = False
    distillation: DistillationAssessment | None = None
    delta_rho_upper: float = 0.0
    requested_external_requests: int = 0
    requested_memory_writes: int = 0
    requested_output_bytes: int = 0
    tolerance_policy: TolerancePolicy = field(default_factory=TolerancePolicy)
    supported_risk_model_versions: Sequence[str] = DEFAULT_SUPPORTED_RISK_MODEL_VERSIONS


def evaluate_decision(request: DecisionEvaluationRequest) -> DecisionResult:
    if not isinstance(request, DecisionEvaluationRequest):
        return _validation_result(
            ValidationIssue(
                code="decision_request_invalid",
                reason_code=ReasonCode.DENY_MODEL_INPUT_INVALID,
                message="request must be DecisionEvaluationRequest",
                path=("decision_request",),
            )
        )
    try:
        return _evaluate_decision_checked(request)
    except ArcanaValidationError as exc:
        return _validation_result(exc.primary_issue)


def _evaluate_decision_checked(request: DecisionEvaluationRequest) -> DecisionResult:
    supported_versions = _validate_supported_risk_model_versions(request.supported_risk_model_versions)
    risk_model_version = expect_risk_model_version(request.risk_model_version, ("risk_model_version",))
    if risk_model_version not in supported_versions:
        return _deny(
            ReasonCode.DENY_RISK_MODEL_UNSUPPORTED,
            "risk_model_version_unsupported",
            "risk model version is not supported by this evaluator",
            {"risk_model_version": risk_model_version},
        )

    if not isinstance(request.matrix_bundle, MatrixBundle):
        return _deny(
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "matrix_bundle_invalid",
            "matrix_bundle must be MatrixBundle",
        )
    request = replace(request, matrix_bundle=request.matrix_bundle.validated_snapshot())
    if not request.matrix_bundle.upper.node_order:
        return _deny(
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "matrix_node_order_missing",
            "matrix node ordering must be declared for decision evaluation",
        )

    if not isinstance(request.tolerance_policy, TolerancePolicy):
        return _deny(
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "tolerance_policy_invalid",
            "tolerance_policy must be TolerancePolicy",
        )
    rho_threshold = expect_number_range(request.rho_threshold, 0, 1, ("rho_threshold",), ReasonCode.DENY_MODEL_INPUT_INVALID)
    delta_rho_upper = expect_number_min(request.delta_rho_upper, 0, ("delta_rho_upper",), ReasonCode.DENY_MODEL_INPUT_INVALID)

    if not isinstance(request.decision_horizon, DecisionHorizon):
        return _deny(
            ReasonCode.DENY_DECISION_HORIZON_MISMATCH,
            "decision_horizon_invalid",
            "decision_horizon must be DecisionHorizon",
        )
    decision_horizon = _validate_decision_horizon(request.decision_horizon)

    decision_time = _parse_datetime(
        expect_datetime_string(request.decision_time, ("decision_time",), ReasonCode.DENY_CONTEXT_STALE),
        ("decision_time",),
        ReasonCode.DENY_CONTEXT_STALE,
    )

    if not isinstance(request.calibration_profile, CalibrationProfile):
        return _deny(
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            "calibration_profile_invalid",
            "calibration_profile must be CalibrationProfile",
        )
    calibration_profile = _validate_calibration_profile(request.calibration_profile)
    if calibration_profile.risk_model_version != risk_model_version:
        return _deny(
            ReasonCode.DENY_RISK_MODEL_UNSUPPORTED,
            "calibration_risk_model_mismatch",
            "calibration profile risk model version does not match request",
            {
                "risk_model_version": risk_model_version,
                "calibration_risk_model_version": calibration_profile.risk_model_version,
            },
        )
    if not _same_decision_horizon(decision_horizon, calibration_profile.decision_horizon):
        return _deny(
            ReasonCode.DENY_DECISION_HORIZON_MISMATCH,
            "calibration_horizon_mismatch",
            "calibration profile decision horizon does not match request",
            _horizon_metrics(decision_horizon, calibration_profile.decision_horizon),
        )

    freshness_failure = _calibration_freshness_failure(calibration_profile, decision_time)
    if freshness_failure is not None:
        return freshness_failure

    graph_hash = expect_sha256(request.graph_hash, ("graph_hash",), ReasonCode.DENY_GRAPH_HASH_MISMATCH)
    graph_hash_failure = _graph_hash_failure(request.matrix_bundle, graph_hash)
    if graph_hash_failure is not None:
        return graph_hash_failure

    required_calibration_level = _coerce_calibration_level(
        request.required_calibration_level,
        ("required_calibration_level",),
        ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
    )

    rho_metrics = _rho_metrics(request.matrix_bundle, rho_threshold, request.tolerance_policy)
    base_metrics: dict[str, Any] = {
        **rho_metrics,
        "delta_rho_upper": delta_rho_upper,
        "calibration_level": calibration_profile.level.value,
        "required_calibration_level": required_calibration_level.value,
    }
    synthetic_codes = _synthetic_info_codes(calibration_profile)

    if calibration_profile.level is CalibrationLevel.A0:
        return _result(
            Verdict.OBSERVE_ONLY,
            (ReasonCode.REQUIRE_OBSERVE_ONLY, ReasonCode.INFO_A0_NON_CERTIFIABLE, *synthetic_codes),
            metrics={**base_metrics, "issue_code": "a0_observe_only"},
            caveats=("A0 calibration is non-certifiable and cannot support admission.",),
        )

    if _CALIBRATION_RANK[calibration_profile.level] < _CALIBRATION_RANK[required_calibration_level]:
        return _deny(
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            "calibration_level_too_weak",
            "calibration level is weaker than required",
            base_metrics,
        )

    distillation_failure = _distillation_failure(request.distillation, calibration_profile.level, base_metrics)
    if distillation_failure is not None:
        return distillation_failure

    loss_model_failure = _loss_model_failure(request.loss_in_scope, request.loss_bounds)
    if loss_model_failure is not None:
        return loss_model_failure

    budget_failure = _budget_failure(request.autonomy_budget, decision_time, delta_rho_upper, request)
    if budget_failure is not None:
        return budget_failure

    if not request.tolerance_policy.below_threshold_with_margin(base_metrics["rho_upper"], rho_threshold):
        if request.scope_reduction_available:
            return _result(
                Verdict.REQUIRE_SCOPE_REDUCTION,
                (ReasonCode.REQUIRE_SCOPE_REDUCTION, *synthetic_codes),
                metrics={**base_metrics, "issue_code": "rho_upper_requires_scope_reduction"},
                caveats=("rho_upper does not clear the threshold with the declared numerical margin.",),
            )
        return _deny(
            ReasonCode.DENY_RHO_UPPER_BOUND,
            "rho_upper_bound_exceeded",
            "rho_upper does not clear the threshold with the declared numerical margin",
            base_metrics,
        )

    loss_evaluation = evaluate_loss_bounds(request.loss_bounds, loss_in_scope=request.loss_in_scope)
    if not loss_evaluation.passed:
        return _loss_bound_result(loss_evaluation, base_metrics)
    base_metrics.update(loss_evaluation.metrics)

    fastgate_failure = _fastgate_failure(request.fastgate, request.fastgate_required, base_metrics, request.tolerance_policy)
    if fastgate_failure is not None:
        return fastgate_failure

    required_controls = _validate_string_sequence(
        request.required_controls,
        ("required_controls",),
        ReasonCode.DENY_MODEL_INPUT_INVALID,
        unique=True,
    )
    available_controls = _validate_string_sequence(
        request.available_controls,
        ("available_controls",),
        ReasonCode.DENY_MODEL_INPUT_INVALID,
        unique=True,
    )

    if request.scope_reduction_required:
        return _result(
            Verdict.REQUIRE_SCOPE_REDUCTION,
            (ReasonCode.REQUIRE_SCOPE_REDUCTION, *synthetic_codes),
            metrics={**base_metrics, "issue_code": "scope_reduction_required"},
            caveats=("requested capability envelope must be reduced before admission.",),
        )

    if request.human_gate_required:
        return _result(
            Verdict.REQUIRE_HUMAN_GATE,
            (ReasonCode.REQUIRE_HUMAN_GATE, *synthetic_codes),
            metrics={**base_metrics, "issue_code": "human_gate_required"},
            required_controls=required_controls,
            caveats=("human or policy approval is required before admission.",),
        )

    missing_controls = tuple(control for control in required_controls if control not in available_controls)
    if missing_controls:
        return _result(
            Verdict.REQUIRE_HUMAN_GATE,
            (ReasonCode.REQUIRE_HUMAN_GATE, *synthetic_codes),
            metrics={**base_metrics, "issue_code": "required_controls_unavailable", "missing_controls": missing_controls},
            required_controls=required_controls,
            caveats=("required controls are not declared available.",),
        )

    if required_controls:
        return _result(
            Verdict.ALLOW_WITH_CONTROLS,
            (ReasonCode.ALLOW_WITH_CONTROLS, *synthetic_codes),
            metrics=base_metrics,
            required_controls=required_controls,
        )

    return _result(
        Verdict.ALLOW_BOUNDED_AUTONOMY,
        (ReasonCode.ALLOW_BOUNDED_AUTONOMY, *synthetic_codes),
        metrics=base_metrics,
    )


def _validate_supported_risk_model_versions(values: Sequence[str]) -> tuple[str, ...]:
    versions = _validate_string_sequence(
        values,
        ("supported_risk_model_versions",),
        ReasonCode.DENY_RISK_MODEL_UNSUPPORTED,
        min_items=1,
        unique=True,
    )
    return tuple(expect_risk_model_version(version, ("supported_risk_model_versions", index)) for index, version in enumerate(versions))


def _validate_decision_horizon(horizon: DecisionHorizon) -> DecisionHorizon:
    return DecisionHorizon(
        id=expect_non_empty_string(horizon.id, ("decision_horizon", "id"), ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
        duration_seconds=expect_int_min(horizon.duration_seconds, 1, ("decision_horizon", "duration_seconds"), ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
        context=expect_non_empty_string(horizon.context, ("decision_horizon", "context"), ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
    )


def _validate_calibration_profile(profile: CalibrationProfile) -> CalibrationProfile:
    if not isinstance(profile.level, CalibrationLevel):
        fail("calibration_level_invalid", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "calibration level must be CalibrationLevel", ("calibration_profile", "level"))
    if not isinstance(profile.certification_status, CertificationStatus):
        fail("calibration_status_invalid", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "certification_status must be CertificationStatus", ("calibration_profile", "certification_status"))
    if profile.level is CalibrationLevel.A0 and profile.certification_status is not CertificationStatus.NON_CERTIFIABLE:
        fail("a0_must_be_non_certifiable", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "A0 calibration must be non_certifiable", ("calibration_profile", "certification_status"))
    _validate_evidence_window_object(profile.evidence_window)
    _validate_uncertainty_object(profile.uncertainty)
    _validate_edge_weight_policy_object(profile.edge_weight_policy)
    source = _validate_string_sequence(profile.source, ("calibration_profile", "source"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT, min_items=1, unique=True)
    validate_calibration_sources_for_level(profile.level, source, ("calibration_profile", "source"))
    validate_certification_status_for_level(profile.level, profile.certification_status, source, ("calibration_profile", "certification_status"))
    return CalibrationProfile(
        profile_id=expect_calibration_profile_id(profile.profile_id, ("calibration_profile", "profile_id")),
        risk_model_version=expect_risk_model_version(profile.risk_model_version, ("calibration_profile", "risk_model_version")),
        level=profile.level,
        decision_horizon=_validate_decision_horizon(profile.decision_horizon),
        source=source,
        evidence_window=profile.evidence_window,
        confidence=expect_number_range(profile.confidence, 0, 1, ("calibration_profile", "confidence"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
        uncertainty=profile.uncertainty,
        edge_weight_policy=profile.edge_weight_policy,
        caveats=_validate_string_sequence(profile.caveats, ("calibration_profile", "caveats"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT, min_items=1),
        certification_status=profile.certification_status,
        last_updated_at=profile.last_updated_at,
    )


def _validate_evidence_window_object(window: EvidenceWindow) -> None:
    if not isinstance(window, EvidenceWindow):
        fail("evidence_window_invalid", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "evidence_window must be EvidenceWindow", ("calibration_profile", "evidence_window"))
    expect_datetime_string(window.observed_after, ("calibration_profile", "evidence_window", "observed_after"), ReasonCode.DENY_CONTEXT_STALE)
    expect_datetime_string(window.observed_before, ("calibration_profile", "evidence_window", "observed_before"), ReasonCode.DENY_CONTEXT_STALE)
    expect_int_min(window.max_age_seconds, 1, ("calibration_profile", "evidence_window", "max_age_seconds"), ReasonCode.DENY_CONTEXT_STALE)


def _validate_uncertainty_object(uncertainty: CalibrationUncertainty) -> None:
    if not isinstance(uncertainty, CalibrationUncertainty):
        fail("calibration_uncertainty_invalid", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "uncertainty must be CalibrationUncertainty", ("calibration_profile", "uncertainty"))
    lower = expect_number_min(uncertainty.rho_lower, 0, ("calibration_profile", "uncertainty", "rho_lower"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
    mean = expect_number_min(uncertainty.rho_mean, 0, ("calibration_profile", "uncertainty", "rho_mean"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
    upper = expect_number_min(uncertainty.rho_upper, 0, ("calibration_profile", "uncertainty", "rho_upper"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
    if not lower <= mean <= upper:
        fail("calibration_uncertainty_order_invalid", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "expected rho_lower <= rho_mean <= rho_upper", ("calibration_profile", "uncertainty"))


def _validate_edge_weight_policy_object(policy: EdgeWeightPolicy) -> None:
    if not isinstance(policy, EdgeWeightPolicy):
        fail("edge_weight_policy_invalid", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "edge_weight_policy must be EdgeWeightPolicy", ("calibration_profile", "edge_weight_policy"))
    unknown_means_risky = expect_bool(policy.unknown_means_risky, ("calibration_profile", "edge_weight_policy", "unknown_means_risky"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
    use_upper_bound_for_risk = expect_bool(policy.use_upper_bound_for_risk, ("calibration_profile", "edge_weight_policy", "use_upper_bound_for_risk"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
    use_lower_bound_for_controls = expect_bool(policy.use_lower_bound_for_controls, ("calibration_profile", "edge_weight_policy", "use_lower_bound_for_controls"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
    if not unknown_means_risky:
        fail("edge_weight_policy_unknown_not_risky", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "unknown_means_risky must be true", ("calibration_profile", "edge_weight_policy", "unknown_means_risky"))
    if not use_upper_bound_for_risk:
        fail("edge_weight_policy_risk_not_upper_bound", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "use_upper_bound_for_risk must be true", ("calibration_profile", "edge_weight_policy", "use_upper_bound_for_risk"))
    if not use_lower_bound_for_controls:
        fail("edge_weight_policy_controls_not_lower_bound", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "use_lower_bound_for_controls must be true", ("calibration_profile", "edge_weight_policy", "use_lower_bound_for_controls"))


def _calibration_freshness_failure(profile: CalibrationProfile, decision_time: datetime) -> DecisionResult | None:
    observed_after = _parse_datetime(
        expect_datetime_string(profile.evidence_window.observed_after, ("calibration_profile", "evidence_window", "observed_after"), ReasonCode.DENY_CONTEXT_STALE),
        ("calibration_profile", "evidence_window", "observed_after"),
        ReasonCode.DENY_CONTEXT_STALE,
    )
    observed_before = _parse_datetime(
        expect_datetime_string(profile.evidence_window.observed_before, ("calibration_profile", "evidence_window", "observed_before"), ReasonCode.DENY_CONTEXT_STALE),
        ("calibration_profile", "evidence_window", "observed_before"),
        ReasonCode.DENY_CONTEXT_STALE,
    )
    if observed_after > observed_before:
        return _deny(
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            "evidence_window_order_invalid",
            "evidence observed_after must not be later than observed_before",
        )
    if decision_time < observed_before:
        return _deny(
            ReasonCode.DENY_CONTEXT_STALE,
            "decision_time_before_evidence_window",
            "decision_time predates the calibration evidence window",
        )
    max_age_seconds = expect_int_min(
        profile.evidence_window.max_age_seconds,
        1,
        ("calibration_profile", "evidence_window", "max_age_seconds"),
        ReasonCode.DENY_CONTEXT_STALE,
    )
    age_seconds = (decision_time - observed_before).total_seconds()
    if age_seconds > max_age_seconds:
        return _deny(
            ReasonCode.DENY_CONTEXT_STALE,
            "calibration_evidence_stale",
            "calibration evidence is older than max_age_seconds",
            {"evidence_age_seconds": age_seconds, "max_age_seconds": max_age_seconds},
        )
    if profile.last_updated_at is not None:
        last_updated = _parse_datetime(
            expect_datetime_string(profile.last_updated_at, ("calibration_profile", "last_updated_at"), ReasonCode.DENY_CONTEXT_STALE),
            ("calibration_profile", "last_updated_at"),
            ReasonCode.DENY_CONTEXT_STALE,
        )
        if last_updated > decision_time:
            return _deny(
                ReasonCode.DENY_CONTEXT_STALE,
                "calibration_last_updated_in_future",
                "calibration profile last_updated_at is later than decision_time",
            )
    return None


def _graph_hash_failure(bundle: MatrixBundle, graph_hash: str) -> DecisionResult | None:
    matrix_hashes = (bundle.lower.graph_hash, bundle.mean.graph_hash, bundle.upper.graph_hash)
    if any(value is None for value in matrix_hashes):
        return _deny(
            ReasonCode.DENY_GRAPH_HASH_MISMATCH,
            "matrix_graph_hash_missing",
            "matrix interval must be bound to graph_hash",
        )
    if any(value != graph_hash for value in matrix_hashes):
        return _deny(
            ReasonCode.DENY_GRAPH_HASH_MISMATCH,
            "matrix_graph_hash_mismatch",
            "matrix interval graph_hash does not match request graph_hash",
            {"graph_hash": graph_hash},
        )
    return None


def _distillation_failure(
    assessment: DistillationAssessment | None,
    calibration_level: CalibrationLevel,
    metrics: Mapping[str, Any],
) -> DecisionResult | None:
    if assessment is None:
        return None
    if not isinstance(assessment, DistillationAssessment):
        return _deny(
            ReasonCode.DENY_DISTILLATION_RISK,
            "distillation_assessment_invalid",
            "distillation assessment must be DistillationAssessment",
            metrics,
        )
    required_level = _coerce_calibration_level(
        assessment.required_calibration_level,
        ("distillation", "required_calibration_level"),
        ReasonCode.DENY_DISTILLATION_RISK,
    )
    checks = (
        ("distillation_evidence_insufficient", assessment.evidence_sufficient),
        ("distillation_operation_unstable", assessment.stable_operation),
        ("distillation_scope_unbounded", assessment.scope_bounded),
        ("distillation_invalidation_rules_missing", assessment.invalidation_rules_declared),
        ("distillation_calibration_too_weak", _CALIBRATION_RANK[calibration_level] >= _CALIBRATION_RANK[required_level]),
    )
    for issue_code, passed in checks:
        if not isinstance(passed, bool):
            return _deny(
                ReasonCode.DENY_DISTILLATION_RISK,
                "distillation_assessment_flag_invalid",
                "distillation assessment flags must be boolean",
                metrics,
            )
        if not passed:
            return _deny(
                ReasonCode.DENY_DISTILLATION_RISK,
                issue_code,
                "distillation request is not eligible under declared evidence, stability, scope, invalidation, and calibration constraints",
                {**metrics, "distillation_required_calibration_level": required_level.value},
            )
    return None


def _loss_model_failure(loss_in_scope: bool, loss_bounds: LossBounds | None) -> DecisionResult | None:
    if not loss_in_scope:
        return None
    if not isinstance(loss_bounds, LossBounds):
        return _deny(
            ReasonCode.DENY_LOSS_MODEL_INVALID,
            "loss_bounds_missing",
            "loss is in scope but loss_bounds are missing or invalid",
        )
    return None


def _budget_failure(
    budget: AutonomyBudget,
    decision_time: datetime,
    delta_rho_upper: float,
    request: DecisionEvaluationRequest,
) -> DecisionResult | None:
    if not isinstance(budget, AutonomyBudget):
        return _deny(
            ReasonCode.DENY_BUDGET_EXHAUSTED,
            "autonomy_budget_invalid",
            "autonomy_budget must be AutonomyBudget",
        )
    expires_at = _parse_datetime(
        expect_datetime_string(budget.expires_at, ("autonomy_budget", "expires_at"), ReasonCode.DENY_BUDGET_EXHAUSTED),
        ("autonomy_budget", "expires_at"),
        ReasonCode.DENY_BUDGET_EXHAUSTED,
    )
    if decision_time >= expires_at:
        return _deny(
            ReasonCode.DENY_BUDGET_EXHAUSTED,
            "autonomy_budget_expired",
            "autonomy budget has expired",
            {"decision_time": request.decision_time, "budget_expires_at": budget.expires_at},
        )
    counters_declared = False
    if budget.max_delta_rho_upper is not None:
        counters_declared = True
        max_delta = expect_number_min(budget.max_delta_rho_upper, 0, ("autonomy_budget", "max_delta_rho_upper"), ReasonCode.DENY_BUDGET_EXHAUSTED)
        if delta_rho_upper > max_delta:
            return _deny(
                ReasonCode.DENY_BUDGET_EXHAUSTED,
                "autonomy_budget_delta_rho_exceeded",
                "delta_rho_upper exceeds autonomy budget",
                {"delta_rho_upper": delta_rho_upper, "max_delta_rho_upper": max_delta},
            )
    counter_checks = (
        ("max_external_requests", "requested_external_requests", budget.max_external_requests, request.requested_external_requests),
        ("max_memory_writes", "requested_memory_writes", budget.max_memory_writes, request.requested_memory_writes),
        ("max_output_bytes", "requested_output_bytes", budget.max_output_bytes, request.requested_output_bytes),
    )
    for budget_field, request_field, allowed, requested in counter_checks:
        requested_count = expect_int_min(requested, 0, (request_field,), ReasonCode.DENY_BUDGET_EXHAUSTED)
        if allowed is None:
            if requested_count > 0:
                return _deny(
                    ReasonCode.DENY_BUDGET_EXHAUSTED,
                    f"autonomy_budget_{request_field}_missing",
                    f"{request_field} is requested but no matching budget counter is declared",
                    {request_field: requested_count},
                )
            continue
        counters_declared = True
        allowed_count = expect_int_min(allowed, 0, ("autonomy_budget", budget_field), ReasonCode.DENY_BUDGET_EXHAUSTED)
        if requested_count > allowed_count:
            return _deny(
                ReasonCode.DENY_BUDGET_EXHAUSTED,
                f"autonomy_budget_{request_field}_exceeded",
                f"{request_field} exceeds autonomy budget",
                {request_field: requested_count, budget_field: allowed_count},
            )
    if not counters_declared:
        return _deny(
            ReasonCode.DENY_BUDGET_EXHAUSTED,
            "autonomy_budget_empty",
            "at least one autonomy budget counter is required",
        )
    return None


def _rho_metrics(bundle: MatrixBundle, threshold: float, tolerance_policy: TolerancePolicy) -> dict[str, Any]:
    interval = bundle.spectral_radii(threshold)
    if not interval.lower <= interval.mean <= interval.upper:
        fail("rho_interval_order_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "expected rho_lower <= rho_mean <= rho_upper", ("rho_interval",))
    margin = tolerance_policy.margin(threshold)
    return {
        "numerical_contract_version": NUMERICAL_CONTRACT_VERSION,
        "rho_lower": interval.lower,
        "rho_mean": interval.mean,
        "rho_upper": interval.upper,
        "rho_threshold": interval.threshold,
        "rho_margin": margin,
    }


def _loss_bound_result(loss_evaluation: LossBoundEvaluation, metrics: Mapping[str, Any]) -> DecisionResult:
    reason_code = loss_evaluation.reason_code or ReasonCode.DENY_LOSS_MODEL_INVALID
    issue_code = loss_evaluation.issue_code or "loss_bound_failed"
    return _deny(
        reason_code,
        issue_code,
        "loss upper bound does not satisfy declared limit",
        {**metrics, **loss_evaluation.metrics},
    )


def _fastgate_failure(
    fastgate: FastGateContext | None,
    required: bool,
    metrics: Mapping[str, Any],
    tolerance_policy: TolerancePolicy,
) -> DecisionResult | None:
    if fastgate is None:
        if required:
            return _deny(
                ReasonCode.DENY_FASTGATE_UNCERTAIN,
                "fastgate_context_missing",
                "FastGate was required but no FastGate context was provided",
                metrics,
            )
        return None
    if not isinstance(fastgate, FastGateContext):
        return _deny(
            ReasonCode.DENY_FASTGATE_VECTOR_INVALID,
            "fastgate_context_invalid",
            "fastgate must be FastGateContext",
            metrics,
        )
    if fastgate.mode is FastGateMode.OBSERVE_ONLY:
        return _result(
            Verdict.OBSERVE_ONLY,
            (ReasonCode.REQUIRE_OBSERVE_ONLY,),
            metrics={**metrics, "issue_code": "fastgate_observe_only"},
            caveats=("FastGate observe_only mode does not support admission.",),
        )
    if fastgate.mode is FastGateMode.EXACT_RECOMPUTE:
        return None
    if fastgate.mode is FastGateMode.PERRON_COLLATZ_BOUND:
        if fastgate.positive_vector_method is PositiveVectorMethod.FALLBACK_EXACT:
            return _deny(
                ReasonCode.DENY_FASTGATE_VECTOR_INVALID,
                "fastgate_positive_vector_method_not_bound",
                "fallback_exact is not a positive-vector proof method for perron_collatz_bound",
                metrics,
            )
        if fastgate.upper_bound is None:
            return _deny(
                ReasonCode.DENY_FASTGATE_UNCERTAIN,
                "fastgate_upper_bound_missing",
                "perron_collatz_bound requires upper_bound",
                metrics,
            )
        upper_bound = expect_number_min(fastgate.upper_bound, 0, ("fastgate", "upper_bound"), ReasonCode.DENY_FASTGATE_UNCERTAIN)
        if upper_bound < metrics["rho_upper"]:
            return _deny(
                ReasonCode.DENY_FASTGATE_UNCERTAIN,
                "fastgate_upper_bound_not_conservative",
                "FastGate upper_bound is below exact rho_upper",
                {**metrics, "fastgate_upper_bound": upper_bound},
            )
        if not tolerance_policy.below_threshold_with_margin(upper_bound, metrics["rho_threshold"]):
            return _deny(
                ReasonCode.DENY_FASTGATE_UNCERTAIN,
                "fastgate_upper_bound_margin_insufficient",
                "FastGate upper_bound does not clear threshold with margin",
                {**metrics, "fastgate_upper_bound": upper_bound},
            )
        return None
    return _deny(
        ReasonCode.DENY_FASTGATE_VECTOR_INVALID,
        "fastgate_mode_invalid",
        "unsupported FastGate mode",
        metrics,
    )


def _coerce_calibration_level(value: Any, path: tuple[str | int, ...], reason_code: ReasonCode) -> CalibrationLevel:
    if isinstance(value, CalibrationLevel):
        return value
    if isinstance(value, str):
        try:
            return CalibrationLevel(value)
        except ValueError:
            pass
    fail("calibration_level_invalid", reason_code, "unsupported calibration level", path)


def _validate_string_sequence(
    value: Sequence[str],
    path: tuple[str | int, ...],
    reason_code: ReasonCode,
    *,
    min_items: int = 0,
    unique: bool = False,
) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        fail("array_invalid", reason_code, "expected sequence of strings", path)
    if len(value) < min_items:
        fail("array_too_short", reason_code, f"expected at least {min_items} item(s)", path)
    normalized: list[str] = []
    for index, item in enumerate(value):
        normalized.append(expect_non_empty_string(item, (*path, index), reason_code))
    if unique and len(normalized) != len(set(normalized)):
        fail("array_not_unique", reason_code, "expected unique string values", path)
    return tuple(normalized)


def _parse_datetime(value: str, path: tuple[str | int, ...], reason_code: ReasonCode) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        fail("datetime_invalid", reason_code, "expected RFC3339-compatible date-time", path)
    if parsed.tzinfo is None:
        fail("datetime_timezone_missing", reason_code, "date-time must include timezone offset", path)
    return parsed


def _same_decision_horizon(left: DecisionHorizon, right: DecisionHorizon) -> bool:
    return left.id == right.id and left.duration_seconds == right.duration_seconds and left.context == right.context


def _horizon_metrics(request_horizon: DecisionHorizon, profile_horizon: DecisionHorizon) -> dict[str, Any]:
    return {
        "request_horizon_id": request_horizon.id,
        "profile_horizon_id": profile_horizon.id,
        "request_horizon_seconds": request_horizon.duration_seconds,
        "profile_horizon_seconds": profile_horizon.duration_seconds,
    }


def _synthetic_info_codes(profile: CalibrationProfile) -> tuple[ReasonCode, ...]:
    return (ReasonCode.INFO_SYNTHETIC_FIXTURE,) if "synthetic_demo" in profile.source else ()


def _deny(reason_code: ReasonCode, issue_code: str, message: str, metrics: Mapping[str, Any] | None = None) -> DecisionResult:
    return _result(
        Verdict.DENY,
        (reason_code,),
        metrics={**(metrics or {}), "issue_code": issue_code},
        caveats=(message,),
    )


def _validation_result(issue: ValidationIssue) -> DecisionResult:
    return _deny(
        issue.reason_code,
        issue.code,
        issue.message,
        {"validation_path": issue.path_text},
    )


def _result(
    verdict: Verdict,
    reason_codes: Sequence[ReasonCode],
    *,
    metrics: Mapping[str, Any] | None = None,
    required_controls: Sequence[str] = (),
    caveats: Sequence[str] = (),
) -> DecisionResult:
    codes = tuple(dict.fromkeys(reason_codes))
    if not codes:
        fail("reason_codes_empty", ReasonCode.DENY_MODEL_INPUT_INVALID, "decision result requires at least one reason code", ("reason_codes",))
    return DecisionResult(
        verdict=verdict,
        reason_codes=codes,
        metrics=dict(metrics or {}),
        required_controls=tuple(required_controls),
        caveats=tuple(caveats),
    )


__all__ = [
    "DEFAULT_SUPPORTED_RISK_MODEL_VERSIONS",
    "DecisionEvaluationRequest",
    "DecisionResult",
    "DistillationAssessment",
    "ReasonCode",
    "RiskContext",
    "Verdict",
    "evaluate_decision",
]
