"""Typed certificate artifact contracts for ARCANA."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from arcana._validation import (
    expect_certificate_id,
    expect_datetime_string,
    expect_enum,
    expect_mapping,
    expect_number_range,
    expect_risk_model_version,
    expect_string_list,
    fail,
    require_value,
)
from arcana.errors import CalibrationLevel, CertificationStatus, ReasonCode, Verdict
from arcana.model import DecisionHorizon, EvidenceReference, FastGateContext, LossBounds, RhoInterval


class CertificateType(str, Enum):
    BOUNDED_AUTONOMY_CERTIFICATE = "bounded_autonomy_certificate"
    SUBCRITICAL_UNDER_MODEL_CERTIFICATE = "subcritical_under_model_certificate"
    DEMO_NON_CERTIFIABLE_CERTIFICATE = "demo_non_certifiable_certificate"


@dataclass(frozen=True)
class CertificateCalibrationProfile:
    profile_id: str
    level: CalibrationLevel
    source: tuple[str, ...]
    confidence: float
    certification_status: CertificationStatus

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("calibration_profile",)) -> "CertificateCalibrationProfile":
        from arcana._validation import expect_calibration_profile_id

        data = expect_mapping(value, path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
        level = expect_enum(CalibrationLevel, require_value(data, "level", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "level"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
        status = expect_enum(
            CertificationStatus,
            require_value(data, "certification_status", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
            (*path, "certification_status"),
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
        )
        if level is CalibrationLevel.A0 and status is not CertificationStatus.NON_CERTIFIABLE:
            fail("a0_must_be_non_certifiable", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "A0 certificate profile must be non_certifiable", (*path, "certification_status"))
        return cls(
            profile_id=expect_calibration_profile_id(require_value(data, "profile_id", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "profile_id")),
            level=level,
            source=expect_string_list(require_value(data, "source", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "source"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT, min_items=1, unique=True),
            confidence=expect_number_range(require_value(data, "confidence", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), 0, 1, (*path, "confidence"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
            certification_status=status,
        )


@dataclass(frozen=True)
class BoundedAutonomyCertificate:
    certificate_id: str
    certificate_type: CertificateType
    risk_model_version: str
    calibration_profile: CertificateCalibrationProfile
    decision_horizon: DecisionHorizon
    verdict: Verdict
    rho_interval: RhoInterval
    loss_bounds: LossBounds
    evidence: EvidenceReference
    reason_codes: tuple[ReasonCode, ...]
    issued_at: str
    caveats: tuple[str, ...]
    fastgate: FastGateContext | None = None
    required_controls: tuple[str, ...] = ()
    expires_at: str | None = None

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ()) -> "BoundedAutonomyCertificate":
        data = expect_mapping(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        raw_codes = require_value(data, "reason_codes", path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        if not isinstance(raw_codes, list) or not raw_codes:
            fail("reason_codes_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "reason_codes must be a non-empty array", (*path, "reason_codes"))
        reason_codes = tuple(expect_enum(ReasonCode, item, (*path, "reason_codes", index), ReasonCode.DENY_MODEL_INPUT_INVALID) for index, item in enumerate(raw_codes))
        calibration_profile = CertificateCalibrationProfile.from_mapping(
            require_value(data, "calibration_profile", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
            (*path, "calibration_profile"),
        )
        certificate_type = expect_enum(
            CertificateType,
            require_value(data, "certificate_type", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
            (*path, "certificate_type"),
            ReasonCode.DENY_MODEL_INPUT_INVALID,
        )
        if calibration_profile.level is CalibrationLevel.A0:
            if certificate_type is not CertificateType.DEMO_NON_CERTIFIABLE_CERTIFICATE:
                fail("a0_certificate_type_invalid", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "A0 certificate must be demo_non_certifiable_certificate", (*path, "certificate_type"))
            if ReasonCode.INFO_A0_NON_CERTIFIABLE not in reason_codes:
                fail("a0_missing_info_reason", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "A0 certificate requires ARCANA_INFO_A0_NON_CERTIFIABLE", (*path, "reason_codes"))
        expires_at = data.get("expires_at")
        return cls(
            certificate_id=expect_certificate_id(require_value(data, "certificate_id", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "certificate_id")),
            certificate_type=certificate_type,
            risk_model_version=expect_risk_model_version(require_value(data, "risk_model_version", path, ReasonCode.DENY_RISK_MODEL_UNSUPPORTED), (*path, "risk_model_version")),
            calibration_profile=calibration_profile,
            decision_horizon=DecisionHorizon.from_mapping(require_value(data, "decision_horizon", path, ReasonCode.DENY_DECISION_HORIZON_MISMATCH), (*path, "decision_horizon")),
            verdict=expect_enum(Verdict, require_value(data, "verdict", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "verdict"), ReasonCode.DENY_MODEL_INPUT_INVALID),
            rho_interval=RhoInterval.from_mapping(require_value(data, "rho_interval", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "rho_interval")),
            loss_bounds=LossBounds.from_mapping(require_value(data, "loss_bounds", path, ReasonCode.DENY_LOSS_MODEL_INVALID), (*path, "loss_bounds")),
            evidence=EvidenceReference.from_mapping(require_value(data, "evidence", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "evidence")),
            reason_codes=reason_codes,
            issued_at=expect_datetime_string(require_value(data, "issued_at", path, ReasonCode.DENY_CONTEXT_STALE), (*path, "issued_at"), ReasonCode.DENY_CONTEXT_STALE),
            caveats=expect_string_list(require_value(data, "caveats", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "caveats"), ReasonCode.DENY_MODEL_INPUT_INVALID, min_items=1),
            fastgate=FastGateContext.from_mapping(data["fastgate"], (*path, "fastgate")) if "fastgate" in data else None,
            required_controls=expect_string_list(data.get("required_controls", []), (*path, "required_controls"), ReasonCode.DENY_MODEL_INPUT_INVALID, unique=True),
            expires_at=expect_datetime_string(expires_at, (*path, "expires_at"), ReasonCode.DENY_CONTEXT_STALE) if expires_at is not None else None,
        )


__all__ = [
    "BoundedAutonomyCertificate",
    "CertificateCalibrationProfile",
    "CertificateType",
]
