"""Exact joint-coverage oracles, source bindings and downgrade controls."""

from dataclasses import replace
from datetime import datetime
from fractions import Fraction
from itertools import product
import copy
import json
import math

import numpy as np
import pytest

from arcana.artifacts import validate_risk_context_semantics
from arcana.calibration import CalibrationProfile, CalibrationUncertainty, EdgeWeightPolicy, EvidenceWindow
from arcana.certificate import build_demo_non_certifiable_certificate, risk_context_to_mapping
from arcana.coverage import CoverageContract, CoverageFailureBound, coverage_policy_hash, evaluate_coverage, validate_coverage_binding
from arcana.decision import DecisionEvaluationRequest, evaluate_decision
from arcana.demo import build_demo_artifacts
from arcana.errors import ArcanaValidationError, CalibrationLevel, CertificationStatus, CoverageMethod, CoverageSource, FastGateMode, IncrementScope, PositiveVectorMethod, TemporalMode, Verdict
from arcana.fastgate import FastGateCacheBinding, FastGateRequest, PositiveVector, SparseMatrixDelta, compute_sparse_delta_hash, evaluate_fastgate
from arcana.increments import IncrementContract, IncrementSnapshot
from arcana.matrices import MatrixBundle, PropagationMatrix
from arcana.model import AutonomyBudget, CoveragePolicy, DecisionHorizon, TemporalPolicy, reject_legacy_scoped_budget
from arcana.schemas import EXAMPLE_DIR, load_typed_fixture, parse_typed_document, validate_document
from arcana.temporal import TemporalContract
from admission_support import assert_contract_gated, complete_admission


GRAPH = "sha256:" + "5" * 64
EVIDENCE = "sha256:" + "6" * 64
DESIGN = "sha256:" + "7" * 64
NOW = "2026-09-28T10:00:00Z"
START = "2026-09-28T09:00:00Z"
EXPIRY = "2026-09-28T11:00:00Z"
HORIZON = DecisionHorizon("coverage_synthetic", 300, "fixed synthetic operator family")
APIS = ("main", "exact", "collatz", "fallback", "uncertain_fallback")


def _matrix(values=None):
    return PropagationMatrix([[.25, 0], [0, .125]] if values is None else values, ("a", "b"), GRAPH)


def _increment(lower=True):
    low = _matrix([[.125, 0], [0, .0625]]) if lower else None
    return IncrementContract(IncrementScope.CALIBRATION_ENVELOPE, "arcana.risk.v0.2", "arcana.cal.coverage_a1", HORIZON,
                             IncrementSnapshot(_matrix(), low), IncrementSnapshot(_matrix(), low), EVIDENCE,
                             "synthetic-coverage-oracle", "joint_before_after_envelope", START, EXPIRY)


def _temporal():
    return TemporalContract(TemporalMode.FIXED_OPERATOR, "arcana.risk.v0.2", "arcana.cal.coverage_a1", HORIZON,
                            2, (_matrix(),), _matrix(), (1., 0.), "per_generation_expected_offspring",
                            "expected_unsafe_activations", "none_after_initial", EVIDENCE,
                            "synthetic-coverage-oracle", "joint_generation_envelope", START, EXPIRY)


def _contract(method=CoverageMethod.UNION_BOUND, increment=None, temporal=None, probabilities=None):
    baseline = increment is not None and increment.scope is IncrementScope.CALIBRATION_ENVELOPE and increment.before.lower is not None
    ids = [f"current_upper:{i}:{j}" for i in range(2) for j in range(2)]
    if baseline:
        ids += [f"before_lower:{i}:{j}" for i in range(2) for j in range(2)]
    if temporal is not None:
        ids += ["temporal_joint_premises"]
    if method is CoverageMethod.JOINT_BOUND:
        ids = ["complete_family"]
    bounds = tuple(CoverageFailureBound(name, p) for name, p in zip(ids, probabilities or [1 / 128] * len(ids), strict=True))
    return CoverageContract("arcana.risk.v0.2", "arcana.cal.coverage_a1", HORIZON, _matrix(), method, bounds,
                            "synthetic-population", DESIGN, EVIDENCE, "synthetic-coverage-oracle",
                            CoverageSource.SYNTHETIC_FIXTURE, START, EXPIRY, "fixed_prespecified_family",
                            "direct_operator_bounds", "arbitrary",
                            increment_binding_hash=None if increment is None else increment.binding_hash,
                            before_lower_required=baseline,
                            temporal_binding_hash=None if temporal is None else temporal.binding_hash)


