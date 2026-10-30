"""arcana.admission.v1: allow-like verdicts need bound increment and temporal contracts."""

from dataclasses import replace

import pytest

from admission_support import CONTRACT_GAPS, assert_contract_gated, complete_admission
import test_decision_reason_codes as main_api
import test_fastgate as fastgate_api
from arcana.admission import ADMISSION_CONTRACT_POLICY
from arcana.calibration import CalibrationUncertainty
from arcana.decision import evaluate_decision
from arcana.errors import CalibrationLevel, ReasonCode, TemporalMode, Verdict
from arcana.fastgate import evaluate_fastgate
from arcana.matrices import MatrixBundle
from arcana.model import TemporalPolicy


def _main(**overrides):
    return main_api._request(**overrides)


def _fastgate(**overrides):
    return fastgate_api._request(**overrides)


def _dag(weight: float) -> MatrixBundle:
    values = [[0.0, weight, 0.0], [0.0, 0.0, weight], [0.0, 0.0, 0.0]]
    return MatrixBundle.from_values(values, values, values, node_order=("agent", "tool", "external"),
                                    graph_hash=main_api.GRAPH_HASH)


LEGACY_GAPS = {"calibration_evidence_hash_missing", "increment_contract_missing", "temporal_contract_missing"}


def _with_rho_interval(request, lower: float, upper: float):
    """Declare a profile rho interval coherent with the operator under test (F6)."""
    profile = replace(request.calibration_profile, uncertainty=CalibrationUncertainty(lower, lower, upper))
    return replace(request, calibration_profile=profile)


def _tight_temporal(request, cumulative: float = 10.0):
    policy = TemporalPolicy(TemporalMode.FIXED_OPERATOR, request.temporal.generations, 1e12, cumulative)
    return replace(request, autonomy_budget=replace(request.autonomy_budget, temporal_policy=policy))


def test_legacy_request_that_passes_every_check_is_observe_only() -> None:
    result = evaluate_decision(_main())
    assert_contract_gated(result, LEGACY_GAPS)
    assert result.reason_codes == (ReasonCode.REQUIRE_OBSERVE_ONLY,)
    assert result.metrics["admission_contract_policy"] == ADMISSION_CONTRACT_POLICY
    assert result.metrics["rho_upper"] < result.metrics["rho_threshold"]


def test_complete_contracts_restore_admission_and_record_policy() -> None:
    result = evaluate_decision(complete_admission(_main()))
    assert result.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY
    assert result.metrics["admission_contract_gaps"] == ()
    assert result.metrics["admission_contract_policy"] == ADMISSION_CONTRACT_POLICY


@pytest.mark.parametrize("missing", ["increment", "temporal"])
def test_each_contract_is_required(missing: str) -> None:
    request = complete_admission(_main())
    budget = {"increment": {"increment_scope": None}, "temporal": {"temporal_policy": None}}[missing]
    request = replace(request, **{missing: None}, autonomy_budget=replace(request.autonomy_budget, **budget))
    if missing == "increment":
        request = replace(request, delta_rho_upper=0.0)
    assert_contract_gated(evaluate_decision(request), {f"{missing}_contract_missing"})


def test_audit_f5_caller_declared_increment_cannot_reach_admission() -> None:
    bundle = MatrixBundle.from_values([[0, .79], [.79, 0]], [[0, .79], [.79, 0]], [[0, .79], [.79, 0]],
                                      node_order=("agent", "tool"), graph_hash=main_api.GRAPH_HASH)
    result = evaluate_decision(_with_rho_interval(_main(matrix_bundle=bundle, delta_rho_upper=0.0), 0, .8))
    assert_contract_gated(result, LEGACY_GAPS)


def test_audit_f2_acyclic_high_weight_action_is_not_admitted() -> None:
    legacy = evaluate_decision(_with_rho_interval(_main(matrix_bundle=_dag(1e6)), 0, .3))
    assert legacy.metrics["rho_upper"] == 0.0
    assert_contract_gated(legacy, LEGACY_GAPS)
    bound = _tight_temporal(complete_admission(_main(matrix_bundle=_dag(1e6))))
    denied = evaluate_decision(bound)
    assert denied.verdict is Verdict.DENY
    assert denied.metrics["issue_code"] == "temporal_cumulative_budget_exceeded"
    assert denied.metrics["temporal_cumulative_activations_upper"] > 1e6


@pytest.mark.parametrize("values,seed", [([[0, 50.0], [0, 0]], (1.0, 0.0)), ([[0, 0], [50.0, 0]], (0.0, 1.0))])
def test_audit_f3_each_half_of_a_split_cycle_is_charged_for_its_cascade(values, seed) -> None:
    bundle = MatrixBundle.from_values(values, values, values, node_order=("agent", "tool"), graph_hash=main_api.GRAPH_HASH)
    request = complete_admission(_main(matrix_bundle=bundle))
    request = _tight_temporal(replace(request, temporal=replace(request.temporal, initial_upper=seed)))
    result = evaluate_decision(request)
    assert result.metrics["rho_upper"] == 0.0
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == "temporal_cumulative_budget_exceeded"


