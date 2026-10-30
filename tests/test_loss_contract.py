"""arcana.loss.v1: typed loss contract, DKW reference estimator and exact tail oracles (R3.4)."""

from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from fractions import Fraction
import json
from pathlib import Path
import random

import pytest

from admission_support import assert_contract_gated, complete_admission
import test_decision_reason_codes as main_api
import test_fastgate as fastgate_api
from arcana.decision import DecisionEvaluationRequest, evaluate_decision
from arcana.errors import ArcanaValidationError, LossMethod, LossSource, ReasonCode, SchemaVersion, Verdict
from arcana.fastgate import evaluate_fastgate
from arcana.loss_contract import (
    LOSS_CONTRACT_VERSION,
    LossContract,
    dkw_epsilon,
    loss_estimate,
    tail_metrics,
)
from arcana.model import AutonomyBudget, LossPolicy, reject_legacy_scoped_budget
from arcana.schemas import load_typed_fixture, validate_document

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "loss_dkw_empirical.synthetic.json"
ALPHA = Fraction(99, 100)
UNIT = "synthetic_eur"


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _context(request) -> dict:
    instant = datetime.fromisoformat(request.decision_time.replace("Z", "+00:00"))
    profile_id = (request.calibration_profile.profile_id if isinstance(request, DecisionEvaluationRequest)
                  else request.calibration_profile_id)
    return dict(risk_model_version=request.risk_model_version, calibration_profile_id=profile_id,
                decision_horizon=request.decision_horizon, valid_from=_iso(instant - timedelta(hours=1)),
                expires_at=_iso(instant + timedelta(hours=1)))


def _shift(request, *, seconds: int) -> str:
    return _iso(datetime.fromisoformat(request.decision_time.replace("Z", "+00:00")) + timedelta(seconds=seconds))


def _declared(request=None, **overrides) -> LossContract:
    fields = dict(**_context(request or main_api._request()), unit=UNIT, method=LossMethod.DECLARED_UPPER_BOUNDS,
                  failure_probability_upper=0.01, evidence_hash="sha256:" + "e" * 64, evidence_source_id="synthetic-loss",
                  source_kind=LossSource.SYNTHETIC_FIXTURE, aar_99_upper=100.0, aes_99_upper=150.0)
    return LossContract(**{**fields, **overrides})


def _dkw(sample, support=1.0, delta=0.05, request=None, **overrides) -> LossContract:
    fields = dict(**_context(request or main_api._request()), unit=UNIT, method=LossMethod.DKW_EMPIRICAL_UPPER,
                  failure_probability_upper=delta, evidence_hash="sha256:" + "e" * 64, evidence_source_id="synthetic-loss",
                  source_kind=LossSource.SYNTHETIC_FIXTURE, sample=tuple(sample), support_upper=support)
    return LossContract(**{**fields, **overrides})


def _policy(**overrides) -> LossPolicy:
    return LossPolicy(**{**dict(unit=UNIT, max_allowed_aar_99=200.0, max_allowed_aes_99=250.0,
                                max_failure_probability=0.05, require_empirical_qualification=False), **overrides})


def _with_loss(request, contract, policy=None):
    budget = replace(request.autonomy_budget, loss_policy=policy or _policy())
    return replace(request, loss=contract, loss_in_scope=True, loss_bounds=None, autonomy_budget=budget)


def _main(contract=None, policy=None, **request_overrides):
    request = complete_admission(main_api._request(**request_overrides))
    return _with_loss(request, contract or _declared(request), policy)


def _fastgate(contract=None, policy=None):
    request = complete_admission(fastgate_api._request())
    return _with_loss(request, contract or _declared(request), policy)


def _decide(request):
    return evaluate_decision(request) if isinstance(request, DecisionEvaluationRequest) else evaluate_fastgate(request).decision


def _code(callable_, *args, **kwargs) -> tuple[str, ReasonCode]:
    with pytest.raises(ArcanaValidationError) as error:
        callable_(*args, **kwargs)
    return error.value.code, error.value.primary_issue.reason_code


# Exact oracles


