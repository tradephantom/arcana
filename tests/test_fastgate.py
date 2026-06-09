from __future__ import annotations

from arcana.certificate import (
    BoundedAutonomyCertificate,
    CertificateCalibrationProfile,
    CertificateType,
    certificate_to_mapping,
    risk_context_to_mapping,
)
from arcana.errors import CalibrationLevel, CertificationStatus, FastGateMode, PositiveVectorMethod, ReasonCode, SchemaVersion, Verdict
from arcana.fastgate import (
    FastGateCacheBinding,
    FastGateRequest,
    PositiveVector,
    SparseDeltaEntry,
    SparseMatrixDelta,
    evaluate_fastgate,
)
from arcana.matrices import PropagationMatrix, TolerancePolicy
from arcana.model import AutonomyBudget, DecisionHorizon, EvidenceReference, LossBounds, RhoInterval, RiskContext
from arcana.schemas import validate_document


GRAPH_HASH = "sha256:" + "6" * 64
OTHER_GRAPH_HASH = "sha256:" + "7" * 64
DELTA_HASH = "sha256:" + "8" * 64
DECISION_TIME = "2026-06-09T00:10:00Z"


def _horizon(seconds: int = 300) -> DecisionHorizon:
    return DecisionHorizon(id="fastgate_5m", duration_seconds=seconds, context="synthetic FastGate unit test")


def _budget(max_delta: float = 0.1) -> AutonomyBudget:
    return AutonomyBudget(
        expires_at="2026-06-09T00:30:00Z",
        max_delta_rho_upper=max_delta,
        max_external_requests=0,
        max_memory_writes=0,
        max_output_bytes=65536,
    )


def _before_matrix(graph_hash: str = GRAPH_HASH) -> PropagationMatrix:
    return PropagationMatrix.from_values(
        [[0.0, 0.2], [0.2, 0.0]],
        node_order=("agent", "tool"),
        graph_hash=graph_hash,
    )


def _delta(value: float = 0.1, *, graph_hash: str = GRAPH_HASH, horizon: DecisionHorizon | None = None) -> SparseMatrixDelta:
    return SparseMatrixDelta(
        delta_hash=DELTA_HASH,
        graph_hash=graph_hash,
        decision_horizon=horizon or _horizon(),
        entries=(SparseDeltaEntry(row=0, column=1, value=value),),
    )


def _positive_vector(method: PositiveVectorMethod = PositiveVectorMethod.IRREDUCIBLE_PERRON_VECTOR) -> PositiveVector:
    return PositiveVector(
        values=(1.0, 1.0),
        node_order=("agent", "tool"),
        graph_hash=GRAPH_HASH,
        method=method,
        irreducible_declared=method is PositiveVectorMethod.IRREDUCIBLE_PERRON_VECTOR,
        scc_decomposition_declared=method is PositiveVectorMethod.SCC_DECOMPOSITION,
        affected_component_closure_valid=method is PositiveVectorMethod.SCC_DECOMPOSITION,
        component_local_closure_valid=method is PositiveVectorMethod.COMPONENT_LOCAL_GATE,
    )


def _request(**overrides: object) -> FastGateRequest:
    request = FastGateRequest(
        mode=FastGateMode.EXACT_RECOMPUTE,
        risk_model_version="arcana.risk.v0.2",
        calibration_profile_id="arcana.cal.fastgate_a1",
        calibration_level=CalibrationLevel.A1,
        required_calibration_level=CalibrationLevel.A1,
        decision_horizon=_horizon(),
        decision_time=DECISION_TIME,
        graph_hash=GRAPH_HASH,
        before_upper=_before_matrix(),
        delta_upper=_delta(),
        threshold=0.8,
        autonomy_budget=_budget(),
    )
    return request.__class__(**{**request.__dict__, **overrides})


def _assert_result(evaluation, verdict: Verdict, reason_code: ReasonCode) -> None:
    assert evaluation.decision.verdict is verdict
    assert evaluation.decision.reason_codes[0] is reason_code


def test_exact_recompute_allows_when_after_rho_is_below_threshold() -> None:
    evaluation = evaluate_fastgate(_request())

    _assert_result(evaluation, Verdict.ALLOW_BOUNDED_AUTONOMY, ReasonCode.ALLOW_BOUNDED_AUTONOMY)
    assert evaluation.fastgate.mode is FastGateMode.EXACT_RECOMPUTE
    assert evaluation.decision.metrics["rho_after_upper"] < evaluation.decision.metrics["rho_threshold"]


def test_exact_recompute_denies_rho_breach() -> None:
    evaluation = evaluate_fastgate(_request(delta_upper=_delta(4.0), autonomy_budget=_budget(max_delta=10.0)))

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_RHO_UPPER_BOUND)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_exact_rho_upper_bound_exceeded"


