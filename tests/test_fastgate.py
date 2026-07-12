from __future__ import annotations

import math

import numpy as np
import pytest

from arcana.certificate import (
    BoundedAutonomyCertificate,
    CertificateCalibrationProfile,
    CertificateType,
    certificate_to_mapping,
    risk_context_to_mapping,
)
from arcana.errors import ArcanaValidationError, CalibrationLevel, CertificationStatus, FastGateMode, PositiveVectorMethod, ReasonCode, SchemaVersion, Verdict
from arcana.fastgate import (
    FastGateCacheBinding,
    FastGateRequest,
    PositiveVector,
    SparseDeltaEntry,
    SparseMatrixDelta,
    _collatz_bound,
    compute_sparse_delta_hash,
    evaluate_fastgate,
)
from arcana.matrices import PropagationMatrix, TolerancePolicy
from arcana.model import AutonomyBudget, DecisionHorizon, EvidenceReference, LossBounds, RhoInterval, RiskContext
from arcana.schemas import validate_document


GRAPH_HASH = "sha256:" + "6" * 64
OTHER_GRAPH_HASH = "sha256:" + "7" * 64
EVIDENCE_HASH = "sha256:" + "a" * 64
DECISION_TIME = "2026-06-09T00:10:00Z"


def _horizon(seconds: int = 300) -> DecisionHorizon:
    return DecisionHorizon(id="fastgate_5m", duration_seconds=seconds, context="synthetic FastGate unit test")


def _budget(max_delta: float = 0.11) -> AutonomyBudget:
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


def _reducible_before_matrix(graph_hash: str = GRAPH_HASH) -> PropagationMatrix:
    return PropagationMatrix.from_values(
        [[0.0, 0.2], [0.0, 0.0]],
        node_order=("agent", "tool"),
        graph_hash=graph_hash,
    )


def _delta(value: float = 0.1, *, graph_hash: str = GRAPH_HASH, horizon: DecisionHorizon | None = None) -> SparseMatrixDelta:
    decision_horizon = horizon or _horizon()
    entries = (SparseDeltaEntry(row=0, column=1, value=value),)
    delta_hash = (
        compute_sparse_delta_hash(
            graph_hash=graph_hash,
            decision_horizon=decision_horizon,
            entries=entries,
        )
        if value >= 0
        else "sha256:" + "8" * 64
    )
    return SparseMatrixDelta(
        delta_hash=delta_hash,
        graph_hash=graph_hash,
        decision_horizon=decision_horizon,
        entries=entries,
    )


def _empty_delta(*, graph_hash: str = GRAPH_HASH, horizon: DecisionHorizon | None = None) -> SparseMatrixDelta:
    decision_horizon = horizon or _horizon()
    return SparseMatrixDelta(
        delta_hash=compute_sparse_delta_hash(
            graph_hash=graph_hash,
            decision_horizon=decision_horizon,
            entries=(),
        ),
        graph_hash=graph_hash,
        decision_horizon=decision_horizon,
        entries=(),
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
        evidence_hash=EVIDENCE_HASH,
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


def test_threshold_above_subcritical_limit_returns_model_input_invalid() -> None:
    evaluation = evaluate_fastgate(_request(threshold=1.01))

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_MODEL_INPUT_INVALID)
    assert evaluation.decision.metrics["issue_code"] == "number_out_of_range"


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
    assert evaluation.fastgate.upper_bound is not None
    assert evaluation.after_upper is not None
    assert evaluation.fastgate.upper_bound >= evaluation.after_upper.spectral_radius()