def _oracle(atoms: list[tuple[Fraction, Fraction]]) -> tuple[Fraction, Fraction]:
    """Acerbi-Tasche: ES = (E[L 1{L > q}] + q (P(L <= q) - alpha)) / (1 - alpha), q the lower alpha-quantile."""
    values = sorted({value for value, _ in atoms})
    cdf = {value: sum(mass for atom, mass in atoms if atom <= value) for value in values}
    quantile = next(value for value in values if cdf[value] >= ALPHA)
    above = sum(value * mass for value, mass in atoms if value > quantile)
    return quantile, (above + quantile * (cdf[quantile] - ALPHA)) / (1 - ALPHA)


def _random_law(generator: random.Random) -> list[tuple[Fraction, Fraction]]:
    size = generator.randrange(1, 12)
    weights = [generator.randrange(1, 200) for _ in range(size)]
    values = sorted(Fraction(generator.randrange(0, 50), generator.choice((1, 2, 4))) for _ in range(size))
    return [(value, Fraction(weight, sum(weights))) for value, weight in zip(values, weights)]


def test_tail_metrics_match_the_acerbi_tasche_oracle() -> None:
    generator = random.Random(20261031)
    for _ in range(500):
        law = _random_law(generator)
        assert tail_metrics(law) == _oracle(law), law


@pytest.mark.parametrize("law,expected", [
    ([(Fraction(5), Fraction(1))], (Fraction(5), Fraction(5))),
    ([(Fraction(0), ALPHA), (Fraction(10), 1 - ALPHA)], (Fraction(0), Fraction(10))),  # atom ends exactly at alpha
    ([(Fraction(0), Fraction(98, 100)), (Fraction(10), Fraction(2, 100))], (Fraction(10), Fraction(10))),
    ([(Fraction(1), Fraction(1, 2)), (Fraction(1), Fraction(1, 2))], (Fraction(1), Fraction(1))),  # ties
])
def test_tail_metrics_handle_atoms_and_ties(law, expected) -> None:
    assert tail_metrics(law) == expected


def test_dkw_epsilon_is_a_rational_upper_bound() -> None:
    for n in (1, 7, 100, 18_445, 100_000):
        for delta in (1e-9, 0.01, 0.05, 0.5, 0.999):
            epsilon = dkw_epsilon(n, delta)
            with localcontext() as context:
                context.prec = 80
                exact_square = (2 / Decimal(delta)).ln() / (2 * n)
                assert Decimal(epsilon.numerator) ** 2 >= exact_square * Decimal(epsilon.denominator) ** 2 or epsilon == 1
            assert epsilon <= 1


# DKW estimator properties


def _uniform(generator: random.Random, n: int) -> list[float]:
    return [generator.random() for _ in range(n)]


def test_estimator_bounds_are_ordered_and_capped_by_support() -> None:
    generator = random.Random(7)
    for n in (1, 50, 3000):
        estimate = loss_estimate(_dkw(_uniform(generator, n)))
        assert estimate.aar_99_empirical <= estimate.aar_99_upper <= 1
        assert estimate.aes_99_empirical <= estimate.aes_99_upper <= 1
        assert estimate.aar_99_upper <= estimate.aes_99_upper
        assert estimate.aar_99_empirical <= estimate.aes_99_empirical


def test_small_samples_fall_back_to_the_support() -> None:
    estimate = loss_estimate(_dkw([0.1] * 100, support=7.0))
    assert estimate.epsilon > 1 - ALPHA
    assert (estimate.aar_99_upper, estimate.aes_99_upper) == (7, 7)


def test_estimator_is_monotone_in_confidence_and_in_the_sample() -> None:
    generator = random.Random(11)
    sample = _uniform(generator, 25_000)
    loose, tight = loss_estimate(_dkw(sample, delta=0.2)), loss_estimate(_dkw(sample, delta=0.001))
    assert loose.aar_99_upper <= tight.aar_99_upper and loose.aes_99_upper <= tight.aes_99_upper
    raised = sample.copy()
    for index in generator.sample(range(len(raised)), 500):
        raised[index] = min(1.0, raised[index] + 0.25)
    higher = loss_estimate(_dkw(raised, delta=0.2))
    assert higher.aar_99_upper >= loose.aar_99_upper and higher.aes_99_upper >= loose.aes_99_upper


def test_estimator_is_translation_equivariant() -> None:
    sample = [index / 1024 for index in range(20_000)]
    base = loss_estimate(_dkw(sample, support=32.0))
    shifted = loss_estimate(_dkw([value + 8 for value in sample], support=40.0))
    assert shifted.aar_99_upper == base.aar_99_upper + 8
    assert shifted.aes_99_upper == base.aes_99_upper + 8
    assert shifted.epsilon == base.epsilon


