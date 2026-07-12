from __future__ import annotations

import dataclasses
import math

from arcana.calibration import CalibrationProfile, CalibrationUncertainty, EdgeWeightPolicy, EvidenceWindow
from arcana.decision import DecisionEvaluationRequest, DistillationAssessment, evaluate_decision
from arcana.errors import CalibrationLevel, CertificationStatus, FastGateMode, PositiveVectorMethod, ReasonCode, Verdict
from arcana.matrices import MatrixBundle
from arcana.model import AutonomyBudget, DecisionHorizon, FastGateContext, LossBounds


GRAPH_HASH = "sha256:" + "1" * 64
OTHER_GRAPH_HASH = "sha256:" + "2" * 64
DECISION_TIME = "2026-06-09T00:10:00Z"


def _horizon(seconds: int = 300, context: str = "synthetic decision test") -> DecisionHorizon:
    return DecisionHorizon(id="test_5m", duration_seconds=seconds, context=context)


def _profile(
    *,
    level: CalibrationLevel = CalibrationLevel.A1,
    risk_model_version: str = "arcana.risk.v0.2",
    horizon: DecisionHorizon | None = None,
    source: tuple[str, ...] = ("static_conservative_prior",),
    observed_before: str = "2026-06-09T00:00:00Z",
    max_age_seconds: int = 3600,
    certification_status: CertificationStatus | None = None,
) -> CalibrationProfile:
    default_status = CertificationStatus.NON_CERTIFIABLE if level in {CalibrationLevel.A0, CalibrationLevel.A1} else CertificationStatus.CERTIFIABLE_UNDER_PROFILE
    return CalibrationProfile(
        profile_id=f"arcana.cal.test_{level.value.lower()}",
        risk_model_version=risk_model_version,
        level=level,
        decision_horizon=horizon or _horizon(),
        source=source,
        evidence_window=EvidenceWindow(
            observed_after="2026-06-08T23:50:00Z",
            observed_before=observed_before,
            max_age_seconds=max_age_seconds,
        ),
        confidence=0.8,
        uncertainty=CalibrationUncertainty(rho_lower=0.1, rho_mean=0.2, rho_upper=0.3),
        edge_weight_policy=EdgeWeightPolicy(
            unknown_means_risky=True,
            use_upper_bound_for_risk=True,
            use_lower_bound_for_controls=True,
        ),
        caveats=("synthetic unit test calibration",),
        certification_status=certification_status or default_status,
        last_updated_at="2026-06-09T00:00:00Z",
    )


def _budget() -> AutonomyBudget:
    return AutonomyBudget(
        expires_at="2026-06-09T00:30:00Z",
        max_delta_rho_upper=0.05,
        max_external_requests=1,
        max_memory_writes=0,
        max_output_bytes=65536,
    )


def _matrices(*, graph_hash: str = GRAPH_HASH, high_rho: bool = False) -> MatrixBundle:
    if high_rho:
        return MatrixBundle.from_values(
            lower=[[0.0, 0.4], [0.4, 0.0]],
            mean=[[0.0, 0.6], [0.6, 0.0]],
            upper=[[0.0, 0.9], [0.9, 0.0]],
            node_order=("agent", "tool"),
            graph_hash=graph_hash,
        )
    return MatrixBundle.from_values(
        lower=[[0.0, 0.05], [0.05, 0.0]],
        mean=[[0.0, 0.1], [0.1, 0.0]],
        upper=[[0.0, 0.2], [0.2, 0.0]],
        node_order=("agent", "tool"),
        graph_hash=graph_hash,
    )


def _loss() -> LossBounds:
    return LossBounds(
        aar_99_upper=100.0,
        aes_99_upper=150.0,
        max_allowed_aar_99=200.0,
        max_allowed_aes_99=250.0,
    )


def _request(**overrides: object) -> DecisionEvaluationRequest:
    request = DecisionEvaluationRequest(
        risk_model_version="arcana.risk.v0.2",
        calibration_profile=_profile(),
        decision_horizon=_horizon(),
        graph_hash=GRAPH_HASH,
        matrix_bundle=_matrices(),
        rho_threshold=0.8,
        autonomy_budget=_budget(),
        decision_time=DECISION_TIME,
        loss_in_scope=True,
        loss_bounds=_loss(),
        delta_rho_upper=0.01,
    )
    return dataclasses.replace(request, **overrides)


