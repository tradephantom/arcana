"""Conditional increment proof oracles, bindings and downgrade regressions."""

from dataclasses import replace
from datetime import datetime
from fractions import Fraction
from itertools import product
import json
import math

import numpy as np
import pytest

from arcana.artifacts import validate_risk_context_semantics
from arcana.calibration import CalibrationProfile, CalibrationUncertainty, EdgeWeightPolicy, EvidenceWindow
from arcana.certificate import build_demo_non_certifiable_certificate, risk_context_to_mapping
from arcana.decision import DecisionEvaluationRequest, evaluate_decision
from arcana.demo import build_demo_artifacts
from arcana.errors import ArcanaValidationError, CalibrationLevel, CertificationStatus, FastGateMode, IncrementScope, PositiveVectorMethod, Verdict
from arcana.fastgate import FastGateCacheBinding, FastGateRequest, PositiveVector, SparseDeltaEntry, SparseMatrixDelta, compute_sparse_delta_hash, evaluate_fastgate
from arcana.increments import IncrementContract, IncrementSnapshot, evaluate_increment
from arcana.matrices import MatrixBundle, PropagationMatrix
from arcana.model import AutonomyBudget, DecisionHorizon
from arcana.schemas import EXAMPLE_DIR, load_typed_fixture, parse_typed_document, validate_document
from admission_support import assert_contract_gated, complete_admission


GRAPH = "sha256:" + "1" * 64
EVIDENCE = "sha256:" + "2" * 64
NOW = "2026-09-10T10:00:00Z"
EXPIRES = "2026-09-10T11:00:00Z"
HORIZON = DecisionHorizon("increment_synthetic", 300, "synthetic conditional increment")


def _matrix(values, *, graph=GRAPH, order=("a", "b")):
    return PropagationMatrix(values, order, graph)


def _contract(scope=IncrementScope.CALIBRATION_ENVELOPE, *, lower=True):
    return IncrementContract(
        scope=scope, risk_model_version="arcana.risk.v0.2", calibration_profile_id="arcana.cal.increment_a1",
        decision_horizon=HORIZON,
        before=IncrementSnapshot(_matrix([[0, .5], [.5, 0]]), _matrix([[0, .5], [0, 0]]) if lower else None),
        after=IncrementSnapshot(_matrix([[0, .5], [.78125, 0]])),
        evidence_hash=EVIDENCE, evidence_source_id="synthetic-increment-oracle",
        evidence_scope="joint_before_after_envelope" if scope is IncrementScope.CALIBRATION_ENVELOPE else "represented_snapshot_pair",
        valid_from="2026-09-10T09:00:00Z", expires_at=EXPIRES,
    )


def _budget(contract, limit=.25):
    return AutonomyBudget(EXPIRES, max_delta_rho_upper=limit, increment_scope=contract.scope)


def _profile(contract):
    return CalibrationProfile(
        profile_id=contract.calibration_profile_id, risk_model_version=contract.risk_model_version,
        level=CalibrationLevel.A1, decision_horizon=contract.decision_horizon,
        source=("static_conservative_prior",),
        evidence_window=EvidenceWindow("2026-09-10T09:00:00Z", "2026-09-10T09:59:00Z", 3600),
        confidence=.8, uncertainty=CalibrationUncertainty(0, .3, .8),
        edge_weight_policy=EdgeWeightPolicy(True, True, True),
        caveats=("synthetic contract test, not empirical evidence",),
        certification_status=CertificationStatus.NON_CERTIFIABLE,
        last_updated_at="2026-09-10T09:59:00Z",
    )


def _main(contract):
    upper = contract.after.upper
    lower = contract.after.lower or _matrix(np.zeros_like(upper.values), graph=upper.graph_hash, order=upper.node_order)
    return DecisionEvaluationRequest(
        risk_model_version=contract.risk_model_version, calibration_profile=_profile(contract),
        decision_horizon=contract.decision_horizon, graph_hash=upper.graph_hash,
        matrix_bundle=MatrixBundle(lower, upper, upper), rho_threshold=.9,
        autonomy_budget=_budget(contract), decision_time=NOW, increment=contract,
    )