def test_warm_path_allows_with_valid_positive_vector() -> None:
    evaluation = evaluate_fastgate(
        _request(
            mode=FastGateMode.PERRON_COLLATZ_BOUND,
            positive_vector=_positive_vector(),
        )
    )

    _assert_result(evaluation, Verdict.ALLOW_BOUNDED_AUTONOMY, ReasonCode.ALLOW_BOUNDED_AUTONOMY)
    assert evaluation.fastgate.mode is FastGateMode.PERRON_COLLATZ_BOUND
    assert evaluation.fastgate.positive_vector_method is PositiveVectorMethod.IRREDUCIBLE_PERRON_VECTOR
    assert evaluation.fastgate.upper_bound == 0.30000000000000004


def test_warm_path_returns_uncertain_when_margin_is_insufficient_and_exact_unavailable() -> None:
    evaluation = evaluate_fastgate(
        _request(
            mode=FastGateMode.PERRON_COLLATZ_BOUND,
            delta_upper=_delta(0.59),
            positive_vector=_positive_vector(),
            tolerance_policy=TolerancePolicy(abs_tolerance=0.02, rel_tolerance=0.0),
            exact_recompute_available=False,
        )
    )

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_FASTGATE_UNCERTAIN)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_upper_bound_margin_insufficient"


def test_missing_positive_vector_returns_vector_invalid() -> None:
    evaluation = evaluate_fastgate(_request(mode=FastGateMode.PERRON_COLLATZ_BOUND))

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_FASTGATE_VECTOR_INVALID)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_positive_vector_missing"


def test_nonpositive_positive_vector_entry_returns_vector_invalid() -> None:
    vector = PositiveVector(
        values=(1.0, 0.0),
        node_order=("agent", "tool"),
        graph_hash=GRAPH_HASH,
        method=PositiveVectorMethod.IRREDUCIBLE_PERRON_VECTOR,
        irreducible_declared=True,
    )

    evaluation = evaluate_fastgate(_request(mode=FastGateMode.PERRON_COLLATZ_BOUND, positive_vector=vector))

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_FASTGATE_VECTOR_INVALID)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_positive_vector_entry_nonpositive"


def test_reducible_graph_without_declared_handling_returns_vector_invalid() -> None:
    evaluation = evaluate_fastgate(
        _request(
            mode=FastGateMode.PERRON_COLLATZ_BOUND,
            positive_vector=_positive_vector(),
            reducible_graph_declared=True,
        )
    )

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_FASTGATE_VECTOR_INVALID)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_reducible_graph_handling_missing"


def test_scc_decomposition_with_valid_closure_allows() -> None:
    evaluation = evaluate_fastgate(
        _request(
            mode=FastGateMode.PERRON_COLLATZ_BOUND,
            positive_vector=_positive_vector(PositiveVectorMethod.SCC_DECOMPOSITION),
            reducible_graph_declared=True,
        )
    )

    _assert_result(evaluation, Verdict.ALLOW_BOUNDED_AUTONOMY, ReasonCode.ALLOW_BOUNDED_AUTONOMY)
    assert evaluation.fastgate.positive_vector_method is PositiveVectorMethod.SCC_DECOMPOSITION


def test_epsilon_floor_with_insufficient_margin_returns_uncertain() -> None:
    vector = PositiveVector(
        values=(0.0, 1.0),
        node_order=("agent", "tool"),
        graph_hash=GRAPH_HASH,
        method=PositiveVectorMethod.EPSILON_FLOOR,
        epsilon=0.001,
    )

    evaluation = evaluate_fastgate(
        _request(
            mode=FastGateMode.PERRON_COLLATZ_BOUND,
            positive_vector=vector,
            exact_recompute_available=False,
        )
    )

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_FASTGATE_UNCERTAIN)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_upper_bound_margin_insufficient"


def test_component_local_gate_invalid_closure_returns_vector_invalid() -> None:
    vector = PositiveVector(
        values=(1.0, 1.0),
        node_order=("agent", "tool"),
        graph_hash=GRAPH_HASH,
        method=PositiveVectorMethod.COMPONENT_LOCAL_GATE,
        component_local_closure_valid=False,
    )

    evaluation = evaluate_fastgate(_request(mode=FastGateMode.PERRON_COLLATZ_BOUND, positive_vector=vector))

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_FASTGATE_VECTOR_INVALID)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_component_local_closure_invalid"


def test_stale_hot_path_cache_returns_context_stale() -> None:
    cache = FastGateCacheBinding(
        risk_model_version="arcana.risk.v0.2",
        calibration_profile_id="arcana.cal.fastgate_a1",
        decision_horizon_id="fastgate_5m",
        decision_horizon_duration_seconds=300,
        graph_hash=GRAPH_HASH,
        delta_hash=DELTA_HASH,
        threshold=0.8,
        positive_vector_method=PositiveVectorMethod.IRREDUCIBLE_PERRON_VECTOR,
        expires_at="2026-06-09T00:00:00Z",
    )

    evaluation = evaluate_fastgate(
        _request(
            mode=FastGateMode.PERRON_COLLATZ_BOUND,
            positive_vector=_positive_vector(),
            cache_binding=cache,
        )
    )

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_CONTEXT_STALE)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_cache_expired"