def _assert_result(result, verdict: Verdict, reason_code: ReasonCode) -> None:
    assert result.verdict is verdict
    assert result.reason_codes[0] is reason_code


def test_exact_path_allows_bounded_autonomy() -> None:
    result = evaluate_decision(_request())

    _assert_result(result, Verdict.ALLOW_BOUNDED_AUTONOMY, ReasonCode.ALLOW_BOUNDED_AUTONOMY)
    assert math.isclose(result.metrics["rho_upper"], 0.2, rel_tol=1e-12)


def test_required_controls_route_to_allow_with_controls_when_available() -> None:
    result = evaluate_decision(
        _request(
            required_controls=("read_only_input", "deny_memory_write"),
            available_controls=("read_only_input", "deny_memory_write"),
        )
    )

    _assert_result(result, Verdict.ALLOW_WITH_CONTROLS, ReasonCode.ALLOW_WITH_CONTROLS)
    assert result.required_controls == ("read_only_input", "deny_memory_write")


def test_missing_required_control_routes_to_human_gate() -> None:
    result = evaluate_decision(_request(required_controls=("deny_memory_write",), available_controls=()))

    _assert_result(result, Verdict.REQUIRE_HUMAN_GATE, ReasonCode.REQUIRE_HUMAN_GATE)
    assert result.metrics["issue_code"] == "required_controls_unavailable"


def test_a0_profile_returns_observe_only_with_non_certifiable_info() -> None:
    result = evaluate_decision(
        _request(
            calibration_profile=_profile(
                level=CalibrationLevel.A0,
                source=("synthetic_demo",),
            )
        )
    )

    _assert_result(result, Verdict.OBSERVE_ONLY, ReasonCode.REQUIRE_OBSERVE_ONLY)
    assert ReasonCode.INFO_A0_NON_CERTIFIABLE in result.reason_codes
    assert ReasonCode.INFO_SYNTHETIC_FIXTURE in result.reason_codes


def test_human_gate_requirement_returns_human_gate_verdict() -> None:
    result = evaluate_decision(_request(human_gate_required=True))

    _assert_result(result, Verdict.REQUIRE_HUMAN_GATE, ReasonCode.REQUIRE_HUMAN_GATE)


def test_scope_reduction_requirement_returns_scope_reduction_verdict() -> None:
    result = evaluate_decision(_request(scope_reduction_required=True))

    _assert_result(result, Verdict.REQUIRE_SCOPE_REDUCTION, ReasonCode.REQUIRE_SCOPE_REDUCTION)


def test_calibration_insufficient_deny_reason() -> None:
    result = evaluate_decision(_request(required_calibration_level=CalibrationLevel.A2))

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
    assert result.metrics["issue_code"] == "calibration_level_too_weak"


def test_a1_profile_cannot_be_certifiable_under_public_contract() -> None:
    result = evaluate_decision(
        _request(
            calibration_profile=_profile(
                level=CalibrationLevel.A1,
                certification_status=CertificationStatus.CERTIFIABLE_UNDER_PROFILE,
            )
        )
    )

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
    assert result.metrics["issue_code"] == "calibration_level_must_be_non_certifiable"


def test_source_class_must_match_calibration_level() -> None:
    result = evaluate_decision(
        _request(
            calibration_profile=_profile(
                level=CalibrationLevel.A1,
                source=("runtime_observation",),
            )
        )
    )

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
    assert result.metrics["issue_code"] == "calibration_source_level_mismatch"


def test_risk_model_unsupported_deny_reason() -> None:
    result = evaluate_decision(_request(risk_model_version="arcana.risk.v0.9"))

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_RISK_MODEL_UNSUPPORTED)
    assert result.metrics["issue_code"] == "risk_model_version_unsupported"


def test_model_input_invalid_deny_reason() -> None:
    result = evaluate_decision(_request(matrix_bundle=object()))

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_MODEL_INPUT_INVALID)
    assert result.metrics["issue_code"] == "matrix_bundle_invalid"


def test_context_stale_deny_reason() -> None:
    result = evaluate_decision(
        _request(
            calibration_profile=_profile(
                observed_before="2026-06-09T00:00:00Z",
                max_age_seconds=10,
            )
        )
    )

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_CONTEXT_STALE)
    assert result.metrics["issue_code"] == "calibration_evidence_stale"


def test_graph_hash_mismatch_deny_reason() -> None:
    result = evaluate_decision(_request(graph_hash=OTHER_GRAPH_HASH))

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_GRAPH_HASH_MISMATCH)
    assert result.metrics["issue_code"] == "matrix_graph_hash_mismatch"