def _fastgate(contract, mode=FastGateMode.EXACT_RECOMPUTE):
    entries = (SparseDeltaEntry(1, 0, .28125),)
    delta = SparseMatrixDelta(compute_sparse_delta_hash(graph_hash=GRAPH, decision_horizon=HORIZON, entries=entries),
                              GRAPH, HORIZON, entries)
    return FastGateRequest(
        mode=mode, risk_model_version=contract.risk_model_version,
        calibration_profile_id=contract.calibration_profile_id, calibration_level=CalibrationLevel.A1,
        required_calibration_level=CalibrationLevel.A1, decision_horizon=HORIZON, decision_time=NOW,
        graph_hash=GRAPH, before_upper=contract.before.upper, delta_upper=delta, threshold=.9,
        autonomy_budget=_budget(contract), increment=contract, evidence_hash=EVIDENCE,
        evidence_source_id=contract.evidence_source_id,
        positive_vector=PositiveVector((1, 1.25), ("a", "b"), GRAPH,
                                      PositiveVectorMethod.IRREDUCIBLE_PERRON_VECTOR, irreducible_declared=True),
    )


def _request(api, contract):
    if api == "main":
        return _main(contract)
    if api == "exact":
        return _fastgate(contract)
    if api == "collatz":
        return _fastgate(contract, FastGateMode.PERRON_COLLATZ_BOUND)
    raise AssertionError(api)


def _evaluate(request):
    if isinstance(request, DecisionEvaluationRequest):
        return evaluate_decision(request)
    return evaluate_fastgate(request).decision


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
@pytest.mark.parametrize("lower", [True, False])
def test_c02_latent_increment_budget_is_not_upper_model_increment(api, lower):
    contract = _contract(lower=lower)
    result = _evaluate(_request(api, contract))
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] in {"autonomy_budget_delta_rho_exceeded", "fastgate_budget_delta_rho_exceeded"}
    # Exact radius identities, independent of implementation candidate solvers.
    assert Fraction(1, 2) * Fraction(25, 32) == Fraction(5, 8)**2
    assert Fraction(1, 2) * Fraction(9, 32) == Fraction(3, 8)**2
    assert Fraction(3, 8) > Fraction(1, 4) > Fraction(1, 8)
    assert Fraction(result.metrics["delta_rho_upper"]) >= Fraction(5, 8)
    assert result.metrics["increment_before_lower"] == 0
    expected_source = "calibration_matrix_numerical_lower" if lower else "nonnegative_zero_fallback"
    assert result.metrics["increment_baseline_source"] == expected_source
    assert result.metrics["increment_binding_hash"] == contract.binding_hash
    assert result.metrics["increment_scope"] == "calibration_envelope"
    assert result.metrics["increment_evidence_assurance"] == "declared_premises_not_empirically_verified"


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
def test_explicit_upper_model_scope_retains_only_represented_model_guarantee(api):
    contract = _contract(IncrementScope.UPPER_MODEL)
    result = _evaluate(complete_admission(_request(api, contract)))
    assert result.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY
    assert Fraction(1, 8) <= Fraction(result.metrics["delta_rho_upper"]) < Fraction(1, 4)
    assert result.metrics["increment_scope"] == "upper_model"
    assert result.metrics["increment_baseline_source"] == "upper_model_numerical_lower"


def test_nonzero_calibration_lower_can_avoid_zero_fallback_denial():
    matrix = lambda value: _matrix([[value]], order=("a",))
    contract = replace(_contract(), before=IncrementSnapshot(matrix(.5), matrix(.375)), after=IncrementSnapshot(matrix(.625)))
    request = complete_admission(_main(contract))
    result = evaluate_decision(request)
    assert result.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY
    assert result.metrics["delta_rho_upper"] == .25
    missing = replace(contract, before=IncrementSnapshot(matrix(.5)))
    denied = evaluate_decision(replace(request, increment=missing))
    assert denied.verdict is Verdict.DENY
    assert denied.metrics["delta_rho_upper"] == .625