def test_graph_hash_mismatch_returns_graph_hash_reason() -> None:
    evaluation = evaluate_fastgate(_request(graph_hash=OTHER_GRAPH_HASH))

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_GRAPH_HASH_MISMATCH)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_before_matrix_graph_hash_mismatch"


def test_delta_horizon_mismatch_returns_horizon_reason() -> None:
    evaluation = evaluate_fastgate(_request(delta_upper=_delta(horizon=_horizon(seconds=600))))

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_DECISION_HORIZON_MISMATCH)
    assert evaluation.decision.metrics["issue_code"] == "sparse_delta_horizon_mismatch"


def test_malformed_sparse_delta_returns_model_input_invalid() -> None:
    evaluation = evaluate_fastgate(_request(delta_upper=_delta(-0.1)))

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_MODEL_INPUT_INVALID)
    assert evaluation.decision.metrics["issue_code"] == "number_invalid"


def test_budget_exhaustion_returns_budget_reason() -> None:
    evaluation = evaluate_fastgate(_request(autonomy_budget=_budget(max_delta=0.01)))

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_BUDGET_EXHAUSTED)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_budget_delta_rho_exceeded"


def test_a0_fastgate_artifact_is_observe_only() -> None:
    evaluation = evaluate_fastgate(
        _request(
            calibration_level=CalibrationLevel.A0,
            mode=FastGateMode.EXACT_RECOMPUTE,
        )
    )

    _assert_result(evaluation, Verdict.OBSERVE_ONLY, ReasonCode.REQUIRE_OBSERVE_ONLY)
    assert ReasonCode.INFO_A0_NON_CERTIFIABLE in evaluation.decision.reason_codes
    assert evaluation.fastgate.mode is FastGateMode.OBSERVE_ONLY


def test_fallback_exact_method_delegates_to_exact_recompute() -> None:
    vector = PositiveVector(
        values=(1.0, 1.0),
        node_order=("agent", "tool"),
        graph_hash=GRAPH_HASH,
        method=PositiveVectorMethod.FALLBACK_EXACT,
    )

    evaluation = evaluate_fastgate(_request(mode=FastGateMode.PERRON_COLLATZ_BOUND, positive_vector=vector))

    _assert_result(evaluation, Verdict.ALLOW_BOUNDED_AUTONOMY, ReasonCode.ALLOW_BOUNDED_AUTONOMY)
    assert evaluation.fastgate.mode is FastGateMode.EXACT_RECOMPUTE


def test_perron_fastgate_fields_validate_in_context_and_certificate() -> None:
    evaluation = evaluate_fastgate(
        _request(
            mode=FastGateMode.PERRON_COLLATZ_BOUND,
            positive_vector=_positive_vector(PositiveVectorMethod.SCC_DECOMPOSITION),
            reducible_graph_declared=True,
        )
    )
    assert evaluation.fastgate.upper_bound is not None
    loss_bounds = LossBounds(
        aar_99_upper=100.0,
        aes_99_upper=120.0,
        max_allowed_aar_99=200.0,
        max_allowed_aes_99=250.0,
    )
    evidence = EvidenceReference(
        source_type="synthetic_fixture",
        source_id="fastgate-unit-test",
        synthetic=True,
        evidence_hash="sha256:" + "9" * 64,
    )
    rho_interval = RhoInterval(
        lower=0.2,
        mean=0.25,
        upper=evaluation.fastgate.upper_bound,
        threshold=0.8,
    )
    context = RiskContext(
        risk_model_version="arcana.risk.v0.2",
        calibration_profile_id="arcana.cal.fastgate_a1",
        calibration_level=CalibrationLevel.A1,
        decision_horizon=_horizon(),
        graph_hash=GRAPH_HASH,
        rho_interval=rho_interval,
        decision=evaluation.decision.verdict,
        reason_codes=evaluation.decision.reason_codes,
        evidence=evidence,
        autonomy_budget=_budget(),
        loss_bounds=loss_bounds,
        fastgate=evaluation.fastgate,
    )
    certificate = BoundedAutonomyCertificate(
        certificate_id="arcana-cert-fastgate-a1-unit-test",
        certificate_type=CertificateType.BOUNDED_AUTONOMY_CERTIFICATE,
        risk_model_version="arcana.risk.v0.2",
        calibration_profile=CertificateCalibrationProfile(
            profile_id="arcana.cal.fastgate_a1",
            level=CalibrationLevel.A1,
            source=("static_conservative_prior",),
            confidence=0.7,
            certification_status=CertificationStatus.CERTIFIABLE_UNDER_PROFILE,
        ),
        decision_horizon=_horizon(),
        verdict=evaluation.decision.verdict,
        rho_interval=rho_interval,
        loss_bounds=loss_bounds,
        evidence=evidence,
        reason_codes=evaluation.decision.reason_codes,
        issued_at=DECISION_TIME,
        caveats=("synthetic FastGate schema validation only",),
        fastgate=evaluation.fastgate,
    )

    validate_document(risk_context_to_mapping(context), SchemaVersion.CONTEXT_V02)
    validate_document(certificate_to_mapping(certificate), SchemaVersion.CERTIFICATE_V02)