def _policy(**kwargs):
    return CoveragePolicy(**{"max_failure_probability": .125, "population_id": "synthetic-population",
                             "design_hash": DESIGN, "evidence_hash": EVIDENCE,
                             "evidence_source_id": "synthetic-coverage-oracle", "require_empirical_qualification": False, **kwargs})


def _evaluate(contract=None, policy=None, **kwargs):
    return evaluate_coverage(_contract() if contract is None else contract, _policy() if policy is None else policy,
                             **{"decision_time": NOW, "current_upper": _matrix(), **kwargs})


def _request(api, contract=None, policy=None, increment=None, temporal=None):
    contract = _contract(increment=increment, temporal=temporal) if contract is None else contract
    policy = _policy() if policy is None else policy
    budget = AutonomyBudget(EXPIRY, max_delta_rho_upper=10, coverage_policy=policy,
                            increment_scope=None if increment is None else increment.scope,
                            temporal_policy=None if temporal is None else TemporalPolicy(temporal.mode, temporal.generations, 10, 20))
    common = {"coverage": contract, "increment": increment, "temporal": temporal}
    profile = CalibrationProfile(contract.calibration_profile_id, contract.risk_model_version, CalibrationLevel.A1,
                                 HORIZON, ("static_conservative_prior",), EvidenceWindow(START, NOW, 3600), .99,
                                 CalibrationUncertainty(0, .1, .3), EdgeWeightPolicy(True, True, True),
                                 ("synthetic declared coverage only",), CertificationStatus.NON_CERTIFIABLE,
                                 evidence_hash=contract.evidence_hash)
    if api == "main":
        lower = increment.after.lower if increment is not None and increment.after.lower is not None else _matrix()
        return DecisionEvaluationRequest("arcana.risk.v0.2", profile, HORIZON, GRAPH, MatrixBundle(lower, _matrix(), _matrix()),
                                         .9, budget, NOW, **common)
    delta = SparseMatrixDelta(compute_sparse_delta_hash(graph_hash=GRAPH, decision_horizon=HORIZON, entries=()), GRAPH, HORIZON, ())
    current = _matrix([[.25, 2], [0, .125]]) if api == "uncertain_fallback" else _matrix()
    if api == "uncertain_fallback":
        common["coverage"] = replace(contract, current_upper=current)
    method = PositiveVectorMethod.FALLBACK_EXACT if api == "fallback" else PositiveVectorMethod.EPSILON_FLOOR
    return FastGateRequest(FastGateMode.EXACT_RECOMPUTE if api == "exact" else FastGateMode.PERRON_COLLATZ_BOUND,
                           "arcana.risk.v0.2", contract.calibration_profile_id, CalibrationLevel.A1, CalibrationLevel.A1,
                           HORIZON, NOW, GRAPH, current, delta, .9, budget,
                           positive_vector=PositiveVector((1., 1.), current.node_order, GRAPH, method, epsilon=.01),
                           evidence_hash=EVIDENCE, evidence_source_id="synthetic-coverage-oracle",
                           calibration_profile=profile, **common)


def _decision(request):
    return evaluate_decision(request) if isinstance(request, DecisionEvaluationRequest) else evaluate_fastgate(request).decision


def test_two_marginal_claims_do_not_inherit_joint_confidence():
    contract = _contract(probabilities=[.01, .01, 0, 0])
    with pytest.raises(ArcanaValidationError, match="coverage_failure_budget_exceeded"):
        _evaluate(contract, _policy(max_failure_probability=.01))
    metrics = _evaluate(contract)
    assert Fraction(metrics["coverage_probability_lower"]) <= 1 - 2 * Fraction(.01)
    assert metrics["coverage_probability_lower"] < .99


def test_arbitrary_dependence_exhaustive_finite_probability_space():
    universe = set(range(4))
    sets = [{i for i in universe if mask & (1 << i)} for mask in range(16)]
    for left, right in product(sets, repeat=2):
        p, q = len(left) / 4, len(right) / 4
        c = _contract(probabilities=[p, q, 0, 0])
        if p + q >= 1:
            with pytest.raises(ArcanaValidationError, match="coverage_failure_budget_exceeded"):
                _evaluate(c, _policy(max_failure_probability=.999))
        else:
            m = _evaluate(c, _policy(max_failure_probability=.999))
            truth = Fraction(len(universe - left - right), 4)
            assert Fraction(m["coverage_probability_lower"]) <= truth