def test_wide_unchanged_envelope_charges_uncertainty_without_relational_proof():
    contract = _contract()
    contract = replace(contract, after=IncrementSnapshot(contract.before.upper))
    result = evaluate_increment(contract, decision_time=NOW)
    assert result["delta_rho_upper"] >= .5


@pytest.mark.parametrize("before,after", [(.5, .25), (.5, .5), (0, .5)])
def test_decreasing_point_model_never_credits_budget(before, after):
    matrix = lambda value: _matrix([[value]], order=("a",))
    contract = replace(_contract(), before=IncrementSnapshot(matrix(before), matrix(before)), after=IncrementSnapshot(matrix(after)))
    result = evaluate_increment(contract, decision_time=NOW)
    assert result["delta_rho_upper"] == max(0, after - before)


def test_enclosure_over_exhaustive_dyadic_two_cycle_family():
    # Each true radius is sqrt(a*b); squared rational comparison avoids a float oracle.
    contract = _contract()
    bound = Fraction(evaluate_increment(contract, decision_time=NOW)["delta_rho_upper"])
    for a, b in product([Fraction(0), Fraction(1, 4), Fraction(1, 2)], [Fraction(0), Fraction(1, 4), Fraction(25, 32)]):
        assert bound**2 >= a * b
    matrix = lambda value: _matrix([[value]], order=("a",))
    for low, high, after in product([0, .125, .25], [.25, .5], [0, .375, .75]):
        contract = replace(contract, before=IncrementSnapshot(matrix(high), matrix(low)), after=IncrementSnapshot(matrix(after)))
        bound = Fraction(evaluate_increment(contract, decision_time=NOW)["delta_rho_upper"])
        for before_true, after_true in product([low, high], [0, after]):
            assert bound >= max(Fraction(0), Fraction(after_true) - Fraction(before_true))


def test_increment_subtraction_rounds_outward_at_binary64_edge():
    matrix = lambda value: _matrix([[value]], order=("a",))
    contract = replace(_contract(), before=IncrementSnapshot(matrix(.5), matrix(2**-55)), after=IncrementSnapshot(matrix(.5)))
    result = evaluate_increment(contract, decision_time=NOW)
    exact = Fraction(1, 2) - Fraction(1, 2**55)
    assert Fraction(result["delta_rho_upper"]) >= exact
    assert Fraction(math.nextafter(result["delta_rho_upper"], -math.inf)) < exact


@pytest.mark.parametrize("scalar", [0, .01, -1, float("nan"), "0", False])
def test_scoped_main_evaluator_rejects_all_scalar_overrides(scalar):
    result = evaluate_decision(replace(_main(_contract()), delta_rho_upper=scalar))
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == "increment_scalar_override_forbidden"


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
@pytest.mark.parametrize("value,code", [(None, "increment_contract_missing"), ({}, "increment_contract_invalid")])
def test_missing_and_invalid_contracts_are_distinct(api, value, code):
    result = _evaluate(replace(_request(api, _contract()), increment=value))
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == code


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
def test_scope_downgrade_and_scope_omission_are_rejected(api):
    contract = _contract()
    request = _request(api, contract)
    result = _evaluate(replace(request, increment=_contract(IncrementScope.UPPER_MODEL)))
    assert result.metrics["issue_code"] == "increment_scope_mismatch"
    result = _evaluate(replace(request, autonomy_budget=replace(request.autonomy_budget, increment_scope=None)))
    assert result.metrics["issue_code"] == "increment_budget_scope_missing"


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
@pytest.mark.parametrize("field,value,code", [
    ("risk_model_version", "arcana.risk.v0.3", "increment_risk_model_mismatch"),
    ("calibration_profile_id", "arcana.cal.other", "increment_calibration_profile_mismatch"),
    ("decision_horizon", replace(HORIZON, context="different context"), "increment_horizon_mismatch"),
    ("decision_horizon", replace(HORIZON, duration_seconds=301), "increment_horizon_mismatch"),
    ("valid_from", "2026-09-10T10:01:00Z", "increment_evidence_not_yet_valid"),
    ("expires_at", NOW, "increment_evidence_expired"),
])
def test_evaluator_binding_and_time_fail_closed(api, field, value, code):
    contract = _contract()
    result = _evaluate(replace(_request(api, contract), increment=replace(contract, **{field: value})))
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == code