def test_warm_path_returns_uncertain_when_margin_is_insufficient_and_exact_unavailable() -> None:
    evaluation = evaluate_fastgate(
        _request(
            mode=FastGateMode.PERRON_COLLATZ_BOUND,
            delta_upper=_delta(0.59),
            positive_vector=_positive_vector(),
            tolerance_policy=TolerancePolicy(abs_tolerance=0.02, rel_tolerance=0.0),
            autonomy_budget=_budget(max_delta=10.0),
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


def test_irreducible_method_rejects_reducible_after_state_even_if_declared() -> None:
    evaluation = evaluate_fastgate(
        _request(
            mode=FastGateMode.PERRON_COLLATZ_BOUND,
            before_upper=_reducible_before_matrix(),
            delta_upper=_empty_delta(),
            positive_vector=_positive_vector(),
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
            autonomy_budget=_budget(max_delta=1000.0),
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
        delta_hash=_delta().delta_hash,
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


def test_hot_path_cache_tolerance_mismatch_returns_context_stale() -> None:
    cache = FastGateCacheBinding(
        risk_model_version="arcana.risk.v0.2",
        calibration_profile_id="arcana.cal.fastgate_a1",
        decision_horizon_id="fastgate_5m",
        decision_horizon_duration_seconds=300,
        graph_hash=GRAPH_HASH,
        delta_hash=_delta().delta_hash,
        threshold=0.8,
        positive_vector_method=PositiveVectorMethod.IRREDUCIBLE_PERRON_VECTOR,
        expires_at="2026-06-09T00:20:00Z",
        abs_tolerance=0.02,
        rel_tolerance=0.0,
        evidence_hash=EVIDENCE_HASH,
    )

    evaluation = evaluate_fastgate(
        _request(
            mode=FastGateMode.PERRON_COLLATZ_BOUND,
            positive_vector=_positive_vector(),
            cache_binding=cache,
            evidence_hash=EVIDENCE_HASH,
        )
    )

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_CONTEXT_STALE)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_cache_abs_tolerance_mismatch"


def test_hot_path_cache_requires_evidence_binding() -> None:
    cache = FastGateCacheBinding(
        risk_model_version="arcana.risk.v0.2",
        calibration_profile_id="arcana.cal.fastgate_a1",
        decision_horizon_id="fastgate_5m",
        decision_horizon_duration_seconds=300,
        graph_hash=GRAPH_HASH,
        delta_hash=_delta().delta_hash,
        threshold=0.8,
        positive_vector_method=PositiveVectorMethod.IRREDUCIBLE_PERRON_VECTOR,
        expires_at="2026-06-09T00:20:00Z",
    )

    evaluation = evaluate_fastgate(
        _request(
            mode=FastGateMode.PERRON_COLLATZ_BOUND,
            positive_vector=_positive_vector(),
            cache_binding=cache,
        )
    )

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_CONTEXT_STALE)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_cache_evidence_binding_missing"


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


def test_sparse_delta_hash_mismatch_returns_model_input_invalid() -> None:
    original = _delta(0.1)
    tampered = SparseMatrixDelta(
        delta_hash=original.delta_hash,
        graph_hash=original.graph_hash,
        decision_horizon=original.decision_horizon,
        entries=(SparseDeltaEntry(row=0, column=1, value=0.2),),
    )

    evaluation = evaluate_fastgate(_request(delta_upper=tampered))

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_MODEL_INPUT_INVALID)
    assert evaluation.decision.metrics["issue_code"] == "sparse_delta_hash_mismatch"


def test_sparse_delta_hash_is_independent_of_entry_order() -> None:
    entries_forward = (
        SparseDeltaEntry(row=0, column=1, value=0.1),
        SparseDeltaEntry(row=1, column=0, value=0.2),
    )
    entries_reverse = tuple(reversed(entries_forward))

    assert compute_sparse_delta_hash(
        graph_hash=GRAPH_HASH,
        decision_horizon=_horizon(),
        entries=entries_forward,
    ) == compute_sparse_delta_hash(
        graph_hash=GRAPH_HASH,
        decision_horizon=_horizon(),
        entries=entries_reverse,
    )


def test_sparse_delta_hash_binds_graph_horizon_and_additive_mode() -> None:
    entries = (SparseDeltaEntry(row=0, column=1, value=0.1),)
    baseline = compute_sparse_delta_hash(
        graph_hash=GRAPH_HASH,
        decision_horizon=_horizon(),
        entries=entries,
    )

    assert baseline != compute_sparse_delta_hash(
        graph_hash=OTHER_GRAPH_HASH,
        decision_horizon=_horizon(),
        entries=entries,
    )
    assert baseline != compute_sparse_delta_hash(
        graph_hash=GRAPH_HASH,
        decision_horizon=_horizon(seconds=600),
        entries=entries,
    )
    assert baseline != compute_sparse_delta_hash(
        graph_hash=GRAPH_HASH,
        decision_horizon=_horizon(),
        entries=entries,
        additive=False,
    )


def test_non_additive_delta_has_specific_rejection_even_with_valid_hash() -> None:
    entries = (SparseDeltaEntry(row=0, column=1, value=0.1),)
    delta = SparseMatrixDelta(
        delta_hash=compute_sparse_delta_hash(
            graph_hash=GRAPH_HASH,
            decision_horizon=_horizon(),
            entries=entries,
            additive=False,
        ),
        graph_hash=GRAPH_HASH,
        decision_horizon=_horizon(),
        entries=entries,
        additive=False,
    )

    evaluation = evaluate_fastgate(_request(delta_upper=delta))

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_MODEL_INPUT_INVALID)
    assert evaluation.decision.metrics["issue_code"] == "sparse_delta_not_additive"