def test_exact_sum_comparison_and_outward_rounding():
    c = _contract(probabilities=[.1, .2, 0, 0])
    exact = Fraction(.1) + Fraction(.2)
    with pytest.raises(ArcanaValidationError, match="coverage_failure_budget_exceeded"):
        _evaluate(c, _policy(max_failure_probability=.3))
    m = _evaluate(c, _policy(max_failure_probability=.5))
    assert Fraction(m["coverage_failure_probability_upper"]) >= exact
    assert Fraction(m["coverage_probability_lower"]) <= 1 - exact
    c = _contract(probabilities=[math.ulp(0.), 0, 0, 0])
    assert _evaluate(c)["coverage_probability_lower"] == math.nextafter(1., 0.)


def test_joint_bound_is_one_external_full_family_premise():
    m = _evaluate(_contract(CoverageMethod.JOINT_BOUND))
    assert m["coverage_method"] == "joint_bound"
    assert m["coverage_claim_count"] == 4
    assert m["coverage_probability_lower"] == 127 / 128
    assert m["coverage_empirical_qualification"] == "not_established"


@pytest.mark.parametrize("api", APIS)
def test_all_evaluator_paths_return_conditional_coverage(api):
    r = _request(api)
    d = _decision(r)
    assert_contract_gated(d)
    assert d.metrics["coverage_probability_lower"] == 31 / 32
    assert d.metrics["coverage_binding_hash"] == r.coverage.binding_hash
    assert d.metrics["coverage_policy_hash"] == coverage_policy_hash(r.autonomy_budget.coverage_policy)
    assert d.metrics["coverage_empirical_qualification"] == "not_established"
    if api in {"fallback", "uncertain_fallback"}:
        assert evaluate_fastgate(r).fastgate.mode is FastGateMode.EXACT_RECOMPUTE


@pytest.mark.parametrize("api", APIS)
def test_no_fallback_bypasses_failure_budget(api):
    r = _request(api, policy=_policy(max_failure_probability=1 / 64))
    d = _decision(r)
    assert d.verdict is Verdict.DENY
    assert d.metrics["issue_code"] == "coverage_failure_budget_exceeded"


@pytest.mark.parametrize("api", APIS)
@pytest.mark.parametrize("kind,code", [(CoverageSource.SYNTHETIC_FIXTURE, "coverage_synthetic_not_empirical"),
                                      (CoverageSource.EXTERNAL_UNVERIFIED, "coverage_empirical_review_required")])
def test_real_evidence_gate_cannot_be_opened_by_source_label(api, kind, code):
    r = _request(api, replace(_contract(), source_kind=kind), _policy(require_empirical_qualification=True))
    assert _decision(r).verdict is Verdict.DENY
    assert _decision(r).metrics["issue_code"] == code


@pytest.mark.parametrize("api", APIS)
@pytest.mark.parametrize("remove", ["contract", "policy", "both"])
def test_policy_and_contract_cannot_be_silently_dropped(api, remove):
    r = _request(api)
    if remove in {"contract", "both"}:
        r = replace(r, coverage=None)
    if remove in {"policy", "both"}:
        r = replace(r, autonomy_budget=replace(r.autonomy_budget, coverage_policy=None))
    d = _decision(r)
    if remove == "both":
        assert d.metrics["coverage_scope"] == "not_evaluated"
        assert "coverage_probability_lower" not in d.metrics
    else:
        assert d.verdict is Verdict.DENY
        assert d.metrics["issue_code"] == f"coverage_{remove}_missing"