@pytest.mark.parametrize("field,value,code", [
    ("evidence_hash", "sha256:" + "3" * 64, "increment_evidence_hash_mismatch"),
    ("evidence_source_id", "different-evidence", "increment_evidence_source_id_mismatch"),
])
def test_fastgate_binds_current_evidence_identity(field, value, code):
    request = _fastgate(_contract())
    result = evaluate_fastgate(replace(request, **{field: value})).decision
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == code


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
def test_after_matrix_must_be_actual_evaluator_matrix(api):
    contract = _contract()
    different = replace(contract, after=IncrementSnapshot(_matrix([[0, .5], [.5, 0]])))
    result = _evaluate(replace(_request(api, contract), increment=different))
    assert result.metrics["issue_code"] == "increment_after_upper_mismatch"


def test_fastgate_before_content_is_bound_even_when_graph_hash_is_unchanged():
    contract = _contract()
    different = replace(contract, before=IncrementSnapshot(_matrix([[0, .25], [.5, 0]])))
    result = evaluate_fastgate(replace(_fastgate(contract), increment=different)).decision
    assert result.metrics["issue_code"] == "increment_before_upper_mismatch"


def test_main_binds_declared_after_lower_endpoint():
    contract = _contract()
    different = replace(contract, after=IncrementSnapshot(contract.after.upper, _matrix([[0, .1], [0, 0]])))
    result = evaluate_decision(replace(_main(contract), increment=different))
    assert result.metrics["issue_code"] == "increment_after_lower_mismatch"


@pytest.mark.parametrize("method,vector", [
    (PositiveVectorMethod.FALLBACK_EXACT, (1, 1.25)),
    (PositiveVectorMethod.IRREDUCIBLE_PERRON_VECTOR, (1, 2)),
])
def test_exact_fallback_preserves_calibration_envelope_scope(method, vector):
    contract = _contract()
    request = _fastgate(contract, FastGateMode.PERRON_COLLATZ_BOUND)
    request = replace(request, autonomy_budget=_budget(contract, 2), positive_vector=replace(request.positive_vector, method=method, values=vector))
    evaluated = evaluate_fastgate(complete_admission(request))
    assert evaluated.fastgate.mode is FastGateMode.EXACT_RECOMPUTE
    assert evaluated.allowed
    assert evaluated.decision.metrics["increment_binding_hash"] == contract.binding_hash
    assert evaluated.decision.metrics["increment_scope"] == "calibration_envelope"
    assert evaluated.decision.metrics["delta_rho_upper"] >= .625


def _cache(request):
    return FastGateCacheBinding(
        request.risk_model_version, request.calibration_profile_id, HORIZON.id, HORIZON.duration_seconds,
        GRAPH, request.delta_upper.delta_hash, request.threshold, request.positive_vector.method, EXPIRES,
        evidence_hash=request.evidence_hash, evidence_source_id=request.evidence_source_id,
        increment_scope=request.increment.scope, increment_binding_hash=request.increment.binding_hash,
    )


def test_cache_cannot_reuse_legacy_scope_or_changed_calibration_lower():
    contract = _contract()
    request = _fastgate(contract)
    request = replace(request, autonomy_budget=_budget(contract, 1), cache_binding=_cache(request))
    assert_contract_gated(evaluate_fastgate(request).decision)
    legacy_cache = replace(request.cache_binding, increment_scope=None, increment_binding_hash=None)
    assert evaluate_fastgate(replace(request, cache_binding=legacy_cache)).decision.metrics["issue_code"] == "fastgate_cache_increment_scope_mismatch"
    new_lower = replace(contract, before=IncrementSnapshot(contract.before.upper, _matrix([[0, 0], [0, 0]])))
    result = evaluate_fastgate(replace(request, increment=new_lower)).decision
    assert result.metrics["issue_code"] == "fastgate_cache_increment_binding_hash_mismatch"
    missing_hash = replace(request.cache_binding, increment_binding_hash=None)
    assert evaluate_fastgate(replace(request, cache_binding=missing_hash)).decision.metrics["issue_code"] == "fastgate_cache_increment_binding_hash_mismatch"