def test_bounds_cover_a_known_law_in_repeated_draws() -> None:
    # Uniform[0, 1]: AaR_99 = 0.99, AES_99 = 0.995. The guarantee allows failures with probability 0.1.
    generator = random.Random(20261030)
    failures = 0
    for _ in range(8):
        estimate = loss_estimate(_dkw(_uniform(generator, 20_000), delta=0.1))
        failures += estimate.aar_99_upper < Fraction(99, 100) or estimate.aes_99_upper < Fraction(995, 1000)
        assert estimate.aar_99_upper < 1  # informative at this sample size
    assert failures == 0


# Contract validation


@pytest.mark.parametrize("overrides,code", [
    ({"alpha": 0.95}, "loss_alpha_unsupported"),
    ({"quantile_convention": "upper_quantile"}, "loss_quantile_convention_unsupported"),
    ({"aes_99_upper": 90.0}, "loss_tail_order_invalid"),
    ({"aar_99_upper": -1.0}, "number_invalid"),
    ({"failure_probability_upper": 1.0}, "loss_failure_probability_vacuous"),
    ({"sample": (1.0,)}, "loss_sample_unexpected"),
    ({"unit": "  "}, "loss_unit_blank"),
    ({"method": "bootstrap"}, "enum_invalid"),
    ({"expires_at": "2026-06-08T00:00:00Z"}, "loss_window_invalid"),
])
def test_declared_contract_validation(overrides, code) -> None:
    assert _code(_declared, **overrides)[0] == code


@pytest.mark.parametrize("sample,overrides,code", [
    ((0.5,), {"failure_probability_upper": 0.0}, "loss_failure_probability_invalid"),
    ((0.5, 1.5), {}, "loss_sample_outside_support"),
    ((), {}, "loss_sample_size_invalid"),
    ((0.5, float("inf")), {}, "number_invalid"),
    ((0.5,), {"aar_99_upper": 1.0}, "loss_declared_bounds_unexpected"),
    ((0.5,), {"support_upper": None}, "number_invalid"),
])
def test_estimator_contract_validation(sample, overrides, code) -> None:
    assert _code(_dkw, sample, **overrides)[0] == code


def test_contract_round_trip_and_tamper_detection() -> None:
    for contract in (_declared(), _dkw([0.25, 0.5, 0.75])):
        mapping = contract.to_mapping()
        assert LossContract.from_mapping(mapping) == contract
        validate_document(mapping, SchemaVersion.LOSS_V1)
        tampered = {**mapping, "unit": "other_units"}
        assert _code(LossContract.from_mapping, tampered)[0] == "loss_binding_hash_mismatch"
    assert _code(LossContract.from_mapping, {**_declared().to_mapping(), "extra": 1})[0] == "loss_field_unknown"


def test_public_example_parses_and_validates() -> None:
    contract = load_typed_fixture(EXAMPLE)
    assert isinstance(contract, LossContract)
    assert contract.schema_version == LOSS_CONTRACT_VERSION
    assert json.loads(EXAMPLE.read_text())["binding_hash"] == contract.binding_hash


def test_policy_validation_and_legacy_artifacts() -> None:
    assert _code(_policy, max_failure_probability=1.0)[0] == "loss_policy_vacuous"
    assert _code(_policy, unit=" ")[0] == "loss_policy_unit_blank"
    assert _code(LossPolicy.from_mapping, {**vars(_policy()), "extra": 1})[0] == "loss_policy_field_unknown"
    budget = AutonomyBudget(expires_at="2026-06-09T00:30:00Z", max_external_requests=1, loss_policy=_policy())
    assert _code(reject_legacy_scoped_budget, budget)[0] == "legacy_artifact_loss_policy_unsupported"


# Binding and admission


@pytest.mark.parametrize("build", [_main, _fastgate], ids=["main", "fastgate"])
def test_declared_contract_reaches_admission_with_loss_metrics(build) -> None:
    decision = _decide(build())
    assert decision.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY, decision
    assert decision.metrics["admission_contract_gaps"] == ()
    if build is _main:
        assert decision.metrics["loss_contract_version"] == LOSS_CONTRACT_VERSION
        assert decision.metrics["loss_unit"] == UNIT
        assert decision.metrics["loss_empirical_qualification"] == "not_established"