@pytest.mark.parametrize("field,value,code", [
    ("population_id", "other", "coverage_population_mismatch"),
    ("design_hash", GRAPH, "coverage_design_hash_mismatch"),
    ("evidence_hash", GRAPH, "coverage_evidence_hash_mismatch"),
    ("evidence_source_id", "other", "coverage_evidence_source_mismatch"),
    ("risk_model_version", "arcana.risk.v9.0", "coverage_risk_model_mismatch"),
    ("calibration_profile_id", "arcana.cal.other", "coverage_calibration_profile_mismatch"),
    ("decision_horizon", replace(HORIZON, context="other"), "coverage_horizon_mismatch"),
    ("expires_at", NOW, "coverage_expired"),
    ("expires_at", "2026-09-28T10:04:59Z", "coverage_horizon_not_covered"),
    ("valid_from", "2026-09-28T10:00:01Z", "coverage_not_yet_valid"),
])
@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
def test_binding_and_validity_fail_specifically(api, field, value, code):
    r = _request(api)
    d = _decision(replace(r, coverage=replace(r.coverage, **{field: value})))
    assert d.verdict is Verdict.DENY
    assert d.metrics["issue_code"] == code


@pytest.mark.parametrize("change", ["values", "coordinates", "graph"])
@pytest.mark.parametrize("api", ["main", "exact", "collatz"])
def test_actual_matrix_binding_not_only_graph_hash(api, change):
    r = _request(api)
    matrix = _matrix([[.5, 0], [0, .125]]) if change == "values" else PropagationMatrix(
        _matrix().values, ("b", "a") if change == "coordinates" else ("a", "b"), EVIDENCE if change == "graph" else GRAPH)
    d = _decision(replace(r, coverage=replace(r.coverage, current_upper=matrix)))
    assert d.metrics["issue_code"] == "coverage_current_matrix_mismatch"


@pytest.mark.parametrize("api", ["main", "exact", "collatz", "fallback"])
@pytest.mark.parametrize("has_lower", [False, True])
def test_combined_increment_temporal_family_and_missing_claims(api, has_lower):
    inc, temporal = _increment(has_lower), _temporal()
    r = _request(api, increment=inc, temporal=temporal)
    d = _decision(r)
    assert d.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY
    assert d.metrics["coverage_claim_count"] == (9 if has_lower else 5)
    with pytest.raises(ArcanaValidationError, match="coverage_claim_missing"):
        replace(r.coverage, bounds=r.coverage.bounds[:-1])
    for field in ("increment_binding_hash", "temporal_binding_hash"):
        c = replace(r.coverage, **{field: GRAPH})
        assert _decision(replace(r, coverage=c)).metrics["issue_code"] == f"coverage_{field.replace('_hash', '')}_mismatch"
    if has_lower:
        c = replace(r.coverage, before_lower_required=False,
                    bounds=tuple(b for b in r.coverage.bounds if not b.claim_id.startswith("before_lower")))
        assert _decision(replace(r, coverage=c)).metrics["issue_code"] == "coverage_baseline_scope_mismatch"


def test_joint_premise_covers_entire_combined_family():
    inc, temporal = _increment(), _temporal()
    c = _contract(CoverageMethod.JOINT_BOUND, inc, temporal)
    assert _evaluate(c, increment=inc, temporal=temporal)["coverage_claim_count"] == 9
    with pytest.raises(ArcanaValidationError, match="coverage_temporal_binding_mismatch"):
        _evaluate(c, increment=inc)


def test_missing_temporal_event_and_zero_entries_cannot_be_ignored():
    c = _contract(temporal=_temporal())
    for claim in ("temporal_joint_premises", "current_upper:0:1"):
        with pytest.raises(ArcanaValidationError, match="coverage_claim_missing"):
            replace(c, bounds=tuple(b for b in c.bounds if b.claim_id != claim))


def test_standalone_binding_rejects_cross_contract_context():
    inc = replace(_increment(), calibration_profile_id="arcana.cal.other")
    c = _contract(increment=inc)
    with pytest.raises(ArcanaValidationError, match="coverage_increment_calibration_profile_id_mismatch"):
        _evaluate(c, increment=inc)
    inc = replace(_increment(), expires_at="2026-09-28T10:04:00Z")
    with pytest.raises(ArcanaValidationError, match="coverage_increment_window_incomplete"):
        _evaluate(_contract(increment=inc), increment=inc)


@pytest.mark.parametrize("field,value", [("method", "independent_product"), ("dependence", "independent"),
                                        ("factor_semantics", "marginal_factor_product"),
                                        ("selection_protocol", "adaptive_anytime"), ("source_kind", "empirically_approved")])
def test_unsupported_statistical_claims_are_rejected(field, value):
    with pytest.raises(ArcanaValidationError):
        replace(_contract(), **{field: value})
    raw = _contract().to_mapping()
    raw[field] = value
    with pytest.raises(ArcanaValidationError):
        parse_typed_document(raw)