@pytest.mark.parametrize("field,value,code", [
    ("increment_scope", "unrecognized", "enum_invalid"),
    ("increment_binding_hash", "bad-digest", "sha256_hash_invalid"),
])
def test_malformed_increment_cache_is_rejected(field, value, code):
    request = _fastgate(_contract())
    result = evaluate_fastgate(replace(request, cache_binding=replace(_cache(request), **{field: value}))).decision
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == code


@pytest.mark.parametrize("lower,code", [
    (_matrix([[0, .6], [0, 0]]), "increment_interval_order_invalid"),
    (_matrix([[0, .5], [0, 0]], order=("b", "a")), "increment_interval_node_order_mismatch"),
    (_matrix([[0]], order=("a",)), "increment_interval_shape_mismatch"),
    (_matrix([[0, .5], [0, 0]], graph="sha256:" + "4" * 64), "increment_interval_graph_mismatch"),
])
def test_invalid_lower_interval_is_never_replaced_by_zero(lower, code):
    with pytest.raises(ArcanaValidationError) as error:
        IncrementSnapshot(_contract().before.upper, lower)
    assert error.value.code == code


def test_node_coordinate_change_is_not_an_increment_pair():
    contract = _contract()
    with pytest.raises(ArcanaValidationError) as error:
        replace(contract, after=IncrementSnapshot(_matrix([[0, .5], [.78125, 0]], order=("b", "a"))))
    assert error.value.code == "increment_transition_node_order_mismatch"


def test_increment_pair_rejects_changed_matrix_dimension():
    with pytest.raises(ArcanaValidationError) as error:
        replace(_contract(), after=IncrementSnapshot(_matrix([[.5]], order=("a",))))
    assert error.value.code == "increment_transition_shape_mismatch"


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
def test_increment_graph_mismatch_is_a_distinct_failure(api):
    contract = _contract()
    after = IncrementSnapshot(_matrix(contract.after.upper.values, graph="sha256:" + "9" * 64))
    result = _evaluate(replace(_request(api, contract), increment=replace(contract, after=after)))
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == "increment_after_upper_graph_mismatch"


@pytest.mark.parametrize("field,value,code", [
    ("schema_version", "arcana.increment.v9", "increment_version_unsupported"),
    ("valid_from", "2026-09-10T09:00:00", "increment_time_timezone_missing"),
    ("expires_at", "2026-09-10T08:59:00Z", "increment_evidence_window_invalid"),
    ("evidence_scope", "marginal_only", "increment_evidence_scope_mismatch"),
    ("evidence_source_id", "  ", "increment_evidence_source_blank"),
])
def test_constructor_rejects_invalid_contract_premises(field, value, code):
    with pytest.raises(ArcanaValidationError) as error:
        replace(_contract(), **{field: value})
    assert error.value.code == code


@pytest.mark.parametrize("time,code", [
    ("2026-09-10T10:00:00", "increment_time_timezone_missing"),
    ("2026-09-10T08:59:00Z", "increment_evidence_not_yet_valid"),
    (EXPIRES, "increment_evidence_expired"),
])
def test_standalone_increment_checks_time(time, code):
    with pytest.raises(ArcanaValidationError) as error:
        evaluate_increment(_contract(), decision_time=time)
    assert error.value.code == code


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
@pytest.mark.parametrize("target,code", [("snapshot", "increment_snapshot_hash_mismatch"), ("binding", "increment_binding_hash_mismatch")])
def test_mutated_objects_are_revalidated(api, target, code):
    contract = _contract()
    request = _request(api, contract)
    if target == "snapshot":
        object.__setattr__(contract.before, "lower", None)
    else:
        object.__setattr__(contract, "evidence_source_id", "mutated-source")
    result = _evaluate(request)
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == code


