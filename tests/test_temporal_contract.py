"""Exact recurrence oracles and adversarial temporal admission contracts."""

from dataclasses import replace
from datetime import datetime
from fractions import Fraction
from itertools import product
import json
import math
import random

import numpy as np
import pytest

from arcana.artifacts import validate_risk_context_semantics
from arcana.calibration import CalibrationProfile, CalibrationUncertainty, EdgeWeightPolicy, EvidenceWindow
from arcana.certificate import build_demo_non_certifiable_certificate, risk_context_to_mapping
from arcana.decision import DecisionEvaluationRequest, evaluate_decision
from arcana.demo import build_demo_artifacts
from arcana.errors import ArcanaValidationError, CalibrationLevel, CertificationStatus, FastGateMode, PositiveVectorMethod, TemporalMode, Verdict
from arcana.fastgate import FastGateCacheBinding, FastGateRequest, PositiveVector, SparseMatrixDelta, compute_sparse_delta_hash, evaluate_fastgate
from arcana.increments import IncrementContract, IncrementSnapshot
from arcana.errors import IncrementScope
from arcana.matrices import MatrixBundle, PropagationMatrix, TolerancePolicy, spectral_bounds
from arcana.model import AutonomyBudget, DecisionHorizon, TemporalPolicy
from arcana.schemas import EXAMPLE_DIR, load_typed_fixture, parse_typed_document, validate_document
from arcana.temporal import TemporalContract, evaluate_temporal, temporal_policy_hash, validate_temporal_binding
from admission_support import assert_contract_gated, complete_admission


GRAPH = "sha256:" + "3" * 64
EVIDENCE = "sha256:" + "4" * 64
NOW = "2026-09-11T10:00:00Z"
EXPIRES = "2026-09-11T11:00:00Z"
HORIZON = DecisionHorizon("temporal_synthetic", 300, "synthetic causal generations")


def _matrix(values, graph=GRAPH, order=None):
    return PropagationMatrix(values, tuple(str(i) for i in range(len(values))) if order is None else order, graph)


def _contract(values=None, *, generations=3, seed=None):
    if values is None:
        operators = (_matrix([[0, .5], [0, 0]]), _matrix([[0, 0], [.25, 0]]))
        envelope = _matrix([[0, .5], [.25, 0]])
        mode = TemporalMode.COMMON_ENVELOPE
    else:
        envelope = _matrix(values)
        operators = (envelope,)
        mode = TemporalMode.FIXED_OPERATOR
    return TemporalContract(
        mode=mode, risk_model_version="arcana.risk.v0.2", calibration_profile_id="arcana.cal.temporal_a1",
        decision_horizon=HORIZON, generations=generations, operators=operators, envelope_upper=envelope,
        initial_upper=tuple(seed) if seed is not None else (1.,) + (0.,) * (envelope.size - 1),
        operator_semantics="per_generation_expected_offspring", state_units="expected_unsafe_activations",
        exogenous_input="none_after_initial", evidence_hash=EVIDENCE, evidence_source_id="synthetic-temporal-oracle",
        evidence_scope="joint_generation_envelope", valid_from="2026-09-11T09:00:00Z", expires_at=EXPIRES,
    )


def _policy(contract, peak=10., cumulative=20.):
    return TemporalPolicy(contract.mode, contract.generations, peak, cumulative)


def _evaluate(contract, policy=None, **overrides):
    return evaluate_temporal(contract, _policy(contract) if policy is None else policy,
                             **{"decision_time": NOW, "rho_threshold": .9, **overrides})


def _profile(contract):
    return CalibrationProfile(
        profile_id=contract.calibration_profile_id, risk_model_version=contract.risk_model_version,
        level=CalibrationLevel.A1, decision_horizon=contract.decision_horizon, source=("static_conservative_prior",),
        evidence_window=EvidenceWindow("2026-09-11T09:00:00Z", "2026-09-11T09:59:00Z", 3600),
        confidence=.8, uncertainty=CalibrationUncertainty(0, .2, .8), edge_weight_policy=EdgeWeightPolicy(True, True, True),
        caveats=("synthetic generation contract, no empirical coverage",),
        certification_status=CertificationStatus.NON_CERTIFIABLE, last_updated_at="2026-09-11T09:59:00Z",
        evidence_hash=EVIDENCE,
    )


