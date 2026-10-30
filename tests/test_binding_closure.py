"""FastGate cache and certificate bindings for the profile evidence hash, confidence floor and loss contract."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from admission_support import complete_admission
import test_fastgate as fastgate_api
from test_loss_contract import _declared, _policy, _with_loss
from arcana.certificate import (
    BoundedAutonomyCertificate,
    CertificateCalibrationProfile,
    CertificateType,
    certificate_to_mapping,
)
from arcana.artifacts import validate_certificate_semantics
from arcana.errors import (
    ArcanaValidationError,
    CalibrationLevel,
    CertificationStatus,
    FastGateMode,
    ReasonCode,
    SchemaVersion,
    Verdict,
)
from arcana.fastgate import FastGateCacheBinding, evaluate_fastgate
from arcana.loss_contract import loss_policy_hash
from arcana.model import EvidenceReference, LossBounds, RhoInterval
from arcana.schemas import parse_typed_document, validate_document
from arcana.temporal import temporal_policy_hash

PROFILE_HASH = "sha256:" + "c" * 64


def _request(*, loss: bool = False):
    request = complete_admission(fastgate_api._request(mode=FastGateMode.PERRON_COLLATZ_BOUND,
                                                       positive_vector=fastgate_api._positive_vector()))
    return _with_loss(request, _declared(request)) if loss else request


def _cache(request) -> FastGateCacheBinding:
    """A cache binding that matches every field of the request."""
    budget, loss = request.autonomy_budget, request.loss
    return FastGateCacheBinding(
        request.risk_model_version, request.calibration_profile_id, request.decision_horizon.id,
        request.decision_horizon.duration_seconds, request.graph_hash, request.delta_upper.delta_hash, request.threshold,
        request.positive_vector.method, "2026-06-09T00:30:00Z", evidence_hash=request.evidence_hash,
        increment_scope=request.increment.scope, increment_binding_hash=request.increment.binding_hash,
        temporal_binding_hash=request.temporal.binding_hash, temporal_policy_hash=temporal_policy_hash(budget.temporal_policy),
        calibration_profile_evidence_hash=request.calibration_profile.evidence_hash,
        min_calibration_confidence=request.min_calibration_confidence,
        loss_binding_hash=None if loss is None else loss.binding_hash,
        loss_policy_hash=None if loss is None else loss_policy_hash(budget.loss_policy),
    )


@pytest.mark.parametrize("loss", [False, True], ids=["no_loss", "loss"])
def test_matching_cache_is_accepted(loss) -> None:
    request = _request(loss=loss)
    evaluation = evaluate_fastgate(replace(request, cache_binding=_cache(request)))
    assert evaluation.decision.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY, evaluation.decision


@pytest.mark.parametrize("change,code,reason", [
    (lambda r: replace(r, calibration_profile=replace(r.calibration_profile, evidence_hash="sha256:" + "9" * 64)),
     "fastgate_cache_calibration_profile_evidence_hash_mismatch", ReasonCode.DENY_CONTEXT_STALE),
    (lambda r: replace(r, min_calibration_confidence=0.6), "fastgate_cache_min_calibration_confidence_mismatch",
     ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
    (lambda r: replace(r, loss=_declared(r, aes_99_upper=160.0)), "fastgate_cache_loss_binding_hash_mismatch",
     ReasonCode.DENY_CONTEXT_STALE),
    (lambda r: replace(r, autonomy_budget=replace(r.autonomy_budget, loss_policy=_policy(max_allowed_aar_99=190.0))),
     "fastgate_cache_loss_policy_hash_mismatch", ReasonCode.DENY_CONTEXT_STALE),
    (lambda r: replace(r, loss=None, loss_in_scope=False, autonomy_budget=replace(r.autonomy_budget, loss_policy=None)),
     "fastgate_cache_loss_binding_hash_mismatch", ReasonCode.DENY_CONTEXT_STALE),
])
def test_cache_is_stale_when_a_bound_input_changes(change, code, reason) -> None:
    request = _request(loss=True)
    decision = evaluate_fastgate(change(replace(request, cache_binding=_cache(request)))).decision
    assert decision.verdict is Verdict.DENY, decision
    assert (decision.metrics["issue_code"], decision.reason_codes[0]) == (code, reason)


def _certificate(profile_hash: str | None) -> BoundedAutonomyCertificate:
    return BoundedAutonomyCertificate(
        certificate_id="arcana-cert-binding-closure-unit-test",
        certificate_type=CertificateType.BOUNDED_AUTONOMY_CERTIFICATE,
        risk_model_version="arcana.risk.v0.2",
        calibration_profile=CertificateCalibrationProfile(
            profile_id="arcana.cal.binding_a2", level=CalibrationLevel.A2, source=("controlled_redteam",), confidence=0.8,
            certification_status=CertificationStatus.CERTIFIABLE_UNDER_PROFILE, evidence_hash=profile_hash,
        ),
        decision_horizon=fastgate_api._horizon(),
        graph_hash=fastgate_api.GRAPH_HASH,
        verdict=Verdict.ALLOW_BOUNDED_AUTONOMY,
        rho_interval=RhoInterval(lower=0.2, mean=0.25, upper=0.3, threshold=0.8),
        loss_bounds=LossBounds(100.0, 120.0, 200.0, 250.0),
        evidence=EvidenceReference(source_type="controlled_test", source_id="binding-closure-controlled-test",
                                   synthetic=False, evidence_hash="sha256:" + "a" * 64),
        reason_codes=(ReasonCode.ALLOW_BOUNDED_AUTONOMY,),
        issued_at="2026-06-09T00:10:00Z",
        caveats=("controlled-test unit validation only; no commercial certificate issuance",),
        expires_at="2026-06-09T01:00:00Z",
    )


NOW = datetime(2026, 6, 9, 0, 20, tzinfo=timezone.utc)


def test_certificate_carries_the_profile_evidence_hash() -> None:
    certificate = _certificate(PROFILE_HASH)
    mapping = certificate_to_mapping(certificate)
    assert mapping["calibration_profile"]["evidence_hash"] == PROFILE_HASH
    validate_document(mapping, SchemaVersion.CERTIFICATE_V02)
    parsed = parse_typed_document(mapping)
    assert parsed.calibration_profile.evidence_hash == PROFILE_HASH
    assert validate_certificate_semantics(certificate, now=NOW) is certificate


def test_allow_like_certificate_requires_the_profile_evidence_hash() -> None:
    certificate = _certificate(None)
    assert "evidence_hash" not in certificate_to_mapping(certificate)["calibration_profile"]
    with pytest.raises(ArcanaValidationError) as error:
        validate_certificate_semantics(certificate, now=NOW)
    assert error.value.code == "certificate_profile_evidence_hash_missing"
    assert error.value.primary_issue.reason_code is ReasonCode.DENY_CALIBRATION_INSUFFICIENT


def test_malformed_certificate_profile_hash_is_rejected() -> None:
    mapping = certificate_to_mapping(_certificate(PROFILE_HASH))
    mapping["calibration_profile"]["evidence_hash"] = "sha256:short"
    with pytest.raises(ArcanaValidationError):
        validate_document(mapping, SchemaVersion.CERTIFICATE_V02)
    with pytest.raises(ArcanaValidationError) as error:
        BoundedAutonomyCertificate.from_mapping(mapping)
    assert error.value.code == "sha256_hash_invalid"
