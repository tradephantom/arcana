"""Typed certificate artifact contracts for ARCANA."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from typing import Any

from arcana._validation import (
    expect_certificate_id,
    expect_datetime_string,
    expect_enum,
    expect_mapping,
    expect_number_range,
    expect_risk_model_version,
    expect_sha256,
    expect_string_list,
    fail,
    require_value,
)
from arcana.calibration import CalibrationProfile, validate_calibration_sources_for_level, validate_certification_status_for_level
from arcana.errors import CalibrationLevel, CertificationStatus, ReasonCode, Verdict
from arcana.model import AutonomyBudget, DecisionHorizon, EvidenceReference, FastGateContext, LossBounds, RhoInterval, RiskContext


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
        source = expect_string_list(require_value(data, "source", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "source"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT, min_items=1, unique=True)
        validate_calibration_sources_for_level(level, source, (*path, "source"))
        validate_certification_status_for_level(level, status, source, (*path, "certification_status"))
        return cls(
            profile_id=expect_calibration_profile_id(require_value(data, "profile_id", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "profile_id")),
            level=level,
            source=source,
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
    graph_hash: str
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
        if len(reason_codes) != len(set(reason_codes)):
            fail("reason_codes_not_unique", ReasonCode.DENY_MODEL_INPUT_INVALID, "reason_codes must be unique", (*path, "reason_codes"))
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
        verdict = expect_enum(Verdict, require_value(data, "verdict", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "verdict"), ReasonCode.DENY_MODEL_INPUT_INVALID)
        evidence = EvidenceReference.from_mapping(require_value(data, "evidence", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "evidence"))
        if certificate_type is CertificateType.DEMO_NON_CERTIFIABLE_CERTIFICATE:
            if calibration_profile.level is not CalibrationLevel.A0:
                fail("demo_certificate_requires_a0", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "demo_non_certifiable_certificate requires A0 calibration", (*path, "calibration_profile", "level"))
            if calibration_profile.certification_status is not CertificationStatus.NON_CERTIFIABLE:
                fail("demo_certificate_must_be_non_certifiable", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "demo_non_certifiable_certificate requires non_certifiable status", (*path, "calibration_profile", "certification_status"))
            if verdict is not Verdict.OBSERVE_ONLY:
                fail("demo_certificate_verdict_invalid", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "demo_non_certifiable_certificate must use observe_only verdict", (*path, "verdict"))
            if not evidence.synthetic:
                fail("demo_certificate_evidence_not_synthetic", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "demo_non_certifiable_certificate requires synthetic evidence", (*path, "evidence", "synthetic"))
        else:
            if calibration_profile.level not in {CalibrationLevel.A2, CalibrationLevel.A3}:
                fail("certificate_calibration_level_insufficient", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "non-demo certificate-like artifacts require A2 or A3 calibration", (*path, "calibration_profile", "level"))
            if calibration_profile.certification_status is not CertificationStatus.CERTIFIABLE_UNDER_PROFILE:
                fail("certificate_profile_not_certifiable", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "non-demo certificate-like artifacts require certifiable_under_profile status", (*path, "calibration_profile", "certification_status"))
            if evidence.synthetic:
                fail("certificate_evidence_synthetic_invalid", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "non-demo certificate-like artifacts cannot use synthetic evidence", (*path, "evidence", "synthetic"))
            if ReasonCode.INFO_A0_NON_CERTIFIABLE in reason_codes or ReasonCode.INFO_SYNTHETIC_FIXTURE in reason_codes:
                fail("certificate_reason_code_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "non-demo certificate-like artifacts cannot carry demo or synthetic info reason codes", (*path, "reason_codes"))
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
            graph_hash=expect_sha256(require_value(data, "graph_hash", path, ReasonCode.DENY_GRAPH_HASH_MISMATCH), (*path, "graph_hash"), ReasonCode.DENY_GRAPH_HASH_MISMATCH),
            verdict=verdict,
            rho_interval=RhoInterval.from_mapping(require_value(data, "rho_interval", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "rho_interval")),
            loss_bounds=LossBounds.from_mapping(require_value(data, "loss_bounds", path, ReasonCode.DENY_LOSS_MODEL_INVALID), (*path, "loss_bounds")),
            evidence=evidence,
            reason_codes=reason_codes,
            issued_at=expect_datetime_string(require_value(data, "issued_at", path, ReasonCode.DENY_CONTEXT_STALE), (*path, "issued_at"), ReasonCode.DENY_CONTEXT_STALE),
            caveats=expect_string_list(require_value(data, "caveats", path, ReasonCode.DENY_MODEL_INPUT_INVALID), (*path, "caveats"), ReasonCode.DENY_MODEL_INPUT_INVALID, min_items=1),
            fastgate=FastGateContext.from_mapping(data["fastgate"], (*path, "fastgate")) if "fastgate" in data else None,
            required_controls=expect_string_list(data.get("required_controls", []), (*path, "required_controls"), ReasonCode.DENY_MODEL_INPUT_INVALID, unique=True),
            expires_at=expect_datetime_string(expires_at, (*path, "expires_at"), ReasonCode.DENY_CONTEXT_STALE) if expires_at is not None else None,
        )


def risk_context_to_mapping(context: RiskContext) -> dict[str, Any]:
    if not isinstance(context, RiskContext):
        fail("risk_context_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "context must be RiskContext", ("risk_context",))
    document: dict[str, Any] = {
        "schema_version": "arcana.context.v0.2",
        "risk_model_version": context.risk_model_version,
        "calibration_profile_id": context.calibration_profile_id,
        "calibration_level": context.calibration_level.value,
        "decision_horizon": _decision_horizon_to_mapping(context.decision_horizon),
        "graph_hash": context.graph_hash,
        "rho_interval": _rho_interval_to_mapping(context.rho_interval),
        "decision": context.decision.value,
        "reason_codes": _reason_codes_to_values(context.reason_codes),
        "evidence": _evidence_to_mapping(context.evidence),
        "autonomy_budget": _autonomy_budget_to_mapping(context.autonomy_budget),
    }
    if context.loss_bounds is not None:
        document["loss_bounds"] = _loss_bounds_to_mapping(context.loss_bounds)
    if context.fastgate is not None:
        document["fastgate"] = _fastgate_to_mapping(context.fastgate)
    if context.required_controls:
        document["required_controls"] = list(context.required_controls)
    RiskContext.from_mapping(document)
    return document


def certificate_to_mapping(certificate: BoundedAutonomyCertificate) -> dict[str, Any]:
    if not isinstance(certificate, BoundedAutonomyCertificate):
        fail("certificate_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "certificate must be BoundedAutonomyCertificate", ("certificate",))
    document: dict[str, Any] = {
        "schema_version": "arcana.certificate.v0.2",
        "certificate_id": certificate.certificate_id,
        "certificate_type": certificate.certificate_type.value,
        "risk_model_version": certificate.risk_model_version,
        "calibration_profile": _certificate_calibration_profile_to_mapping(certificate.calibration_profile),
        "decision_horizon": _decision_horizon_to_mapping(certificate.decision_horizon),
        "graph_hash": certificate.graph_hash,
        "verdict": certificate.verdict.value,
        "rho_interval": _rho_interval_to_mapping(certificate.rho_interval),
        "loss_bounds": _loss_bounds_to_mapping(certificate.loss_bounds),
        "evidence": _evidence_to_mapping(certificate.evidence),
        "reason_codes": _reason_codes_to_values(certificate.reason_codes),
        "issued_at": certificate.issued_at,
        "caveats": list(certificate.caveats),
    }
    if certificate.fastgate is not None:
        document["fastgate"] = _fastgate_to_mapping(certificate.fastgate)
    if certificate.required_controls:
        document["required_controls"] = list(certificate.required_controls)
    if certificate.expires_at is not None:
        document["expires_at"] = certificate.expires_at
    BoundedAutonomyCertificate.from_mapping(document)
    return document


def build_demo_non_certifiable_certificate(
    *,
    certificate_id: str,
    context: RiskContext,
    calibration_profile: CalibrationProfile,
    issued_at: str,
    caveats: Sequence[str],
) -> BoundedAutonomyCertificate:
    expect_certificate_id(certificate_id, ("certificate_id",))
    if not isinstance(context, RiskContext):
        fail("risk_context_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "context must be RiskContext", ("risk_context",))
    if not isinstance(calibration_profile, CalibrationProfile):
        fail(
            "calibration_profile_invalid",
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            "calibration_profile must be CalibrationProfile",
            ("calibration_profile",),
        )
    if calibration_profile.level is not CalibrationLevel.A0:
        fail(
            "demo_certificate_requires_a0",
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            "demo_non_certifiable_certificate requires A0 calibration",
            ("calibration_profile", "level"),
        )
    if calibration_profile.certification_status is not CertificationStatus.NON_CERTIFIABLE:
        fail(
            "a0_must_be_non_certifiable",
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            "A0 calibration must be non_certifiable",
            ("calibration_profile", "certification_status"),
        )
    validate_calibration_sources_for_level(
        calibration_profile.level,
        calibration_profile.source,
        ("calibration_profile", "source"),
    )
    if calibration_profile.profile_id != context.calibration_profile_id:
        fail(
            "demo_profile_id_mismatch",
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            "calibration profile id must match the risk context",
            ("calibration_profile", "profile_id"),
        )
    if calibration_profile.risk_model_version != context.risk_model_version:
        fail(
            "demo_profile_risk_model_mismatch",
            ReasonCode.DENY_RISK_MODEL_UNSUPPORTED,
            "calibration risk model must match the risk context",
            ("calibration_profile", "risk_model_version"),
        )
    if calibration_profile.decision_horizon != context.decision_horizon:
        fail(
            "demo_profile_horizon_mismatch",
            ReasonCode.DENY_DECISION_HORIZON_MISMATCH,
            "calibration decision horizon must match the risk context",
            ("calibration_profile", "decision_horizon"),
        )
    if context.calibration_level is not CalibrationLevel.A0:
        fail(
            "demo_context_requires_a0",
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            "demo certificate context must use A0 calibration",
            ("risk_context", "calibration_level"),
        )
    if context.decision is not Verdict.OBSERVE_ONLY:
        fail(
            "a0_certificate_verdict_invalid",
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            "A0 demo certificate must be observe_only",
            ("risk_context", "decision"),
        )
    if context.loss_bounds is None:
        fail(
            "demo_certificate_loss_bounds_missing",
            ReasonCode.DENY_LOSS_MODEL_INVALID,
            "demo certificate requires explicit loss_bounds",
            ("risk_context", "loss_bounds"),
        )
    if not context.evidence.synthetic:
        fail(
            "demo_certificate_evidence_not_synthetic",
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            "demo certificate evidence must be synthetic",
            ("risk_context", "evidence", "synthetic"),
        )
    if context.evidence.source_type != "synthetic_fixture":
        fail(
            "demo_certificate_evidence_source_invalid",
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            "demo certificate evidence must use synthetic_fixture source_type",
            ("risk_context", "evidence", "source_type"),
        )
    issued_at_value = expect_datetime_string(issued_at, ("issued_at",), ReasonCode.DENY_CONTEXT_STALE)
    issued_at_datetime = datetime.fromisoformat(issued_at_value.replace("Z", "+00:00"))
    from arcana.artifacts import validate_certificate_semantics, validate_risk_context_semantics

    validate_risk_context_semantics(context, now=issued_at_datetime)
    reason_codes = _merge_reason_codes(
        context.reason_codes,
        (
            ReasonCode.REQUIRE_OBSERVE_ONLY,
            ReasonCode.INFO_A0_NON_CERTIFIABLE,
            ReasonCode.INFO_SYNTHETIC_FIXTURE,
        ),
    )
    certificate = BoundedAutonomyCertificate(
        certificate_id=certificate_id,
        certificate_type=CertificateType.DEMO_NON_CERTIFIABLE_CERTIFICATE,
        risk_model_version=context.risk_model_version,
        calibration_profile=CertificateCalibrationProfile(
            profile_id=calibration_profile.profile_id,
            level=calibration_profile.level,
            source=calibration_profile.source,
            confidence=calibration_profile.confidence,
            certification_status=calibration_profile.certification_status,
        ),
        decision_horizon=context.decision_horizon,
        graph_hash=context.graph_hash,
        verdict=context.decision,
        rho_interval=context.rho_interval,
        loss_bounds=context.loss_bounds,
        evidence=context.evidence,
        reason_codes=reason_codes,
        issued_at=issued_at_value,
        caveats=expect_string_list(list(caveats), ("caveats",), ReasonCode.DENY_MODEL_INPUT_INVALID, min_items=1),
        fastgate=context.fastgate,
        required_controls=context.required_controls,
        expires_at=context.autonomy_budget.expires_at,
    )
    certificate_to_mapping(certificate)
    validate_certificate_semantics(certificate, now=issued_at_datetime)
    return certificate


def _decision_horizon_to_mapping(horizon: DecisionHorizon) -> dict[str, Any]:
    return {
        "id": horizon.id,
        "duration_seconds": horizon.duration_seconds,
        "context": horizon.context,
    }


def _rho_interval_to_mapping(interval: RhoInterval) -> dict[str, Any]:
    return {
        "lower": interval.lower,
        "mean": interval.mean,
        "upper": interval.upper,
        "threshold": interval.threshold,
    }


def _loss_bounds_to_mapping(loss_bounds: LossBounds) -> dict[str, Any]:
    return {
        "aar_99_upper": loss_bounds.aar_99_upper,
        "aes_99_upper": loss_bounds.aes_99_upper,
        "max_allowed_aar_99": loss_bounds.max_allowed_aar_99,
        "max_allowed_aes_99": loss_bounds.max_allowed_aes_99,
    }


def _fastgate_to_mapping(fastgate: FastGateContext) -> dict[str, Any]:
    document: dict[str, Any] = {"mode": fastgate.mode.value}
    if fastgate.positive_vector_method is not None:
        document["positive_vector_method"] = fastgate.positive_vector_method.value
    if fastgate.upper_bound is not None:
        document["upper_bound"] = fastgate.upper_bound
    return document


def _evidence_to_mapping(evidence: EvidenceReference) -> dict[str, Any]:
    document: dict[str, Any] = {
        "source_type": evidence.source_type,
        "source_id": evidence.source_id,
        "synthetic": evidence.synthetic,
    }
    if evidence.evidence_hash is not None:
        document["evidence_hash"] = evidence.evidence_hash
    return document


def _autonomy_budget_to_mapping(budget: AutonomyBudget) -> dict[str, Any]:
    document: dict[str, Any] = {"expires_at": budget.expires_at}
    if budget.max_delta_rho_upper is not None:
        document["max_delta_rho_upper"] = budget.max_delta_rho_upper
    if budget.max_external_requests is not None:
        document["max_external_requests"] = budget.max_external_requests
    if budget.max_memory_writes is not None:
        document["max_memory_writes"] = budget.max_memory_writes
    if budget.max_output_bytes is not None:
        document["max_output_bytes"] = budget.max_output_bytes
    return document


def _certificate_calibration_profile_to_mapping(profile: CertificateCalibrationProfile) -> dict[str, Any]:
    return {
        "profile_id": profile.profile_id,
        "level": profile.level.value,
        "source": list(profile.source),
        "confidence": profile.confidence,
        "certification_status": profile.certification_status.value,
    }


def _reason_codes_to_values(reason_codes: Sequence[ReasonCode]) -> list[str]:
    values: list[str] = []
    for index, reason_code in enumerate(reason_codes):
        if not isinstance(reason_code, ReasonCode):
            fail(
                "reason_code_invalid",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "reason_codes must contain ReasonCode values",
                ("reason_codes", index),
            )
        values.append(reason_code.value)
    return values


def _merge_reason_codes(existing: Sequence[ReasonCode], required: Sequence[ReasonCode]) -> tuple[ReasonCode, ...]:
    merged: list[ReasonCode] = []
    for reason_code in (*existing, *required):
        if not isinstance(reason_code, ReasonCode):
            fail("reason_code_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "reason_codes must contain ReasonCode values", ("reason_codes",))
        if reason_code not in merged:
            merged.append(reason_code)
    return tuple(merged)


__all__ = [
    "BoundedAutonomyCertificate",
    "CertificateCalibrationProfile",
    "CertificateType",
    "build_demo_non_certifiable_certificate",
    "certificate_to_mapping",
    "risk_context_to_mapping",
]