@pytest.mark.parametrize("p", [-1., math.inf, -math.inf, math.nan, True, False, "0.1", None, 1.1, 10**400])
def test_invalid_probability_domains(p):
    with pytest.raises(ArcanaValidationError):
        CoverageFailureBound("current_upper:0:0", p)
    with pytest.raises(ArcanaValidationError):
        _policy(max_failure_probability=p)


@pytest.mark.parametrize("field,value", [("population_id", " "), ("design_hash", "bad"), ("evidence_hash", "bad"),
                                        ("evidence_source_id", "\t"), ("require_empirical_qualification", 1),
                                        ("max_failure_probability", 1)])
def test_policy_constructor_rejects_invalid_requirements(field, value):
    with pytest.raises(ArcanaValidationError):
        _policy(**{field: value})


def test_serialization_canonical_order_and_independent_snapshots():
    c = _contract()
    assert replace(c, bounds=tuple(reversed(c.bounds))).binding_hash == c.binding_hash
    assert CoverageContract.from_mapping(json.loads(json.dumps(c.to_mapping()))).to_mapping() == c.to_mapping()
    assert parse_typed_document(c.to_mapping()).binding_hash == c.binding_hash
    raw = c.to_mapping()
    raw["current_upper"]["values"][0][0] = .75
    assert c.current_upper.values[0][0] == .25
    with pytest.raises(ArcanaValidationError, match="coverage_binding_hash_mismatch"):
        CoverageContract.from_mapping(raw)


@pytest.mark.parametrize("field", ["population_id", "method", "evidence_hash", "current_upper", "bounds", "binding_hash"])
def test_typed_mutation_cannot_reuse_hash(field):
    c = _contract()
    changes = {"population_id": "other", "method": CoverageMethod.JOINT_BOUND, "evidence_hash": GRAPH,
               "current_upper": _matrix([[.5, 0], [0, .125]]), "bounds": (CoverageFailureBound("complete_family", 0),),
               "binding_hash": GRAPH}
    object.__setattr__(c, field, changes[field])
    with pytest.raises(ArcanaValidationError):
        _evaluate(c)


@pytest.mark.parametrize("target", ["root", "horizon", "matrix", "bound", "policy"])
def test_unknown_fields_not_silently_ignored(target):
    raw = _contract().to_mapping()
    selected = {"root": raw, "horizon": raw["decision_horizon"], "matrix": raw["current_upper"],
                "bound": raw["bounds"][0], "policy": dict(vars(_policy()))}[target]
    selected["unknown"] = "do not ignore"
    with pytest.raises(ArcanaValidationError):
        CoveragePolicy.from_mapping(selected) if target == "policy" else CoverageContract.from_mapping(raw)


def test_required_fields_null_empty_duplicate_and_wrong_family():
    raw = _contract().to_mapping()
    for key in raw:
        broken = copy.deepcopy(raw)
        del broken[key]
        with pytest.raises(ArcanaValidationError):
            CoverageContract.from_mapping(broken)
    for bounds in (None, "bad", [], [raw["bounds"][0]] * 4, [{"claim_id": "unrelated", "failure_probability_upper": 0}]):
        with pytest.raises(ArcanaValidationError):
            CoverageContract.from_mapping({**raw, "bounds": bounds})
    with pytest.raises(ArcanaValidationError, match="coverage_baseline_binding_missing"):
        replace(_contract(), before_lower_required=True)


def test_validity_boundary_and_date_overflow():
    c = replace(_contract(), expires_at="2026-09-28T10:05:00Z")
    assert _evaluate(c)["coverage_scope"] == "conditional_fixed_family"
    with pytest.raises(ArcanaValidationError, match="coverage_horizon_not_covered"):
        _evaluate(c, decision_time="2026-09-28T10:00:00.000001Z")
    c = replace(c, valid_from="9999-12-31T00:00:00Z", expires_at="9999-12-31T23:59:59Z")
    with pytest.raises(ArcanaValidationError, match="coverage_horizon_end_unrepresentable"):
        _evaluate(c, decision_time="9999-12-31T23:59:58Z")