def test_estimator_contract_is_compared_with_the_policy() -> None:
    sample = [index / 20_000 for index in range(20_000)]
    request = main_api._request()
    tight = _policy(max_allowed_aar_99=0.9, max_allowed_aes_99=1.0)
    decision = evaluate_decision(_main(_dkw(sample, request=request), tight))
    assert decision.reason_codes == (ReasonCode.DENY_AAR_UPPER_BOUND,)
    assert decision.metrics["issue_code"] == "aar_upper_bound_exceeded"
    assert decision.metrics["aar_99_upper"] > decision.metrics["aar_99_empirical"]
    allowed = evaluate_decision(_main(_dkw(sample, request=request), _policy(max_allowed_aar_99=1.0, max_allowed_aes_99=1.0)))
    assert allowed.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY
    assert allowed.metrics["loss_sample_size"] == 20_000


@pytest.mark.parametrize("build", [_main, _fastgate], ids=["main", "fastgate"])
def test_legacy_loss_bounds_stay_observe_only(build) -> None:
    request = build()
    legacy = replace(request, loss=None, loss_bounds=main_api._loss(),
                     autonomy_budget=replace(request.autonomy_budget, loss_policy=None))
    assert_contract_gated(_decide(legacy), {"loss_contract_missing"})


@pytest.mark.parametrize("mutate,code,reason", [
    (lambda r: replace(r, autonomy_budget=replace(r.autonomy_budget, loss_policy=None)), "loss_policy_missing", ReasonCode.DENY_LOSS_MODEL_INVALID),
    (lambda r: replace(r, loss_in_scope=False), "loss_contract_out_of_scope", ReasonCode.DENY_LOSS_MODEL_INVALID),
    (lambda r: replace(r, loss_bounds=main_api._loss()), "loss_scalar_override_forbidden", ReasonCode.DENY_LOSS_MODEL_INVALID),
    (lambda r: replace(r, loss=None), "loss_contract_missing", ReasonCode.DENY_LOSS_MODEL_INVALID),
    (lambda r: replace(r, loss=replace(r.loss, risk_model_version="arcana.risk.v0.3")), "loss_risk_model_mismatch",
     ReasonCode.DENY_RISK_MODEL_UNSUPPORTED),
    (lambda r: replace(r, loss=replace(r.loss, calibration_profile_id="arcana.cal.other")), "loss_calibration_profile_mismatch",
     ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
    (lambda r: replace(r, loss=replace(r.loss, decision_horizon=main_api._horizon(seconds=60))), "loss_horizon_mismatch",
     ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
    (lambda r: replace(r, loss=replace(r.loss, unit="usd")), "loss_unit_mismatch", ReasonCode.DENY_LOSS_MODEL_INVALID),
    (lambda r: replace(r, loss=replace(r.loss, failure_probability_upper=0.2)), "loss_failure_budget_exceeded",
     ReasonCode.DENY_LOSS_MODEL_INVALID),
    (lambda r: replace(r, autonomy_budget=replace(r.autonomy_budget, loss_policy=_policy(require_empirical_qualification=True))),
     "loss_empirical_review_required", ReasonCode.DENY_LOSS_MODEL_INVALID),
    (lambda r: replace(r, loss=replace(r.loss, expires_at=_shift(r, seconds=60))), "loss_horizon_not_covered",
     ReasonCode.DENY_CONTEXT_STALE),
    (lambda r: replace(r, loss=replace(r.loss, expires_at=_shift(r, seconds=0))), "loss_expired", ReasonCode.DENY_CONTEXT_STALE),
    (lambda r: replace(r, loss=replace(r.loss, valid_from=_shift(r, seconds=1))), "loss_not_yet_valid", ReasonCode.DENY_CONTEXT_STALE),
])
@pytest.mark.parametrize("build", [_main, _fastgate], ids=["main", "fastgate"])
def test_contract_binding_failures(build, mutate, code, reason) -> None:
    decision = _decide(mutate(build()))
    assert decision.verdict is Verdict.DENY, decision
    assert (decision.metrics["issue_code"], decision.reason_codes[0]) == (code, reason)


def test_tampered_contract_is_rejected_by_the_evaluator() -> None:
    request = _main()
    object.__setattr__(request.loss, "aar_99_upper", 1.0)
    decision = evaluate_decision(request)
    assert decision.metrics["issue_code"] == "loss_binding_hash_mismatch"