def test_decision_horizon_mismatch_deny_reason() -> None:
    result = evaluate_decision(_request(calibration_profile=_profile(horizon=_horizon(seconds=600))))

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_DECISION_HORIZON_MISMATCH)
    assert result.metrics["issue_code"] == "calibration_horizon_mismatch"


def test_rho_upper_bound_deny_reason() -> None:
    result = evaluate_decision(_request(matrix_bundle=_matrices(high_rho=True)))

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_RHO_UPPER_BOUND)
    assert result.metrics["issue_code"] == "rho_upper_bound_exceeded"


def test_rho_threshold_above_subcritical_limit_is_invalid() -> None:
    result = evaluate_decision(_request(rho_threshold=1.01))

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_MODEL_INPUT_INVALID)
    assert result.metrics["issue_code"] == "number_out_of_range"


def test_aar_upper_bound_deny_reason() -> None:
    result = evaluate_decision(
        _request(
            loss_bounds=LossBounds(
                aar_99_upper=225.0,
                aes_99_upper=150.0,
                max_allowed_aar_99=200.0,
                max_allowed_aes_99=250.0,
            )
        )
    )

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_AAR_UPPER_BOUND)
    assert result.metrics["issue_code"] == "aar_upper_bound_exceeded"


def test_loss_model_invalid_deny_reason() -> None:
    result = evaluate_decision(_request(loss_bounds=None))

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_LOSS_MODEL_INVALID)
    assert result.metrics["issue_code"] == "loss_bounds_missing"


def test_aes_upper_bound_deny_reason() -> None:
    result = evaluate_decision(
        _request(
            loss_bounds=LossBounds(
                aar_99_upper=100.0,
                aes_99_upper=275.0,
                max_allowed_aar_99=200.0,
                max_allowed_aes_99=250.0,
            )
        )
    )

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_AES_UPPER_BOUND)
    assert result.metrics["issue_code"] == "aes_upper_bound_exceeded"


def test_budget_exhausted_deny_reason() -> None:
    result = evaluate_decision(_request(delta_rho_upper=0.06))

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_BUDGET_EXHAUSTED)
    assert result.metrics["issue_code"] == "autonomy_budget_delta_rho_exceeded"


def test_requested_counter_without_declared_budget_denies() -> None:
    budget = AutonomyBudget(
        expires_at="2026-06-09T00:30:00Z",
        max_delta_rho_upper=0.05,
    )

    result = evaluate_decision(_request(autonomy_budget=budget, requested_external_requests=1))

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_BUDGET_EXHAUSTED)
    assert result.metrics["issue_code"] == "autonomy_budget_requested_external_requests_missing"


def test_fastgate_uncertain_deny_reason() -> None:
    result = evaluate_decision(_request(fastgate_required=True))

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_FASTGATE_UNCERTAIN)
    assert result.metrics["issue_code"] == "fastgate_context_missing"


def test_fastgate_vector_invalid_deny_reason() -> None:
    result = evaluate_decision(
        _request(
            fastgate=FastGateContext(
                mode=FastGateMode.PERRON_COLLATZ_BOUND,
                positive_vector_method=PositiveVectorMethod.FALLBACK_EXACT,
                upper_bound=0.2,
            )
        )
    )

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_FASTGATE_VECTOR_INVALID)
    assert result.metrics["issue_code"] == "fastgate_positive_vector_method_not_bound"


def test_distillation_risk_deny_reason() -> None:
    result = evaluate_decision(
        _request(
            calibration_profile=_profile(level=CalibrationLevel.A2, source=("controlled_redteam",)),
            distillation=DistillationAssessment(
                evidence_sufficient=True,
                stable_operation=False,
                scope_bounded=True,
                invalidation_rules_declared=True,
            ),
        )
    )

    _assert_result(result, Verdict.DENY, ReasonCode.DENY_DISTILLATION_RISK)
    assert result.metrics["issue_code"] == "distillation_operation_unstable"


def test_rho_breach_can_route_to_scope_reduction_when_declared() -> None:
    result = evaluate_decision(_request(matrix_bundle=_matrices(high_rho=True), scope_reduction_available=True))

    _assert_result(result, Verdict.REQUIRE_SCOPE_REDUCTION, ReasonCode.REQUIRE_SCOPE_REDUCTION)
    assert result.metrics["issue_code"] == "rho_upper_requires_scope_reduction"