def _request(api, contract):
    current = contract.operators[0]
    budget = AutonomyBudget(EXPIRES, temporal_policy=_policy(contract))
    if api == "main":
        return DecisionEvaluationRequest(contract.risk_model_version, _profile(contract), HORIZON, current.graph_hash,
                                         MatrixBundle(current, current, current), .9, budget, NOW, temporal=contract)
    mode = {"exact": FastGateMode.EXACT_RECOMPUTE, "collatz": FastGateMode.PERRON_COLLATZ_BOUND}[api]
    delta = SparseMatrixDelta(compute_sparse_delta_hash(graph_hash=current.graph_hash, decision_horizon=HORIZON, entries=()),
                              current.graph_hash, HORIZON, ())
    return FastGateRequest(mode, contract.risk_model_version, contract.calibration_profile_id, CalibrationLevel.A1,
                           CalibrationLevel.A1, HORIZON, NOW, current.graph_hash, current, delta, .9, budget,
                           positive_vector=PositiveVector((1.,) * current.size, current.node_order, current.graph_hash,
                                                          PositiveVectorMethod.EPSILON_FLOOR, epsilon=.01),
                           evidence_hash=EVIDENCE, evidence_source_id=contract.evidence_source_id, temporal=contract)


def _decision(request):
    return evaluate_decision(request) if isinstance(request, DecisionEvaluationRequest) else evaluate_fastgate(request).decision


def _step(matrix, state):
    return tuple(sum((Fraction(matrix[i][j]) * state[i] for i in range(len(state))), Fraction(0)) for j in range(len(state)))


def test_asymmetric_source_row_orientation_and_generation_zero():
    contract = _contract([[0, 2, 0], [0, 0, 3], [0, 0, 0]])
    result = _evaluate(contract)
    assert result.passed
    assert result.metrics["temporal_generation_states_upper"] == [(1., 0., 0.), (0., 2., 0.), (0., 0., 6.), (0., 0., 0.)]
    assert result.metrics["temporal_generation_totals_upper"] == [1, 2, 6, 0]
    assert result.metrics["temporal_peak_activations_upper"] == 6
    assert result.metrics["temporal_cumulative_activations_upper"] == 9


def test_public_example_is_exactly_the_synthetic_oracle_contract():
    fixture = load_typed_fixture(EXAMPLE_DIR / "temporal_common_envelope.synthetic.json")
    assert isinstance(fixture, TemporalContract)
    assert fixture.to_mapping() == _contract().to_mapping()


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
@pytest.mark.parametrize("peak,cumulative,code", [(3, 100, "temporal_peak_budget_exceeded"), (100, 8, "temporal_cumulative_budget_exceeded")])
def test_c03_nilpotent_transient_is_not_safe_from_radius_alone(api, peak, cumulative, code):
    contract = _contract([[0, 2, 0], [0, 0, 3], [0, 0, 0]])
    assert spectral_bounds(contract.envelope_upper).upper == 0
    request = _request(api, contract)
    result = _decision(replace(request, autonomy_budget=replace(request.autonomy_budget, temporal_policy=_policy(contract, peak, cumulative))))
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == code
    assert result.metrics["temporal_peak_activations_upper"] == 6


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
def test_c03_switching_nilpotent_operators_reject_supercritical_envelope(api):
    contract = _contract()
    contract = replace(contract, operators=(_matrix([[0, 2], [0, 0]]), _matrix([[0, 0], [2, 0]])),
                       envelope_upper=_matrix([[0, 2], [2, 0]]))
    assert all(spectral_bounds(op).upper == 0 for op in contract.operators)
    assert _step(contract.operators[1].values, _step(contract.operators[0].values, (Fraction(1), Fraction(0)))) == (4, 0)
    result = _decision(_request(api, contract))
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == "temporal_envelope_not_subcritical"
    assert result.metrics["temporal_envelope_rho_upper"] >= 2