def _cache(r):
    return FastGateCacheBinding(r.risk_model_version, r.calibration_profile_id, HORIZON.id, HORIZON.duration_seconds,
                                GRAPH, r.delta_upper.delta_hash, r.threshold, r.positive_vector.method, EXPIRY,
                                evidence_hash=EVIDENCE, evidence_source_id="synthetic-coverage-oracle",
                                coverage_binding_hash=r.coverage.binding_hash,
                                coverage_policy_hash=coverage_policy_hash(r.autonomy_budget.coverage_policy))


@pytest.mark.parametrize("api", ["exact", "collatz", "fallback", "uncertain_fallback"])
@pytest.mark.parametrize("change", ["contract", "policy", "missing_contract_hash", "missing_policy_hash", "downgrade"])
def test_cache_binds_contract_and_policy_without_fallback(api, change):
    r = _request(api)
    r = replace(r, cache_binding=_cache(r))
    assert_contract_gated(_decision(r))
    if change == "contract":
        r = replace(r, coverage=replace(r.coverage, expires_at="2026-09-28T11:01:00Z"))
    elif change == "policy":
        r = replace(r, autonomy_budget=replace(r.autonomy_budget, coverage_policy=_policy(max_failure_probability=.25)))
    elif change == "missing_contract_hash":
        r = replace(r, cache_binding=replace(r.cache_binding, coverage_binding_hash=None))
    elif change == "missing_policy_hash":
        r = replace(r, cache_binding=replace(r.cache_binding, coverage_policy_hash=None))
    elif change == "downgrade":
        r = replace(r, coverage=None, autonomy_budget=replace(r.autonomy_budget, coverage_policy=None))
    d = _decision(r)
    assert d.verdict is Verdict.DENY
    assert d.metrics["issue_code"].startswith("fastgate_cache_coverage_")


def test_old_artifacts_cannot_drop_scoped_policy():
    policy = _policy()
    budget = AutonomyBudget(EXPIRY, max_external_requests=0, coverage_policy=policy)
    with pytest.raises(ArcanaValidationError, match="legacy_artifact_coverage_policy_unsupported"):
        reject_legacy_scoped_budget(budget)
    parsed = AutonomyBudget.from_mapping({"expires_at": EXPIRY, "max_external_requests": 0, "coverage_policy": vars(policy)})
    assert parsed.coverage_policy == policy


def test_public_fixture_reproduces_synthetic_contract():
    fixture = load_typed_fixture(EXAMPLE_DIR / "coverage_union_bound.synthetic.json")
    assert isinstance(fixture, CoverageContract)
    assert fixture.to_mapping() == _contract().to_mapping()


def test_legacy_serializers_and_certificate_builder_reject_coverage():
    artifacts = build_demo_artifacts()
    context = replace(artifacts.context, autonomy_budget=replace(artifacts.context.autonomy_budget, coverage_policy=_policy()))
    profile = load_typed_fixture(EXAMPLE_DIR / "calibration_profile_a0.synthetic.json")
    for operation in (
        lambda: risk_context_to_mapping(context),
        lambda: validate_risk_context_semantics(context, now=datetime.fromisoformat("2026-06-09T00:00:00+00:00")),
        lambda: build_demo_non_certifiable_certificate(certificate_id="arcana-cert-coverage-negative", context=context,
                                                       calibration_profile=profile, issued_at="2026-06-09T00:00:00Z", caveats=("synthetic",)),
    ):
        with pytest.raises(ArcanaValidationError, match="legacy_artifact_coverage_policy_unsupported"):
            operation()


@pytest.mark.parametrize("api", APIS)
@pytest.mark.parametrize("field,value", [("max_failure_probability", math.nan), ("require_empirical_qualification", 0),
                                        ("population_id", " ")])
def test_mutated_policy_is_revalidated_on_every_path(api, field, value):
    r = _request(api)
    object.__setattr__(r.autonomy_budget.coverage_policy, field, value)
    assert _decision(r).verdict is Verdict.DENY


@pytest.mark.parametrize("api", APIS)
@pytest.mark.parametrize("field", ["coverage", "coverage_policy"])
def test_untyped_contract_or_policy_is_not_accepted(api, field):
    r = _request(api)
    if field == "coverage":
        r = replace(r, coverage=r.coverage.to_mapping())
    elif field == "coverage_policy":
        r = replace(r, autonomy_budget=replace(r.autonomy_budget, coverage_policy=vars(_policy())))
    d = _decision(r)
    assert d.verdict is Verdict.DENY
    assert d.metrics["issue_code"] == ("coverage_contract_invalid" if field == "coverage" else "coverage_policy_invalid")