def test_snapshot_copies_input_and_matrix_storage_cannot_be_made_writeable():
    values = np.array([[0, .5], [.5, 0]])
    snapshot = IncrementSnapshot(_matrix(values))
    original_hash = snapshot.snapshot_hash
    values[0, 1] = .1
    assert snapshot.validated_snapshot().snapshot_hash == original_hash
    with pytest.raises(ValueError):
        snapshot.upper.values.setflags(write=True)


@pytest.mark.parametrize("scope", list(IncrementScope))
def test_typed_schema_roundtrip_is_canonical_and_complete(scope):
    contract = _contract(scope)
    wire = contract.to_mapping()
    restored = parse_typed_document(json.loads(json.dumps(wire)))
    assert isinstance(restored, IncrementContract)
    assert restored.to_mapping() == wire
    assert restored.binding_hash == contract.binding_hash
    assert evaluate_increment(restored, decision_time=NOW) == evaluate_increment(contract, decision_time=NOW)


def test_public_increment_example_matches_analytical_contract():
    example = load_typed_fixture(EXAMPLE_DIR / "increment_calibration_envelope.synthetic.json")
    assert isinstance(example, IncrementContract)
    assert example.to_mapping() == _contract().to_mapping()


@pytest.mark.parametrize("value", [0.0, -0.0, 2**-1074, math.nextafter(.5, 1), 2**1023])
def test_represented_entry_identity_survives_json_roundtrip(value):
    matrix = _matrix([[value]], order=("a",))
    contract = replace(_contract(), before=IncrementSnapshot(matrix), after=IncrementSnapshot(matrix))
    restored = parse_typed_document(json.loads(json.dumps(contract.to_mapping())))
    assert restored.before.upper.values[0, 0].item().hex() == float(value).hex()
    assert restored.binding_hash == contract.binding_hash


@pytest.mark.parametrize("location", ["top", "horizon", "snapshot", "matrix"])
def test_unknown_fields_are_rejected_by_schema_and_typed_loader(location):
    document = _contract().to_mapping()
    target = {"top": document, "horizon": document["decision_horizon"], "snapshot": document["before"], "matrix": document["before"]["upper"]}[location]
    target["unrecognized"] = True
    with pytest.raises(ArcanaValidationError):
        validate_document(document)
    with pytest.raises(ArcanaValidationError) as error:
        IncrementContract.from_mapping(document)
    assert error.value.code == "increment_field_unknown"


@pytest.mark.parametrize("mutation,code", [("matrix", "increment_snapshot_hash_mismatch"), ("evidence", "increment_binding_hash_mismatch"), ("null_lower", "object_expected")])
def test_wire_tampering_and_null_lower_never_silently_repair(mutation, code):
    document = _contract().to_mapping()
    if mutation == "matrix":
        document["before"]["upper"]["values"][1][0] = .25
    elif mutation == "evidence":
        document["evidence_source_id"] = "different-source"
    elif mutation == "null_lower":
        document["before"]["lower"] = None
    with pytest.raises(ArcanaValidationError) as error:
        IncrementContract.from_mapping(document)
    assert error.value.code == code


@pytest.mark.parametrize("key", ["before", "after", "binding_hash", "evidence_hash", "scope"])
def test_missing_wire_fields_are_identified(key):
    document = _contract().to_mapping()
    del document[key]
    with pytest.raises(ArcanaValidationError) as error:
        IncrementContract.from_mapping(document)
    assert error.value.code == f"increment_{key}_missing"


@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
def test_scope_requires_numeric_budget_and_rejects_unrepresentable_limit(api):
    request = _request(api, _contract())
    missing = replace(request.autonomy_budget, max_delta_rho_upper=None, max_external_requests=1)
    assert _evaluate(replace(request, autonomy_budget=missing)).metrics["issue_code"] == "increment_budget_limit_missing"
    huge = replace(request.autonomy_budget, max_delta_rho_upper=10**400)
    result = _evaluate(replace(request, autonomy_budget=huge))
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == "number_unrepresentable"