def test_zero_initial_state_cannot_vacuously_satisfy_the_temporal_contract() -> None:
    request = complete_admission(_main())
    request = replace(request, temporal=replace(request.temporal, initial_upper=(0.0, 0.0)))
    result = evaluate_decision(request)
    assert_contract_gated(result, {"temporal_initial_state_zero"})


def test_require_verdicts_still_precede_contract_gating() -> None:
    assert evaluate_decision(_main(human_gate_required=True)).verdict is Verdict.REQUIRE_HUMAN_GATE
    assert evaluate_decision(_main(scope_reduction_required=True)).verdict is Verdict.REQUIRE_SCOPE_REDUCTION


def test_audit_f4_fastgate_rejects_unsupported_risk_model_version() -> None:
    request = complete_admission(_fastgate())
    result = evaluate_fastgate(replace(request, risk_model_version="arcana.risk.v9.9")).decision
    assert result.verdict is Verdict.DENY
    assert result.reason_codes == (ReasonCode.DENY_RISK_MODEL_UNSUPPORTED,)
    assert result.metrics["issue_code"] == "fastgate_risk_model_version_unsupported"


def test_audit_f4_self_declared_level_without_profile_is_not_admission() -> None:
    request = complete_admission(_fastgate())
    request = replace(request, calibration_profile=None, calibration_level=CalibrationLevel.A3,
                      required_calibration_level=CalibrationLevel.A3)
    evaluation = evaluate_fastgate(request)
    assert not evaluation.allowed
    assert_contract_gated(evaluation.decision, {"calibration_profile_missing"})


@pytest.mark.parametrize("field,value,issue", [
    ("calibration_level", CalibrationLevel.A3, "fastgate_calibration_level_mismatch"),
    ("calibration_profile_id", "arcana.cal.other_profile", "fastgate_calibration_profile_id_mismatch"),
])
def test_fastgate_profile_must_match_the_declared_identity(field: str, value: object, issue: str) -> None:
    request = complete_admission(_fastgate())
    result = evaluate_fastgate(replace(request, **{field: value})).decision
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == issue


def test_fastgate_applies_the_main_evaluator_profile_freshness_rule() -> None:
    request = complete_admission(_fastgate())
    window = replace(request.calibration_profile.evidence_window, max_age_seconds=1)
    stale = replace(request, calibration_profile=replace(request.calibration_profile, evidence_window=window))
    result = evaluate_fastgate(stale).decision
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == "calibration_evidence_stale"


@pytest.mark.parametrize("overrides,verdict", [
    ({"human_gate_required": True}, Verdict.REQUIRE_HUMAN_GATE),
    ({"scope_reduction_required": True}, Verdict.REQUIRE_SCOPE_REDUCTION),
    ({"required_controls": ("read_only_input",)}, Verdict.REQUIRE_HUMAN_GATE),
    ({"required_controls": ("read_only_input",), "available_controls": ("read_only_input",)}, Verdict.ALLOW_WITH_CONTROLS),
    ({}, Verdict.ALLOW_BOUNDED_AUTONOMY),
])
def test_fastgate_shares_the_main_evaluator_decision_tail(overrides: dict, verdict: Verdict) -> None:
    for request in (complete_admission(_main(**overrides)), complete_admission(_fastgate(**overrides))):
        decision = evaluate_decision(request) if hasattr(request, "matrix_bundle") else evaluate_fastgate(request).decision
        assert decision.verdict is verdict


def test_contract_gap_names_are_stable() -> None:
    assert CONTRACT_GAPS == {"calibration_profile_missing", "calibration_evidence_hash_missing",
                             "increment_contract_missing", "temporal_contract_missing"}


def test_seed_on_an_unrelated_node_does_not_charge_the_changed_edge() -> None:
    request = complete_admission(fastgate_api._request())
    source = fastgate_api._delta().entries[0].row
    misplaced = tuple(0.0 if index == source else 1.0 for index in range(request.before_upper.size))
    evaluation = evaluate_fastgate(replace(request, temporal=replace(request.temporal, initial_upper=misplaced)))
    assert not evaluation.allowed
    assert_contract_gated(evaluation.decision, {"temporal_seed_misses_changed_source"})


def test_increment_evidence_must_cover_the_whole_decision_horizon() -> None:
    request = complete_admission(_main())
    short = replace(request.increment, expires_at="2026-06-09T00:10:01Z")
    result = evaluate_decision(replace(request, increment=short))
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == "increment_evidence_horizon_not_covered"
