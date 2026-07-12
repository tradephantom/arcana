from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from arcana.artifacts import validate_certificate_semantics, validate_risk_context_semantics
from arcana.calibration import CalibrationProfile
from arcana.certificate import build_demo_non_certifiable_certificate
from arcana.demo import build_demo_artifacts
from arcana.errors import ArcanaValidationError, ReasonCode
from arcana.model import LossBounds, RiskContext
from arcana.schemas import EXAMPLE_DIR, load_json, load_typed_fixture, parse_typed_document


NOW = datetime(2026, 6, 9, 0, 1, tzinfo=timezone.utc)


def _context() -> RiskContext:
    value = parse_typed_document(load_json(EXAMPLE_DIR / "risk_context_allow_with_controls.synthetic.json"))
    assert isinstance(value, RiskContext)
    return value


def test_context_semantics_accept_coherent_current_fixture() -> None:
    context = _context()

    assert validate_risk_context_semantics(context, now=NOW) is context


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (lambda value: dataclasses.replace(value, rho_interval=dataclasses.replace(value.rho_interval, upper=0.81)), "allow_rho_upper_not_subcritical"),
        (lambda value: dataclasses.replace(value, loss_bounds=LossBounds(2600, 1800, 2500, 3000)), "allow_aar_upper_exceeded"),
        (lambda value: dataclasses.replace(value, reason_codes=(ReasonCode.DENY_RHO_UPPER_BOUND, ReasonCode.INFO_SYNTHETIC_FIXTURE)), "verdict_reason_code_mismatch"),
        (lambda value: dataclasses.replace(value, evidence=dataclasses.replace(value.evidence, synthetic=False)), "synthetic_evidence_flag_mismatch"),
    ],
)
def test_context_semantics_reject_contradictions(mutation, expected_code: str) -> None:
    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_risk_context_semantics(mutation(_context()), now=NOW)

    assert exc_info.value.code == expected_code


def test_context_semantics_reject_expired_budget() -> None:
    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_risk_context_semantics(_context(), now=datetime(2026, 6, 9, 0, 6, tzinfo=timezone.utc))

    assert exc_info.value.code == "autonomy_budget_expired"


def test_certificate_semantics_reject_expired_artifact() -> None:
    certificate = build_demo_artifacts().certificate

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_certificate_semantics(certificate, now=datetime(2026, 6, 9, 0, 6, tzinfo=timezone.utc))

    assert exc_info.value.code == "certificate_expired"


def test_demo_builder_rejects_profile_id_mismatch() -> None:
    profile = load_typed_fixture(EXAMPLE_DIR / "calibration_profile_a0.synthetic.json")
    assert isinstance(profile, CalibrationProfile)
    mismatched = dataclasses.replace(profile, profile_id="arcana.cal.A0.different")

    with pytest.raises(ArcanaValidationError) as exc_info:
        build_demo_non_certifiable_certificate(
            certificate_id="arcana-cert-profile-mismatch",
            context=build_demo_artifacts().context,
            calibration_profile=mismatched,
            issued_at="2026-06-09T00:00:00Z",
            caveats=("negative binding test",),
        )

    assert exc_info.value.code == "demo_profile_id_mismatch"


def test_expected_graph_binding_is_enforced() -> None:
    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_risk_context_semantics(_context(), now=NOW, expected_graph_hash="sha256:" + "f" * 64)

    assert exc_info.value.code == "artifact_graph_hash_mismatch"