def test_subcritical_envelope_bounds_all_short_switching_words():
    contract = replace(_contract(generations=6), initial_upper=(1., 1.))
    result = _evaluate(contract)
    assert result.passed
    bounds = result.metrics["temporal_generation_states_upper"]
    for length in range(1, 7):
        for word in product(contract.operators, repeat=length):
            state = (Fraction(1), Fraction(1))
            cumulative = sum(state)
            for index, operator in enumerate(word, 1):
                state = _step(operator.values, state)
                cumulative += sum(state)
                assert all(x <= Fraction(bound) for x, bound in zip(state, bounds[index], strict=True))
            assert cumulative <= Fraction(result.metrics["temporal_cumulative_activations_upper"])


@pytest.mark.parametrize("seed", range(12))
def test_independent_fraction_oracle_for_dyadic_operators(seed):
    rng = random.Random(seed)
    values = [[rng.randrange(0, 5) / 32 for _ in range(3)] for _ in range(3)]
    initial = [rng.randrange(0, 5) / 8 for _ in range(3)]
    contract = _contract(values, seed=initial, generations=8)
    result = _evaluate(contract)
    assert result.passed
    state = tuple(Fraction(x) for x in initial)
    cumulative = Fraction(0)
    peak = Fraction(0)
    for index, bound in enumerate(result.metrics["temporal_generation_states_upper"]):
        if index:
            state = _step(values, state)
        assert all(Fraction(b) >= x for x, b in zip(state, bound, strict=True))
        cumulative += sum(state)
        peak = max(peak, sum(state))
    assert Fraction(result.metrics["temporal_peak_activations_upper"]) >= peak
    assert Fraction(result.metrics["temporal_cumulative_activations_upper"]) >= cumulative


def test_zero_seed_is_zero_only_under_explicit_no_arrivals_contract():
    result = _evaluate(_contract(seed=(0, 0)))
    assert result.passed
    assert result.metrics["temporal_peak_activations_upper"] == result.metrics["temporal_cumulative_activations_upper"] == 0
    with pytest.raises(ArcanaValidationError) as error:
        replace(_contract(seed=(0, 0)), exogenous_input="unbounded")
    assert error.value.code == "temporal_exogenous_input_unsupported"


def test_initial_state_is_budgeted_and_equality_passes():
    contract = _contract([[0]], seed=(2,))
    assert _evaluate(contract, _policy(contract, 2, 2)).passed
    assert _evaluate(contract, _policy(contract, math.nextafter(2, 0), 2)).issue_code == "temporal_peak_budget_exceeded"
    assert _evaluate(contract, _policy(contract, 2, math.nextafter(2, 0))).issue_code == "temporal_cumulative_budget_exceeded"


def test_subnormal_propagation_is_not_rounded_to_zero():
    contract = _contract([[2**-1074]], seed=(.5,), generations=2)
    result = _evaluate(contract)
    assert result.passed
    assert result.metrics["temporal_generation_states_upper"][1][0] == 2**-1074
    assert Fraction(result.metrics["temporal_cumulative_activations_upper"]) >= Fraction(1, 2) + Fraction(1, 2**1075)


@pytest.mark.parametrize("contract,code", [
    (_contract([[0, 2**600, 0], [0, 0, 2**600], [0, 0, 0]]), "temporal_state_bound_unrepresentable"),
    (_contract([[0, 0], [0, 0]], seed=(2**1023, 2**1023)), "temporal_total_bound_unrepresentable"),
    (_contract([[.5]], seed=(float.fromhex("0x1.fffffffffffffp+1023"),)), "temporal_cumulative_bound_unrepresentable"),
])
def test_nonrepresentable_bounds_are_specific_failures(contract, code):
    result = _evaluate(contract)
    assert not result.passed
    assert result.issue_code == code


