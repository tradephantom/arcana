"""F6/F13: profile confidence floor, profile-rho coherence, profile evidence hash, AES >= AaR."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from admission_support import PROFILE_EVIDENCE_HASH, assert_contract_gated, complete_admission
import test_decision_reason_codes as main_api
import test_fastgate as fastgate_api
from arcana.calibration import DEFAULT_MIN_CALIBRATION_CONFIDENCE, CalibrationProfile, CalibrationUncertainty
from arcana.decision import evaluate_decision
from arcana.errors import ArcanaValidationError, CalibrationLevel, FastGateMode, ReasonCode, SchemaVersion, Verdict
from arcana.fastgate import evaluate_fastgate
from arcana.matrices import MatrixBundle
from arcana.model import LossBounds
from arcana.schemas import validate_document

PROFILE_EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "calibration_profile_a0.synthetic.json"


def _main(**overrides):
    return complete_admission(main_api._request(**overrides))


def _exact(**overrides):
    return complete_admission(fastgate_api._request(**overrides))


def _collatz(**overrides):
    return _exact(mode=FastGateMode.PERRON_COLLATZ_BOUND, positive_vector=fastgate_api._positive_vector(), **overrides)


APIS = [pytest.param(_main, id="main"), pytest.param(_exact, id="exact"), pytest.param(_collatz, id="collatz")]


def _decide(request):
    return evaluate_decision(request) if hasattr(request, "matrix_bundle") else evaluate_fastgate(request).decision


def _with_profile(request, **changes):
    return replace(request, calibration_profile=replace(request.calibration_profile, **changes))


def _rho_upper(decision) -> float:
    for key in ("rho_upper", "fastgate_upper_bound", "rho_after_upper"):
        if key in decision.metrics:
            return decision.metrics[key]
    raise AssertionError(decision.metrics)


def _assert_denied(decision, reason_code: ReasonCode, issue_code: str) -> None:
    assert decision.verdict is Verdict.DENY, decision
    assert decision.reason_codes == (reason_code,)
    assert decision.metrics["issue_code"] == issue_code


@pytest.mark.parametrize("build", APIS)
def test_complete_requests_are_admitted(build) -> None:
    decision = _decide(build())
    assert decision.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY
    assert _rho_upper(decision) > 0


# F6: confidence floor


@pytest.mark.parametrize("build", APIS)
def test_audit_r2_zero_confidence_profile_is_denied(build) -> None:
    decision = _decide(_with_profile(build(), confidence=0.0))
    _assert_denied(decision, ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "calibration_confidence_below_minimum")
    assert decision.metrics["calibration_confidence"] == 0.0
    assert decision.metrics["min_calibration_confidence"] == DEFAULT_MIN_CALIBRATION_CONFIDENCE


@pytest.mark.parametrize("build", APIS)
def test_confidence_floor_is_inclusive_and_configurable(build) -> None:
    request = _with_profile(build(), confidence=0.8)
    assert _decide(replace(request, min_calibration_confidence=0.8)).verdict is Verdict.ALLOW_BOUNDED_AUTONOMY
    raised = _decide(replace(request, min_calibration_confidence=0.9))
    _assert_denied(raised, ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "calibration_confidence_below_minimum")


@pytest.mark.parametrize("build", APIS)
@pytest.mark.parametrize("minimum", [0, -0.1, 1.5, float("nan"), "0.5"])
def test_confidence_floor_must_be_a_positive_probability(build, minimum) -> None:
    decision = _decide(replace(build(), min_calibration_confidence=minimum))
    assert decision.verdict is Verdict.DENY
    assert decision.reason_codes == (ReasonCode.DENY_MODEL_INPUT_INVALID,)


def test_a0_profile_stays_observe_only_whatever_its_confidence() -> None:
    profile = replace(main_api._profile(level=CalibrationLevel.A0, source=("synthetic_demo",)), confidence=0.0)
    decision = evaluate_decision(_main(calibration_profile=profile))
    assert decision.verdict is Verdict.OBSERVE_ONLY
    assert decision.metrics["issue_code"] == "a0_observe_only"


# F6: profile <-> rho coherence


@pytest.mark.parametrize("build", APIS)
def test_rho_above_the_profile_interval_is_denied(build) -> None:
    request = build()
    rho = _rho_upper(_decide(request))
    decision = _decide(_with_profile(request, uncertainty=CalibrationUncertainty(0, rho / 4, rho / 2)))
    _assert_denied(decision, ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "rho_upper_above_calibration_profile")
    assert decision.metrics["calibration_rho_upper"] == rho / 2


@pytest.mark.parametrize("build", APIS)
def test_rho_below_the_profile_interval_is_denied(build) -> None:
    request = build()
    floor = min(1.0, 2 * _rho_upper(_decide(request)))
    decision = _decide(_with_profile(request, uncertainty=CalibrationUncertainty(floor, floor, floor)))
    _assert_denied(decision, ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "rho_upper_below_calibration_profile")
    assert decision.metrics["calibration_rho_lower"] == floor


@pytest.mark.parametrize("build", APIS)
def test_profile_interval_endpoints_are_coherent(build) -> None:
    request = build()
    rho = _rho_upper(_decide(request))
    for interval in ((rho, rho, rho), (0, 0, rho), (rho, rho, 1)):
        decision = _decide(_with_profile(request, uncertainty=CalibrationUncertainty(*interval)))
        assert decision.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY, interval


def test_audit_r2_profile_claiming_zero_rho_is_incoherent() -> None:
    request = _with_profile(_main(), uncertainty=CalibrationUncertainty(0, 0, 0))
    _assert_denied(evaluate_decision(request), ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "rho_upper_above_calibration_profile")


def test_acyclic_operator_below_the_calibrated_floor_is_denied() -> None:
    values = [[0.0, 1e6, 0.0], [0.0, 0.0, 1e6], [0.0, 0.0, 0.0]]
    dag = MatrixBundle.from_values(values, values, values, node_order=("agent", "tool", "external"),
                                   graph_hash=main_api.GRAPH_HASH)
    request = main_api._request(matrix_bundle=dag)
    assert request.calibration_profile.uncertainty.rho_lower > 0
    decision = evaluate_decision(request)
    assert decision.metrics["rho_upper"] == 0.0
    _assert_denied(decision, ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "rho_upper_below_calibration_profile")


def test_threshold_breach_keeps_its_own_reason_code() -> None:
    # Legacy request (no temporal contract) so the spectral threshold is the first failing check.
    decision = evaluate_decision(main_api._request(matrix_bundle=main_api._matrices(high_rho=True)))
    assert decision.metrics["rho_upper"] > main_api._profile().uncertainty.rho_upper
    _assert_denied(decision, ReasonCode.DENY_RHO_UPPER_BOUND, "rho_upper_bound_exceeded")


# F6: profile evidence hash


@pytest.mark.parametrize("build", APIS)
def test_profile_without_evidence_hash_is_observe_only(build) -> None:
    decision = _decide(_with_profile(build(), evidence_hash=None))
    assert_contract_gated(decision, {"calibration_evidence_hash_missing"})
    assert decision.metrics["admission_contract_gaps"] == ("calibration_evidence_hash_missing",)


@pytest.mark.parametrize("build", APIS)
def test_malformed_profile_evidence_hash_is_denied(build) -> None:
    decision = _decide(_with_profile(build(), evidence_hash="sha256:not-a-digest"))
    _assert_denied(decision, ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "sha256_hash_invalid")


def test_profile_mapping_carries_a_schema_valid_evidence_hash() -> None:
    mapping = json.loads(PROFILE_EXAMPLE.read_text())
    assert CalibrationProfile.from_mapping(mapping).evidence_hash is None
    mapping["evidence_hash"] = PROFILE_EVIDENCE_HASH
    validate_document(mapping, SchemaVersion.CALIBRATION_PROFILE_V02)
    assert CalibrationProfile.from_mapping(mapping).evidence_hash == PROFILE_EVIDENCE_HASH
    mapping["evidence_hash"] = "md5:0123"
    with pytest.raises(ArcanaValidationError):
        validate_document(mapping, SchemaVersion.CALIBRATION_PROFILE_V02)
    with pytest.raises(ArcanaValidationError) as error:
        CalibrationProfile.from_mapping(mapping)
    assert error.value.code == "sha256_hash_invalid"


# F13: AES >= AaR


@pytest.mark.parametrize("build", APIS)
def test_audit_r7_aes_below_aar_is_an_invalid_loss_model(build) -> None:
    bounds = LossBounds(aar_99_upper=1000, aes_99_upper=1, max_allowed_aar_99=1000, max_allowed_aes_99=10)
    decision = _decide(replace(build(), loss_in_scope=True, loss_bounds=bounds))
    _assert_denied(decision, ReasonCode.DENY_LOSS_MODEL_INVALID, "loss_tail_order_invalid")


@pytest.mark.parametrize("build", APIS)
def test_aes_equal_to_aar_is_a_valid_loss_model(build) -> None:
    bounds = LossBounds(aar_99_upper=100, aes_99_upper=100, max_allowed_aar_99=200, max_allowed_aes_99=200)
    decision = _decide(replace(build(), loss_in_scope=True, loss_bounds=bounds))
    assert decision.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY


def test_invalid_loss_model_is_reported_before_the_rho_threshold() -> None:
    bounds = LossBounds(aar_99_upper=100, aes_99_upper=99, max_allowed_aar_99=200, max_allowed_aes_99=250)
    request = main_api._request(matrix_bundle=main_api._matrices(high_rho=True), loss_bounds=bounds)
    _assert_denied(evaluate_decision(request), ReasonCode.DENY_LOSS_MODEL_INVALID, "loss_tail_order_invalid")


def test_loss_mapping_rejects_aes_below_aar() -> None:
    with pytest.raises(ArcanaValidationError) as error:
        LossBounds.from_mapping({"aar_99_upper": 10, "aes_99_upper": 9, "max_allowed_aar_99": 20, "max_allowed_aes_99": 20})
    assert error.value.code == "loss_tail_order_invalid"
    assert error.value.primary_issue.reason_code is ReasonCode.DENY_LOSS_MODEL_INVALID
