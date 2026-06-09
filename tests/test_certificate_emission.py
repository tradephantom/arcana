from __future__ import annotations

import dataclasses

import pytest

from arcana.calibration import CalibrationProfile
from arcana.certificate import BoundedAutonomyCertificate, build_demo_non_certifiable_certificate
from arcana.demo import CERTIFICATE_ARTIFACT_LABEL, CONTEXT_ARTIFACT_LABEL, build_demo_artifacts
from arcana.errors import ArcanaValidationError, CalibrationLevel, CertificationStatus, ReasonCode, SchemaVersion, Verdict
from arcana.model import RiskContext
from arcana.schemas import EXAMPLE_DIR, load_typed_fixture, parse_typed_document, validate_document


def test_demo_artifacts_emit_schema_valid_context_and_certificate() -> None:
    artifacts = build_demo_artifacts()
    payload = artifacts.to_mapping()
    context_document = payload["artifacts"][CONTEXT_ARTIFACT_LABEL]
    certificate_document = payload["artifacts"][CERTIFICATE_ARTIFACT_LABEL]

    validate_document(context_document, SchemaVersion.CONTEXT_V02)
    validate_document(certificate_document, SchemaVersion.CERTIFICATE_V02)

    assert isinstance(parse_typed_document(context_document), RiskContext)
    assert isinstance(parse_typed_document(certificate_document), BoundedAutonomyCertificate)


def test_demo_certificate_is_a0_non_certifiable_observe_only() -> None:
    certificate = build_demo_artifacts().certificate

    assert certificate.verdict is Verdict.OBSERVE_ONLY
    assert certificate.calibration_profile.level is CalibrationLevel.A0
    assert certificate.calibration_profile.certification_status is CertificationStatus.NON_CERTIFIABLE
    assert ReasonCode.INFO_A0_NON_CERTIFIABLE in certificate.reason_codes
    assert ReasonCode.INFO_SYNTHETIC_FIXTURE in certificate.reason_codes


def test_demo_certificate_builder_rejects_non_a0_profile() -> None:
    calibration_profile = load_typed_fixture(EXAMPLE_DIR / "calibration_profile_a0.synthetic.json")
    assert isinstance(calibration_profile, CalibrationProfile)
    non_a0_profile = dataclasses.replace(
        calibration_profile,
        level=CalibrationLevel.A1,
        certification_status=CertificationStatus.CERTIFIABLE_UNDER_PROFILE,
    )

    with pytest.raises(ArcanaValidationError) as exc_info:
        build_demo_non_certifiable_certificate(
            certificate_id="arcana-cert-invalid-a1-demo",
            context=build_demo_artifacts().context,
            calibration_profile=non_a0_profile,
            issued_at="2026-06-09T00:00:00Z",
            caveats=("invalid non-A0 demo certificate",),
        )

    assert exc_info.value.reason_code is ReasonCode.DENY_CALIBRATION_INSUFFICIENT
    assert exc_info.value.code == "demo_certificate_requires_a0"


def test_demo_context_and_certificate_share_model_horizon_and_evidence() -> None:
    artifacts = build_demo_artifacts()
    context = artifacts.context
    certificate = artifacts.certificate

    assert context.risk_model_version == certificate.risk_model_version
    assert context.decision_horizon == certificate.decision_horizon
    assert context.evidence == certificate.evidence
    assert context.rho_interval == certificate.rho_interval