def test_supercritical_finite_recurrence_is_policy_denied_not_called_infinite():
    contract = _contract([[1.25]])
    assert sum(Fraction(5, 4)**g for g in range(4)) == Fraction(369, 64)
    result = _evaluate(contract)
    assert result.issue_code == "temporal_envelope_not_subcritical"


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
def test_supported_temporal_request_passes_without_legacy_counter_requirement(api):
    contract = _contract()
    result = _decision(complete_admission(_request(api, contract)))
    assert result.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY
    assert result.metrics["temporal_binding_hash"] == contract.binding_hash
    assert result.metrics["temporal_cumulative_activations_upper"] == 1.6875
    assert result.metrics["temporal_evidence_assurance"] == "declared_premises_not_empirically_verified"


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
@pytest.mark.parametrize("field,value,code", [
    ("temporal", None, "temporal_contract_missing"),
    ("temporal", {}, "temporal_contract_invalid"),
    ("policy", None, "temporal_policy_missing"),
    ("policy", {}, "temporal_policy_invalid"),
])
def test_missing_and_invalid_contract_or_policy_cannot_bypass(api, field, value, code):
    request = _request(api, _contract())
    if field == "temporal":
        request = replace(request, temporal=value)
    else:
        request = replace(request, autonomy_budget=replace(request.autonomy_budget, temporal_policy=value, max_external_requests=1))
    result = _decision(request)
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == code


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
@pytest.mark.parametrize("field,value,code", [
    ("generations", 1, "temporal_generations_mismatch"),
    ("risk_model_version", "arcana.risk.v0.3", "temporal_risk_model_mismatch"),
    ("calibration_profile_id", "arcana.cal.changed", "temporal_calibration_profile_mismatch"),
    ("decision_horizon", replace(HORIZON, context="changed"), "temporal_horizon_mismatch"),
    ("valid_from", "2026-09-11T10:01:00Z", "temporal_evidence_not_yet_valid"),
    ("expires_at", NOW, "temporal_evidence_expired"),
    ("expires_at", "2026-09-11T10:04:59Z", "temporal_evidence_horizon_not_covered"),
])
def test_temporal_binding_and_full_horizon_are_mandatory(api, field, value, code):
    contract = _contract()
    result = _decision(replace(_request(api, contract), temporal=replace(contract, **{field: value})))
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == code


def test_policy_mode_cannot_be_downgraded():
    contract = _contract([[.5]])
    result = _evaluate(contract, TemporalPolicy(TemporalMode.COMMON_ENVELOPE, 3, 10, 20))
    assert result.issue_code == "temporal_mode_mismatch"


def test_full_horizon_expiry_equality_and_overflow():
    assert _evaluate(replace(_contract(), expires_at="2026-09-11T10:05:00Z")).passed
    contract = replace(_contract(), decision_horizon=replace(HORIZON, duration_seconds=10**100))
    assert _evaluate(contract).issue_code == "temporal_horizon_end_unrepresentable"


@pytest.mark.parametrize("instant,code", [
    (NOW, "temporal_decision_time_invalid"),
    (None, "temporal_decision_time_invalid"),
    (datetime(2026, 9, 11, 10), "temporal_time_timezone_missing"),
])
def test_direct_binding_requires_timezone_aware_datetime(instant, code):
    contract = _contract()
    with pytest.raises(ArcanaValidationError) as error:
        validate_temporal_binding(contract, _policy(contract), risk_model_version=contract.risk_model_version,
                                  calibration_profile_id=contract.calibration_profile_id, decision_horizon=HORIZON,
                                  decision_time=instant, current_upper=contract.operators[0])
    assert error.value.code == code


@pytest.mark.parametrize("current,code", [
    (_matrix([[0]]), "temporal_current_shape_mismatch"),
    (_matrix([[0, .5], [0, 0]], order=("1", "0")), "temporal_current_node_order_mismatch"),
])
def test_direct_binding_rejects_mismatched_current_coordinates(current, code):
    contract = _contract()
    with pytest.raises(ArcanaValidationError) as error:
        validate_temporal_binding(contract, _policy(contract), risk_model_version=contract.risk_model_version,
                                  calibration_profile_id=contract.calibration_profile_id, decision_horizon=HORIZON,
                                  decision_time=datetime.fromisoformat(NOW), current_upper=current)
    assert error.value.code == code


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
@pytest.mark.parametrize("graph,code", [(GRAPH, "temporal_current_operator_not_declared"), ("sha256:" + "9" * 64, "temporal_current_graph_not_declared")])
def test_current_operator_is_content_and_graph_bound(api, graph, code):
    contract = _contract()
    operators = tuple(_matrix(op.values * .5, graph) for op in contract.operators)
    result = _decision(replace(_request(api, contract), temporal=replace(contract, operators=operators)))
    assert result.metrics["issue_code"] == code


