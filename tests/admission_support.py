"""Test helpers for the arcana.admission.v1 contract policy."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from arcana.admission import changed_sources
from arcana.calibration import CalibrationProfile, CalibrationUncertainty, EdgeWeightPolicy, EvidenceWindow
from arcana.decision import DecisionEvaluationRequest
from arcana.errors import CalibrationLevel, CertificationStatus, IncrementScope, LossMethod, LossSource, TemporalMode, Verdict
from arcana.fastgate import FastGateRequest, evaluate_fastgate
from arcana.increments import IncrementContract, IncrementSnapshot
from arcana.loss_contract import LossContract
from arcana.model import DecisionResult, LossBounds, LossPolicy, TemporalPolicy
from arcana.temporal import TemporalContract

CONTRACT_GAPS = frozenset({"calibration_profile_missing", "calibration_evidence_hash_missing", "loss_contract_missing",
                           "increment_contract_missing", "temporal_contract_missing"})
PROFILE_EVIDENCE_HASH = "sha256:" + "c" * 64
_SOURCES = {
    CalibrationLevel.A1: ("static_conservative_prior",),
    CalibrationLevel.A2: ("controlled_redteam",),
    CalibrationLevel.A3: ("runtime_observation",),
}


def assert_contract_gated(decision: DecisionResult, gaps=CONTRACT_GAPS) -> None:
    """Every risk check passed, but admission is withheld only for missing contracts."""
    assert decision.verdict is Verdict.OBSERVE_ONLY, decision
    assert decision.metrics["issue_code"] == "admission_contracts_missing"
    assert decision.metrics["admission_contract_gaps"]
    assert set(decision.metrics["admission_contract_gaps"]) <= set(gaps)


def complete_admission(request):
    """Add coherent increment, temporal and profile inputs (incl. profile evidence hash) that the request lacks."""
    if isinstance(request, DecisionEvaluationRequest):
        before = after = request.matrix_bundle.upper
        profile_id = request.calibration_profile.profile_id
        evidence = {}
    else:
        assert isinstance(request, FastGateRequest)
        after = evaluate_fastgate(request).after_upper
        assert after is not None, "the base request must reach the matrix update"
        before = request.before_upper
        profile_id = request.calibration_profile_id
        evidence = {"evidence_hash": request.evidence_hash, "evidence_source_id": request.evidence_source_id or "synthetic-admission"}
    instant = datetime.fromisoformat(request.decision_time.replace("Z", "+00:00"))
    horizon = request.decision_horizon
    valid_from = _iso(instant - timedelta(hours=1))
    expires_at = _iso(instant + timedelta(seconds=horizon.duration_seconds, hours=1))
    budget = request.autonomy_budget
    changes = {}
    if request.increment is None:
        changes["increment"] = IncrementContract(
            scope=IncrementScope.UPPER_MODEL, risk_model_version=request.risk_model_version,
            calibration_profile_id=profile_id, decision_horizon=horizon,
            before=IncrementSnapshot(before), after=IncrementSnapshot(after),
            evidence_hash=evidence.get("evidence_hash") or "sha256:" + "a" * 64,
            evidence_source_id=evidence.get("evidence_source_id", "synthetic-admission"),
            evidence_scope="represented_snapshot_pair", valid_from=valid_from, expires_at=expires_at,
        )
        budget = replace(budget, increment_scope=IncrementScope.UPPER_MODEL,
                         max_delta_rho_upper=1e6 if budget.max_delta_rho_upper is None else budget.max_delta_rho_upper)
        if isinstance(request, DecisionEvaluationRequest):
            changes["delta_rho_upper"] = None  # scoped budgets recompute it from the bound snapshots
    if request.temporal is None:
        increment = changes.get("increment", request.increment)
        sources = set(changed_sources(increment)) if increment is not None else set()
        seed = tuple(1.0 if index in (sources or {0}) else 0.0 for index in range(after.size))
        changes["temporal"] = TemporalContract(
            mode=TemporalMode.FIXED_OPERATOR, risk_model_version=request.risk_model_version,
            calibration_profile_id=profile_id, decision_horizon=horizon, generations=1,
            operators=(after,), envelope_upper=after, initial_upper=seed,
            operator_semantics="per_generation_expected_offspring", state_units="expected_unsafe_activations",
            exogenous_input="none_after_initial",
            evidence_hash=evidence.get("evidence_hash") or "sha256:" + "a" * 64,
            evidence_source_id=evidence.get("evidence_source_id", "synthetic-admission"),
            evidence_scope="joint_generation_envelope", valid_from=valid_from, expires_at=expires_at,
        )
        budget = replace(budget, temporal_policy=TemporalPolicy(TemporalMode.FIXED_OPERATOR, 1, 1e6, 1e6))
    if request.loss_in_scope and request.loss is None and isinstance(request.loss_bounds, LossBounds) and budget.loss_policy is None:
        bounds = request.loss_bounds
        changes["loss"] = LossContract(
            risk_model_version=request.risk_model_version, calibration_profile_id=profile_id, decision_horizon=horizon,
            unit="synthetic_loss_units", method=LossMethod.DECLARED_UPPER_BOUNDS, failure_probability_upper=0.01,
            evidence_hash="sha256:" + "d" * 64, evidence_source_id="synthetic-admission", source_kind=LossSource.SYNTHETIC_FIXTURE,
            valid_from=valid_from, expires_at=expires_at, aar_99_upper=bounds.aar_99_upper, aes_99_upper=bounds.aes_99_upper,
        )
        budget = replace(budget, loss_policy=LossPolicy("synthetic_loss_units", bounds.max_allowed_aar_99,
                                                        bounds.max_allowed_aes_99, 0.05, False))
        changes["loss_bounds"] = None
    if isinstance(request.calibration_profile, CalibrationProfile) and request.calibration_profile.evidence_hash is None:
        changes["calibration_profile"] = replace(request.calibration_profile, evidence_hash=PROFILE_EVIDENCE_HASH)
    if isinstance(request, FastGateRequest) and request.calibration_profile is None:
        level = request.calibration_level
        changes["calibration_profile"] = CalibrationProfile(
            profile_id=profile_id, risk_model_version=request.risk_model_version, level=level,
            decision_horizon=horizon, source=_SOURCES[level],
            evidence_window=EvidenceWindow(_iso(instant - timedelta(minutes=10)), _iso(instant - timedelta(minutes=1)), 3600),
            # Declared rho interval [0, 1] is coherent with every subcritical after-state.
            confidence=.8, uncertainty=CalibrationUncertainty(0, .1, 1), edge_weight_policy=EdgeWeightPolicy(True, True, True),
            caveats=("synthetic admission test profile",),
            certification_status=CertificationStatus.NON_CERTIFIABLE if level is CalibrationLevel.A1
            else CertificationStatus.CERTIFIABLE_UNDER_PROFILE, evidence_hash=PROFILE_EVIDENCE_HASH,
        )
    return replace(request, autonomy_budget=budget, **changes)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