def test_sparse_delta_hash_rejects_duplicate_entries() -> None:
    entry = SparseDeltaEntry(row=0, column=1, value=0.1)

    with pytest.raises(ArcanaValidationError) as exc_info:
        compute_sparse_delta_hash(
            graph_hash=GRAPH_HASH,
            decision_horizon=_horizon(),
            entries=(entry, entry),
        )

    assert exc_info.value.code == "sparse_delta_entry_duplicate"


def test_fastgate_admission_requires_evidence_hash_without_cache() -> None:
    evaluation = evaluate_fastgate(_request(evidence_hash=None))

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_evidence_hash_missing"


def test_fastgate_admission_does_not_accept_source_id_without_evidence_hash() -> None:
    evaluation = evaluate_fastgate(
        _request(evidence_hash=None, evidence_source_id="evidence-source-only")
    )

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_evidence_hash_missing"


def test_fastgate_observe_only_allows_missing_evidence_hash() -> None:
    evaluation = evaluate_fastgate(
        _request(mode=FastGateMode.OBSERVE_ONLY, evidence_hash=None)
    )

    _assert_result(evaluation, Verdict.OBSERVE_ONLY, ReasonCode.REQUIRE_OBSERVE_ONLY)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_observe_only"


def test_collatz_bound_is_conservative_across_deterministic_numerical_cases() -> None:
    rng = np.random.default_rng(20260712)
    minimum_gap = math.inf

    for size in range(1, 7):
        for _ in range(64):
            values = rng.lognormal(mean=-4.0, sigma=3.0, size=(size, size))
            vector_values = rng.lognormal(mean=0.0, sigma=3.0, size=size)
            matrix = PropagationMatrix.from_values(values)
            vector = PositiveVector(
                values=tuple(float(value) for value in vector_values),
                node_order=tuple(f"node-{index}" for index in range(size)),
                graph_hash=GRAPH_HASH,
                method=PositiveVectorMethod.IRREDUCIBLE_PERRON_VECTOR,
                irreducible_declared=True,
            )

            bound = _collatz_bound(matrix, vector)
            radius = matrix.spectral_radius()
            minimum_gap = min(minimum_gap, bound - radius)
            assert bound >= radius

    assert minimum_gap >= 0


def test_budget_exhaustion_returns_budget_reason() -> None:
    evaluation = evaluate_fastgate(_request(autonomy_budget=_budget(max_delta=0.01)))

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_BUDGET_EXHAUSTED)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_budget_delta_rho_exceeded"


def test_budget_delta_exhaustion_precedes_fastgate_uncertain() -> None:
    evaluation = evaluate_fastgate(
        _request(
            mode=FastGateMode.PERRON_COLLATZ_BOUND,
            delta_upper=_delta(0.59),
            positive_vector=_positive_vector(),
            tolerance_policy=TolerancePolicy(abs_tolerance=0.02, rel_tolerance=0.0),
            autonomy_budget=_budget(max_delta=0.01),
            exact_recompute_available=False,
        )
    )

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_BUDGET_EXHAUSTED)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_budget_delta_rho_exceeded"