def test_scoped_budget_mapping_requires_increment_limit():
    with pytest.raises(ArcanaValidationError) as error:
        AutonomyBudget.from_mapping({"expires_at": EXPIRES, "max_external_requests": 1, "increment_scope": "calibration_envelope"})
    assert error.value.code == "increment_budget_limit_missing"


def test_legacy_scalar_and_fastgate_paths_are_explicitly_labelled():
    request = _main(_contract())
    request = replace(request, increment=None, autonomy_budget=replace(request.autonomy_budget, increment_scope=None))
    result = evaluate_decision(request)
    assert_contract_gated(result)
    assert result.metrics["increment_scope"] == "legacy_caller_declared"
    assert result.metrics["delta_rho_upper"] == 0
    request = _fastgate(_contract())
    request = replace(request, increment=None, autonomy_budget=replace(request.autonomy_budget, increment_scope=None))
    assert evaluate_fastgate(request).decision.metrics["increment_scope"] == "legacy_upper_model"


def test_scoped_context_cannot_serialize_or_emit_legacy_certificate():
    artifacts = build_demo_artifacts()
    context = replace(artifacts.context, autonomy_budget=replace(artifacts.context.autonomy_budget, increment_scope=IncrementScope.CALIBRATION_ENVELOPE))
    with pytest.raises(ArcanaValidationError) as error:
        risk_context_to_mapping(context)
    assert error.value.code == "legacy_artifact_increment_scope_unsupported"
    with pytest.raises(ArcanaValidationError) as error:
        validate_risk_context_semantics(context, now=datetime.fromisoformat("2026-06-09T00:00:00+00:00"))
    assert error.value.code == "legacy_artifact_increment_scope_unsupported"
    profile = load_typed_fixture(EXAMPLE_DIR / "calibration_profile_a0.synthetic.json")
    with pytest.raises(ArcanaValidationError) as error:
        build_demo_non_certifiable_certificate(certificate_id="arcana-cert-increment-negative", context=context,
                                               calibration_profile=profile, issued_at="2026-06-09T00:00:00Z", caveats=("synthetic test",))
    assert error.value.code == "legacy_artifact_increment_scope_unsupported"


@pytest.mark.parametrize("value,code", [
    (-.1, "matrix_value_negative"),
    (float("nan"), "matrix_value_nonfinite"),
    (float("inf"), "matrix_value_nonfinite"),
    (True, "matrix_value_invalid"),
    (".5", "matrix_value_invalid"),
    (10**400, "matrix_value_nonfinite"),
])
def test_wire_matrix_rejects_invalid_numeric_entries(value, code):
    document = _contract().to_mapping()
    document["before"]["upper"]["values"][0][1] = value
    with pytest.raises(ArcanaValidationError) as error:
        IncrementContract.from_mapping(document)
    assert error.value.code == code


def test_legacy_context_schema_rejects_scope_instead_of_promoting_it():
    document = risk_context_to_mapping(build_demo_artifacts().context)
    document["autonomy_budget"]["increment_scope"] = "calibration_envelope"
    with pytest.raises(ArcanaValidationError):
        parse_typed_document(document)


@pytest.mark.parametrize("scope", list(IncrementScope))
def test_a0_remains_observe_only_under_scoped_main_request(scope):
    request = _main(_contract(scope))
    profile = replace(request.calibration_profile, level=CalibrationLevel.A0, source=("synthetic_demo",))
    result = evaluate_decision(replace(request, calibration_profile=profile))
    assert result.verdict is Verdict.OBSERVE_ONLY
    assert result.metrics["increment_scope"] == scope.value


@pytest.mark.parametrize("mode", [FastGateMode.OBSERVE_ONLY, FastGateMode.EXACT_RECOMPUTE, FastGateMode.PERRON_COLLATZ_BOUND])
def test_a0_or_observe_fastgate_never_admits_scoped_request(mode):
    request = _fastgate(_contract(), mode)
    assert evaluate_fastgate(replace(request, calibration_level=CalibrationLevel.A0)).decision.verdict is Verdict.OBSERVE_ONLY