def test_bounded_family_and_input_resource_limits():
    c = _contract()
    large = PropagationMatrix(np.zeros((65, 65)), tuple(str(i) for i in range(65)), GRAPH)
    with pytest.raises(ArcanaValidationError, match="coverage_node_limit_exceeded"):
        replace(c, current_upper=large)
    for values in (large.values.tolist(), [[0] * 65]):
        raw = c.to_mapping()
        raw["current_upper"]["values"] = values
        with pytest.raises(ArcanaValidationError, match="coverage_node_limit_exceeded"):
            CoverageContract.from_mapping(raw)
    with pytest.raises(ArcanaValidationError, match="coverage_term_count_invalid"):
        replace(c, bounds=c.bounds * 2049)
    raw = c.to_mapping()
    raw["bounds"] *= 2049
    with pytest.raises(ArcanaValidationError, match="coverage_term_count_invalid"):
        CoverageContract.from_mapping(raw)
    matrix = PropagationMatrix(np.zeros((64, 64)), tuple(str(i) for i in range(64)), GRAPH)
    ids = [f"{prefix}:{i}:{j}" for prefix in ("current_upper", "before_lower") for i in range(64) for j in range(64)]
    ids.append("temporal_joint_premises")
    full = replace(c, current_upper=matrix, increment_binding_hash=GRAPH, before_lower_required=True,
                   temporal_binding_hash=EVIDENCE, bounds=tuple(CoverageFailureBound(name, 0) for name in ids))
    assert len(full.claim_ids) == 8193
    assert CoverageContract.from_mapping(full.to_mapping()).binding_hash == full.binding_hash


def test_mutated_nested_matrix_fails_with_typed_validation():
    c = _contract()
    object.__setattr__(c.current_upper, "values", None)
    with pytest.raises(ArcanaValidationError):
        _evaluate(c)


@pytest.mark.parametrize("field", ["increment", "temporal"])
def test_standalone_invalid_cross_contract_and_matrix_are_rejected(field):
    with pytest.raises(ArcanaValidationError, match=f"coverage_{field}_invalid"):
        _evaluate(**{field: {}})
    with pytest.raises(ArcanaValidationError):
        _evaluate(current_upper=None)


def test_joint_bound_cannot_be_relabelled_marginal_or_self_reviewed():
    c = _contract(CoverageMethod.JOINT_BOUND)
    with pytest.raises(ArcanaValidationError, match="coverage_claim_unknown"):
        replace(c, bounds=(CoverageFailureBound("current_upper:0:0", .01),))
    raw = c.to_mapping()
    raw["empirically_reviewed"] = True
    with pytest.raises(ArcanaValidationError):
        validate_document(raw)
    with pytest.raises(ArcanaValidationError, match="coverage_field_unknown"):
        CoverageContract.from_mapping(raw)


def test_policy_is_not_an_autonomy_counter_and_requires_all_fields():
    with pytest.raises(ArcanaValidationError, match="autonomy_budget_empty"):
        AutonomyBudget.from_mapping({"expires_at": EXPIRY, "coverage_policy": vars(_policy())})
    for name in vars(_policy()):
        raw = dict(vars(_policy()))
        del raw[name]
        with pytest.raises(ArcanaValidationError, match=f"coverage_policy_{name}_missing"):
            CoveragePolicy.from_mapping(raw)


@pytest.mark.parametrize("mode", ["main_a0", "fastgate_a0", "observe"])
def test_empirical_requirement_is_not_bypassed_by_observe_or_a0(mode):
    r = _request("main" if mode == "main_a0" else "exact", policy=_policy(require_empirical_qualification=True))
    if mode == "main_a0":
        r = replace(r, calibration_profile=replace(r.calibration_profile, level=CalibrationLevel.A0, source=("synthetic_demo",)))
    elif mode == "fastgate_a0":
        a0 = replace(r.calibration_profile, level=CalibrationLevel.A0, source=("synthetic_demo",))
        r = replace(r, calibration_level=CalibrationLevel.A0, calibration_profile=a0)
    elif mode == "observe":
        r = replace(r, mode=FastGateMode.OBSERVE_ONLY)
    d = _decision(r)
    assert d.verdict is Verdict.DENY
    assert d.metrics["issue_code"] == "coverage_synthetic_not_empirical"