@pytest.mark.parametrize("field,value", [("evidence_hash", "sha256:" + "9" * 64), ("evidence_source_id", "other-source")])
def test_fastgate_binds_evidence_reference(field, value):
    request = _request("exact", _contract())
    assert _decision(replace(request, **{field: value})).metrics["issue_code"] == f"temporal_{field}_mismatch"


def _cache(request):
    return FastGateCacheBinding(request.risk_model_version, request.calibration_profile_id, HORIZON.id,
                                HORIZON.duration_seconds, GRAPH, request.delta_upper.delta_hash, .9,
                                request.positive_vector.method, EXPIRES, evidence_hash=EVIDENCE,
                                evidence_source_id=request.evidence_source_id,
                                temporal_binding_hash=request.temporal.binding_hash,
                                temporal_policy_hash=temporal_policy_hash(request.autonomy_budget.temporal_policy))


def test_cache_binds_temporal_contract_and_policy():
    request = _request("exact", _contract())
    request = replace(request, cache_binding=_cache(request))
    assert_contract_gated(evaluate_fastgate(request).decision)
    for field in ("temporal_binding_hash", "temporal_policy_hash"):
        result = _decision(replace(request, cache_binding=replace(request.cache_binding, **{field: None})))
        assert result.metrics["issue_code"] == f"fastgate_cache_{field}_mismatch"
    changed = replace(request.temporal, initial_upper=(2., 0.))
    assert _decision(replace(request, temporal=changed)).metrics["issue_code"] == "fastgate_cache_temporal_binding_hash_mismatch"
    budget = replace(request.autonomy_budget, temporal_policy=_policy(request.temporal, 9, 20))
    assert _decision(replace(request, autonomy_budget=budget)).metrics["issue_code"] == "fastgate_cache_temporal_policy_hash_mismatch"


@pytest.mark.parametrize("fallback", ["explicit", "uncertain"])
def test_exact_fallback_retains_temporal_metrics_and_gate(fallback):
    request = complete_admission(_request("collatz", _contract()))
    vector = replace(request.positive_vector, method=PositiveVectorMethod.FALLBACK_EXACT) if fallback == "explicit" else replace(request.positive_vector, values=(1, 4))
    request = replace(request, positive_vector=vector)
    result = evaluate_fastgate(request)
    assert result.allowed
    assert result.fastgate.mode is FastGateMode.EXACT_RECOMPUTE
    assert result.decision.metrics["temporal_binding_hash"] == request.temporal.binding_hash
    denied = replace(request, autonomy_budget=replace(request.autonomy_budget, temporal_policy=_policy(request.temporal, .5, 20)))
    assert _decision(denied).metrics["issue_code"] == "temporal_peak_budget_exceeded"


def test_increment_and_temporal_requirements_are_both_enforced():
    temporal = _contract()
    request = _request("main", temporal)
    current = temporal.operators[0]
    increment = IncrementContract(IncrementScope.CALIBRATION_ENVELOPE, temporal.risk_model_version,
                                  temporal.calibration_profile_id, HORIZON, IncrementSnapshot(current), IncrementSnapshot(current),
                                  EVIDENCE, temporal.evidence_source_id, "joint_before_after_envelope", temporal.valid_from, EXPIRES)
    budget = replace(request.autonomy_budget, max_delta_rho_upper=0, increment_scope=IncrementScope.CALIBRATION_ENVELOPE)
    result = _decision(replace(request, autonomy_budget=budget, increment=increment))
    assert result.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY
    assert result.metrics["increment_binding_hash"] == increment.binding_hash
    assert result.metrics["temporal_binding_hash"] == temporal.binding_hash