def test_empty_budget_returns_budget_reason() -> None:
    evaluation = evaluate_fastgate(
        _request(
            autonomy_budget=AutonomyBudget(expires_at="2026-06-09T00:30:00Z"),
        )
    )

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_BUDGET_EXHAUSTED)
    assert evaluation.decision.metrics["issue_code"] == "fastgate_budget_empty"


def test_loss_model_failure_precedes_fastgate_uncertain() -> None:
    evaluation = evaluate_fastgate(
        _request(
            mode=FastGateMode.PERRON_COLLATZ_BOUND,
            delta_upper=_delta(0.59),
            positive_vector=_positive_vector(),
            tolerance_policy=TolerancePolicy(abs_tolerance=0.02, rel_tolerance=0.0),
            exact_recompute_available=False,
            loss_in_scope=True,
            loss_bounds=None,
        )
    )

    _assert_result(evaluation, Verdict.DENY, ReasonCode.DENY_LOSS_MODEL_INVALID)
    assert evaluation.decision.metrics["issue_code"] == "loss_bounds_missing"


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
        certificate_id="arcana-cert-fastgate-a2-unit-test",
        certificate_type=CertificateType.BOUNDED_AUTONOMY_CERTIFICATE,
        risk_model_version="arcana.risk.v0.2",
        calibration_profile=CertificateCalibrationProfile(
            profile_id="arcana.cal.fastgate_a2",
            level=CalibrationLevel.A2,
            source=("controlled_redteam",),
            confidence=0.8,
            certification_status=CertificationStatus.CERTIFIABLE_UNDER_PROFILE,
        ),
        decision_horizon=_horizon(),
        graph_hash=GRAPH_HASH,
        verdict=evaluation.decision.verdict,
        rho_interval=rho_interval,
        loss_bounds=loss_bounds,
        evidence=EvidenceReference(
            source_type="controlled_test",
            source_id="fastgate-unit-controlled-test",
            synthetic=False,
            evidence_hash="sha256:" + "a" * 64,
        ),
        reason_codes=evaluation.decision.reason_codes,
        issued_at=DECISION_TIME,
        caveats=("controlled-test unit validation only; no commercial certificate issuance",),
        fastgate=evaluation.fastgate,
    )

    validate_document(risk_context_to_mapping(context), SchemaVersion.CONTEXT_V02)
    validate_document(certificate_to_mapping(certificate), SchemaVersion.CERTIFICATE_V02)


def test_a1_non_demo_certificate_is_rejected() -> None:
    certificate = BoundedAutonomyCertificate(
        certificate_id="arcana-cert-fastgate-a1-rejected-unit-test",
        certificate_type=CertificateType.BOUNDED_AUTONOMY_CERTIFICATE,
        risk_model_version="arcana.risk.v0.2",
        calibration_profile=CertificateCalibrationProfile(
            profile_id="arcana.cal.fastgate_a1",
            level=CalibrationLevel.A1,
            source=("static_conservative_prior",),
            confidence=0.7,
            certification_status=CertificationStatus.NON_CERTIFIABLE,
        ),
        decision_horizon=_horizon(),
        graph_hash=GRAPH_HASH,
        verdict=Verdict.ALLOW_BOUNDED_AUTONOMY,
        rho_interval=RhoInterval(lower=0.2, mean=0.25, upper=0.3, threshold=0.8),
        loss_bounds=LossBounds(
            aar_99_upper=100.0,
            aes_99_upper=120.0,
            max_allowed_aar_99=200.0,
            max_allowed_aes_99=250.0,
        ),
        evidence=EvidenceReference(
            source_type="controlled_test",
            source_id="fastgate-unit-controlled-test",
            synthetic=False,
            evidence_hash="sha256:" + "b" * 64,
        ),
        reason_codes=(ReasonCode.ALLOW_BOUNDED_AUTONOMY,),
        issued_at=DECISION_TIME,
        caveats=("A1 non-demo certificate rejection unit test",),
    )

    from arcana.errors import ArcanaValidationError

    try:
        certificate_to_mapping(certificate)
    except ArcanaValidationError as exc:
        assert exc.reason_code is ReasonCode.DENY_CALIBRATION_INSUFFICIENT
        assert exc.code == "certificate_calibration_level_insufficient"
    else:  # pragma: no cover
        raise AssertionError("A1 non-demo certificate should be rejected")