@pytest.mark.parametrize("field,value,code", [
    ("operator_semantics", "horizon_total", "temporal_operator_semantics_unsupported"),
    ("state_units", "monetary_loss", "temporal_state_units_unsupported"),
    ("exogenous_input", "unknown", "temporal_exogenous_input_unsupported"),
    ("evidence_scope", "marginal_snapshots", "temporal_evidence_scope_mismatch"),
    ("valid_from", "2026-09-11T09:00:00", "temporal_time_timezone_missing"),
    ("expires_at", "2026-09-11T08:00:00Z", "temporal_evidence_window_invalid"),
    ("schema_version", "arcana.temporal.v2", "temporal_version_unsupported"),
    ("evidence_source_id", " ", "temporal_evidence_source_blank"),
    ("initial_upper", (1,), "temporal_initial_state_dimension_mismatch"),
    ("generations", 257, "temporal_generation_limit_exceeded"),
    ("operators", (), "temporal_operators_empty"),
    ("operators", [], "temporal_operators_invalid"),
])
def test_unsupported_or_incomplete_premises_are_not_assumed(field, value, code):
    with pytest.raises(ArcanaValidationError) as error:
        replace(_contract(), **{field: value})
    assert error.value.code == code


def test_family_requires_entrywise_domination_not_spectral_comparison():
    contract = _contract()
    with pytest.raises(ArcanaValidationError) as error:
        replace(contract, operators=(_matrix([[0, 2], [0, 0]]),))
    assert error.value.code == "temporal_operator_outside_envelope"


@pytest.mark.parametrize("op,code", [
    (_matrix([[0]]), "temporal_operator_shape_mismatch"),
    (_matrix([[0, .5], [0, 0]], order=("1", "0")), "temporal_operator_node_order_mismatch"),
])
def test_family_coordinate_mismatch_fails(op, code):
    with pytest.raises(ArcanaValidationError) as error:
        replace(_contract(), operators=(op,))
    assert error.value.code == code


def test_fixed_mode_is_not_an_undeclared_family():
    with pytest.raises(ArcanaValidationError) as error:
        replace(_contract(), mode=TemporalMode.FIXED_OPERATOR)
    assert error.value.code == "temporal_fixed_operator_count_invalid"
    with pytest.raises(ArcanaValidationError) as error:
        replace(_contract(), mode=TemporalMode.FIXED_OPERATOR, operators=(_contract().operators[0],))
    assert error.value.code == "temporal_fixed_envelope_mismatch"


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
def test_mutation_cannot_keep_old_contract_identity(api):
    contract = _contract()
    request = _request(api, contract)
    object.__setattr__(contract, "initial_upper", (0., 0.))
    result = _decision(request)
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == "temporal_binding_hash_mismatch"


@pytest.mark.parametrize("location", ["top", "operator", "horizon"])
def test_schema_and_typed_unknown_fields_fail(location):
    document = _contract().to_mapping()
    target = {"top": document, "operator": document["operators"][0], "horizon": document["decision_horizon"]}[location]
    target["unknown"] = 1
    with pytest.raises(ArcanaValidationError):
        validate_document(document)
    with pytest.raises(ArcanaValidationError) as error:
        TemporalContract.from_mapping(document)
    assert error.value.code == "temporal_field_unknown"


@pytest.mark.parametrize("key", ["binding_hash", "evidence_hash", "generations", "initial_upper", "exogenous_input", "operators"])
def test_missing_wire_fields_are_specific(key):
    document = _contract().to_mapping()
    del document[key]
    with pytest.raises(ArcanaValidationError) as error:
        TemporalContract.from_mapping(document)
    assert error.value.code == f"temporal_{key}_missing"


@pytest.mark.parametrize("fixed", [True, False])
def test_canonical_wire_roundtrip_preserves_scope_and_recurrence(fixed):
    contract = _contract([[.5]]) if fixed else _contract()
    restored = parse_typed_document(json.loads(json.dumps(contract.to_mapping())))
    assert isinstance(restored, TemporalContract)
    assert restored.to_mapping() == contract.to_mapping()
    assert _evaluate(restored).metrics == _evaluate(contract).metrics
    tampered = contract.to_mapping()
    tampered["initial_upper"][0] = 0
    with pytest.raises(ArcanaValidationError) as error:
        parse_typed_document(tampered)
    assert error.value.code == "temporal_binding_hash_mismatch"


@pytest.mark.parametrize("value", [True, -1, float("nan"), float("inf"), "1", 10**400])
def test_invalid_initial_state_never_becomes_zero(value):
    with pytest.raises(ArcanaValidationError):
        replace(_contract(), initial_upper=(value, 0))


def test_resource_caps_and_policy_mapping():
    assert _evaluate(_contract([[0]], generations=256)).passed
    policy = _policy(_contract())
    assert TemporalPolicy.from_mapping(vars(policy)) == policy
    assert AutonomyBudget.from_mapping({"expires_at": EXPIRES, "temporal_policy": vars(policy)}).temporal_policy == policy
    with pytest.raises(ArcanaValidationError) as error:
        TemporalPolicy.from_mapping({"mode": "common_envelope", "generations": 3, "max_peak_activations_upper": 1})
    assert error.value.code == "temporal_policy_max_cumulative_activations_upper_missing"
    with pytest.raises(ArcanaValidationError) as error:
        replace(_contract(), operators=(_contract().operators[0],) * 65)
    assert error.value.code == "temporal_operator_limit_exceeded"
    with pytest.raises(ArcanaValidationError) as error:
        _contract(np.zeros((65, 65)))
    assert error.value.code == "temporal_node_limit_exceeded"


def test_family_duplicates_are_rejected_without_discarding_entries():
    contract = _contract()
    with pytest.raises(ArcanaValidationError) as error:
        replace(contract, operators=(contract.operators[0], contract.operators[0]))
    assert error.value.code == "temporal_operator_duplicate"


def test_node_and_family_caps_accept_the_exact_boundary():
    assert _evaluate(_contract(np.zeros((64, 64)), generations=1)).passed
    contract = _contract([[.5]], generations=1)
    family = tuple(_matrix([[index / 128]]) for index in range(1, 65))
    result = _evaluate(replace(contract, mode=TemporalMode.COMMON_ENVELOPE, operators=family))
    assert result.passed
    assert result.metrics["temporal_generation_totals_upper"] == [1, .5]


@pytest.mark.parametrize("field", ["max_peak_activations_upper", "max_cumulative_activations_upper"])
@pytest.mark.parametrize("value", [True, -1, float("nan"), float("inf"), "1", 10**400])
def test_policy_limits_require_finite_nonnegative_numbers(field, value):
    with pytest.raises(ArcanaValidationError) as error:
        replace(_policy(_contract()), **{field: value})
    assert error.value.primary_issue.path == ("temporal_policy", field)


def test_temporal_context_cannot_serialize_or_emit_legacy_certificate():
    artifacts = build_demo_artifacts()
    context = replace(artifacts.context, autonomy_budget=replace(artifacts.context.autonomy_budget, temporal_policy=_policy(_contract())))
    profile = load_typed_fixture(EXAMPLE_DIR / "calibration_profile_a0.synthetic.json")
    for operation in (
        lambda: risk_context_to_mapping(context),
        lambda: validate_risk_context_semantics(context, now=datetime.fromisoformat("2026-06-09T00:00:00+00:00")),
        lambda: build_demo_non_certifiable_certificate(certificate_id="arcana-cert-temporal-negative", context=context,
                                                       calibration_profile=profile, issued_at="2026-06-09T00:00:00Z", caveats=("synthetic",)),
    ):
        with pytest.raises(ArcanaValidationError) as error:
            operation()
        assert error.value.code == "legacy_artifact_temporal_policy_unsupported"


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
def test_legacy_request_never_claims_temporal_evaluation(api):
    request = _request(api, _contract())
    request = replace(request, temporal=None, autonomy_budget=AutonomyBudget(EXPIRES, max_external_requests=0))
    result = _decision(request)
    assert_contract_gated(result)
    assert result.metrics["temporal_scope"] == "not_evaluated"


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
def test_a0_cannot_admit_with_temporal_contract(api):
    request = _request(api, _contract())
    if api == "main":
        profile = replace(request.calibration_profile, level=CalibrationLevel.A0, source=("synthetic_demo",))
        request = replace(request, calibration_profile=profile)
    else:
        request = replace(request, calibration_level=CalibrationLevel.A0)
    assert _decision(request).verdict is Verdict.OBSERVE_ONLY
