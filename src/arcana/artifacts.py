"""Semantic admission validation for public ARCANA artifacts.

JSON Schema and typed parsing establish structure. These validators establish
whether a parsed artifact is internally coherent and current for a declared
admission context.
"""

from __future__ import annotations

from datetime import datetime, timezone

from arcana._validation import expect_number_min, expect_number_range, fail
from arcana.calibration import validate_calibration_sources_for_level, validate_certification_status_for_level
from arcana.certificate import BoundedAutonomyCertificate, CertificateType
from arcana.errors import CalibrationLevel, ReasonCode, Verdict
from arcana.model import DecisionHorizon, EvidenceReference, LossBounds, RhoInterval, RiskContext


_ALLOW_VERDICTS = frozenset({Verdict.ALLOW_BOUNDED_AUTONOMY, Verdict.ALLOW_WITH_CONTROLS})
_SYNTHETIC_EVIDENCE_SOURCE_TYPES = frozenset({"synthetic_fixture", "public_benchmark"})
_DENY_REASON_CODES = frozenset(
    {
        ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
        ReasonCode.DENY_RISK_MODEL_UNSUPPORTED,
        ReasonCode.DENY_MODEL_INPUT_INVALID,
        ReasonCode.DENY_CONTEXT_STALE,
        ReasonCode.DENY_GRAPH_HASH_MISMATCH,
        ReasonCode.DENY_DECISION_HORIZON_MISMATCH,
        ReasonCode.DENY_RHO_UPPER_BOUND,
        ReasonCode.DENY_AAR_UPPER_BOUND,
        ReasonCode.DENY_LOSS_MODEL_INVALID,
        ReasonCode.DENY_AES_UPPER_BOUND,
        ReasonCode.DENY_BUDGET_EXHAUSTED,
        ReasonCode.DENY_FASTGATE_UNCERTAIN,
        ReasonCode.DENY_FASTGATE_VECTOR_INVALID,
        ReasonCode.DENY_DISTILLATION_RISK,
    }
)


def validate_risk_context_semantics(
    context: RiskContext,
    *,
    now: datetime,
    expected_risk_model_version: str | None = None,
    expected_calibration_profile_id: str | None = None,
    expected_graph_hash: str | None = None,
    expected_decision_horizon: DecisionHorizon | None = None,
) -> RiskContext:
    """Validate a structurally parsed risk context for use at ``now``."""

    if not isinstance(context, RiskContext):
        fail("risk_context_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "context must be RiskContext", ("risk_context",))
    instant = _aware_datetime(now, ("now",))
    _validate_expected_bindings(
        risk_model_version=context.risk_model_version,
        calibration_profile_id=context.calibration_profile_id,
        graph_hash=context.graph_hash,
        decision_horizon=context.decision_horizon,
        expected_risk_model_version=expected_risk_model_version,
        expected_calibration_profile_id=expected_calibration_profile_id,
        expected_graph_hash=expected_graph_hash,
        expected_decision_horizon=expected_decision_horizon,
        path=("risk_context",),
    )
    _validate_evidence(context.evidence, context.reason_codes, ("risk_context", "evidence"))
    _validate_verdict(
        context.decision,
        context.reason_codes,
        context.rho_interval,
        context.loss_bounds,
        context.required_controls,
        ("risk_context",),
    )
    if context.calibration_level is CalibrationLevel.A0:
        if context.decision is not Verdict.OBSERVE_ONLY:
            fail("a0_context_not_observe_only", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "A0 contexts are observe_only", ("risk_context", "decision"))
        if ReasonCode.INFO_A0_NON_CERTIFIABLE not in context.reason_codes:
            fail("a0_context_missing_non_certifiable_reason", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "A0 contexts must disclose non-certifiable status", ("risk_context", "reason_codes"))
    expires_at = _parse_datetime(context.autonomy_budget.expires_at, ("risk_context", "autonomy_budget", "expires_at"))
    if instant >= expires_at:
        fail("autonomy_budget_expired", ReasonCode.DENY_BUDGET_EXHAUSTED, "autonomy budget is expired at validation time", ("risk_context", "autonomy_budget", "expires_at"))
    return context


def validate_certificate_semantics(
    certificate: BoundedAutonomyCertificate,
    *,
    now: datetime,
    expected_risk_model_version: str | None = None,
    expected_calibration_profile_id: str | None = None,
    expected_graph_hash: str | None = None,
    expected_decision_horizon: DecisionHorizon | None = None,
) -> BoundedAutonomyCertificate:
    """Validate a structurally parsed certificate-like artifact for use at ``now``."""

    if not isinstance(certificate, BoundedAutonomyCertificate):
        fail("certificate_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "certificate must be BoundedAutonomyCertificate", ("certificate",))
    instant = _aware_datetime(now, ("now",))
    _validate_expected_bindings(
        risk_model_version=certificate.risk_model_version,
        calibration_profile_id=certificate.calibration_profile.profile_id,
        graph_hash=certificate.graph_hash,
        decision_horizon=certificate.decision_horizon,
        expected_risk_model_version=expected_risk_model_version,
        expected_calibration_profile_id=expected_calibration_profile_id,
        expected_graph_hash=expected_graph_hash,
        expected_decision_horizon=expected_decision_horizon,
        path=("certificate",),
    )
    validate_calibration_sources_for_level(
        certificate.calibration_profile.level,
        certificate.calibration_profile.source,
        ("certificate", "calibration_profile", "source"),
    )
    validate_certification_status_for_level(
        certificate.calibration_profile.level,
        certificate.calibration_profile.certification_status,
        certificate.calibration_profile.source,
        ("certificate", "calibration_profile", "certification_status"),
    )
    _validate_evidence(certificate.evidence, certificate.reason_codes, ("certificate", "evidence"))
    _validate_verdict(
        certificate.verdict,
        certificate.reason_codes,
        certificate.rho_interval,
        certificate.loss_bounds,
        certificate.required_controls,
        ("certificate",),
    )
    if certificate.certificate_type is CertificateType.DEMO_NON_CERTIFIABLE_CERTIFICATE:
        if certificate.verdict is not Verdict.OBSERVE_ONLY:
            fail("demo_certificate_verdict_invalid", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "demo certificate must be observe_only", ("certificate", "verdict"))
    elif certificate.verdict not in _ALLOW_VERDICTS:
        fail("certificate_verdict_not_admissible", ReasonCode.DENY_MODEL_INPUT_INVALID, "non-demo certificate-like artifacts require an allow-like verdict", ("certificate", "verdict"))

    issued_at = _parse_datetime(certificate.issued_at, ("certificate", "issued_at"))
    if issued_at > instant:
        fail("certificate_issued_in_future", ReasonCode.DENY_CONTEXT_STALE, "issued_at is later than validation time", ("certificate", "issued_at"))
    if certificate.expires_at is None:
        fail("certificate_expiry_missing", ReasonCode.DENY_CONTEXT_STALE, "certificate-like artifacts require expires_at", ("certificate", "expires_at"))
    expires_at = _parse_datetime(certificate.expires_at, ("certificate", "expires_at"))
    if expires_at <= issued_at:
        fail("certificate_time_order_invalid", ReasonCode.DENY_CONTEXT_STALE, "expires_at must be later than issued_at", ("certificate", "expires_at"))
    if instant >= expires_at:
        fail("certificate_expired", ReasonCode.DENY_CONTEXT_STALE, "certificate-like artifact is expired", ("certificate", "expires_at"))
    return certificate


def _validate_expected_bindings(
    *,
    risk_model_version: str,
    calibration_profile_id: str,
    graph_hash: str,
    decision_horizon: DecisionHorizon,
    expected_risk_model_version: str | None,
    expected_calibration_profile_id: str | None,
    expected_graph_hash: str | None,
    expected_decision_horizon: DecisionHorizon | None,
    path: tuple[str, ...],
) -> None:
    if expected_risk_model_version is not None and risk_model_version != expected_risk_model_version:
        fail("artifact_risk_model_mismatch", ReasonCode.DENY_RISK_MODEL_UNSUPPORTED, "artifact risk model does not match the admission context", (*path, "risk_model_version"))
    if expected_calibration_profile_id is not None and calibration_profile_id != expected_calibration_profile_id:
        fail("artifact_calibration_profile_mismatch", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "artifact calibration profile does not match the admission context", (*path, "calibration_profile_id"))
    if expected_graph_hash is not None and graph_hash != expected_graph_hash:
        fail("artifact_graph_hash_mismatch", ReasonCode.DENY_GRAPH_HASH_MISMATCH, "artifact graph hash does not match the admission context", (*path, "graph_hash"))
    if expected_decision_horizon is not None and decision_horizon != expected_decision_horizon:
        fail("artifact_decision_horizon_mismatch", ReasonCode.DENY_DECISION_HORIZON_MISMATCH, "artifact decision horizon does not match the admission context", (*path, "decision_horizon"))


def _validate_evidence(evidence: EvidenceReference, reason_codes: tuple[ReasonCode, ...], path: tuple[str, ...]) -> None:
    if not isinstance(evidence, EvidenceReference):
        fail("evidence_reference_invalid", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "evidence must be EvidenceReference", path)
    if evidence.source_type in _SYNTHETIC_EVIDENCE_SOURCE_TYPES and not evidence.synthetic:
        fail("synthetic_evidence_flag_mismatch", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "synthetic evidence source types must set synthetic=true", (*path, "synthetic"))
    if evidence.source_type not in _SYNTHETIC_EVIDENCE_SOURCE_TYPES and evidence.synthetic:
        fail("non_synthetic_source_flag_mismatch", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "non-synthetic source types must set synthetic=false", (*path, "synthetic"))
    if evidence.evidence_hash is None:
        fail("evidence_hash_missing", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "admissible artifacts require a hash-bound evidence reference", (*path, "evidence_hash"))
    has_synthetic_disclosure = ReasonCode.INFO_SYNTHETIC_FIXTURE in reason_codes
    if evidence.synthetic and not has_synthetic_disclosure:
        fail("synthetic_evidence_reason_missing", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "synthetic evidence requires ARCANA_INFO_SYNTHETIC_FIXTURE", (*path[:-1], "reason_codes"))
    if not evidence.synthetic and has_synthetic_disclosure:
        fail("synthetic_evidence_reason_unexpected", ReasonCode.DENY_MODEL_INPUT_INVALID, "non-synthetic evidence cannot carry ARCANA_INFO_SYNTHETIC_FIXTURE", (*path[:-1], "reason_codes"))


def _validate_verdict(
    verdict: Verdict,
    reason_codes: tuple[ReasonCode, ...],
    rho_interval: RhoInterval,
    loss_bounds: LossBounds | None,
    required_controls: tuple[str, ...],
    path: tuple[str, ...],
) -> None:
    if not isinstance(verdict, Verdict):
        fail("verdict_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "verdict must be Verdict", (*path, "verdict"))
    if not reason_codes or any(not isinstance(code, ReasonCode) for code in reason_codes):
        fail("reason_codes_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "reason_codes must contain typed ARCANA reason codes", (*path, "reason_codes"))
    primary = reason_codes[0]
    expected_primary: ReasonCode | None
    if verdict is Verdict.ALLOW_BOUNDED_AUTONOMY:
        expected_primary = ReasonCode.ALLOW_BOUNDED_AUTONOMY
    elif verdict is Verdict.ALLOW_WITH_CONTROLS:
        expected_primary = ReasonCode.ALLOW_WITH_CONTROLS
    elif verdict is Verdict.REQUIRE_SCOPE_REDUCTION:
        expected_primary = ReasonCode.REQUIRE_SCOPE_REDUCTION
    elif verdict is Verdict.REQUIRE_HUMAN_GATE:
        expected_primary = ReasonCode.REQUIRE_HUMAN_GATE
    elif verdict is Verdict.OBSERVE_ONLY:
        expected_primary = ReasonCode.REQUIRE_OBSERVE_ONLY
    elif verdict is Verdict.DENY:
        expected_primary = None
        if primary not in _DENY_REASON_CODES:
            fail("deny_reason_code_mismatch", ReasonCode.DENY_MODEL_INPUT_INVALID, "deny verdict requires a deny reason code first", (*path, "reason_codes", 0))
    else:
        fail("verdict_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "unsupported verdict", (*path, "verdict"))
    if expected_primary is not None and primary is not expected_primary:
        fail("verdict_reason_code_mismatch", ReasonCode.DENY_MODEL_INPUT_INVALID, "verdict and primary reason code are inconsistent", (*path, "reason_codes", 0))

    if verdict is Verdict.ALLOW_WITH_CONTROLS and not required_controls:
        fail("allow_with_controls_missing_controls", ReasonCode.DENY_MODEL_INPUT_INVALID, "allow_with_controls requires at least one required control", (*path, "required_controls"))
    if verdict is Verdict.ALLOW_BOUNDED_AUTONOMY and required_controls:
        fail("allow_without_controls_has_controls", ReasonCode.DENY_MODEL_INPUT_INVALID, "allow_bounded_autonomy cannot carry required controls", (*path, "required_controls"))
    if verdict not in _ALLOW_VERDICTS:
        return

    lower = expect_number_min(rho_interval.lower, 0, (*path, "rho_interval", "lower"), ReasonCode.DENY_MODEL_INPUT_INVALID)
    mean = expect_number_min(rho_interval.mean, 0, (*path, "rho_interval", "mean"), ReasonCode.DENY_MODEL_INPUT_INVALID)
    upper = expect_number_min(rho_interval.upper, 0, (*path, "rho_interval", "upper"), ReasonCode.DENY_MODEL_INPUT_INVALID)
    threshold = expect_number_range(rho_interval.threshold, 0, 1, (*path, "rho_interval", "threshold"), ReasonCode.DENY_MODEL_INPUT_INVALID)
    if threshold == 0 or not lower <= mean <= upper:
        fail("rho_interval_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "allow-like verdict requires an ordered interval and a positive threshold", (*path, "rho_interval"))
    if not upper < threshold:
        fail("allow_rho_upper_not_subcritical", ReasonCode.DENY_RHO_UPPER_BOUND, "allow-like verdict requires rho_upper below threshold", (*path, "rho_interval", "upper"))
    if loss_bounds is None:
        fail("allow_loss_bounds_missing", ReasonCode.DENY_LOSS_MODEL_INVALID, "allow-like verdict requires explicit loss bounds", (*path, "loss_bounds"))
    _validate_loss_bounds(loss_bounds, path)


def _validate_loss_bounds(loss_bounds: LossBounds, path: tuple[str, ...]) -> None:
    aar = expect_number_min(loss_bounds.aar_99_upper, 0, (*path, "loss_bounds", "aar_99_upper"), ReasonCode.DENY_LOSS_MODEL_INVALID)
    aes = expect_number_min(loss_bounds.aes_99_upper, 0, (*path, "loss_bounds", "aes_99_upper"), ReasonCode.DENY_LOSS_MODEL_INVALID)
    max_aar = expect_number_min(loss_bounds.max_allowed_aar_99, 0, (*path, "loss_bounds", "max_allowed_aar_99"), ReasonCode.DENY_LOSS_MODEL_INVALID)
    max_aes = expect_number_min(loss_bounds.max_allowed_aes_99, 0, (*path, "loss_bounds", "max_allowed_aes_99"), ReasonCode.DENY_LOSS_MODEL_INVALID)
    if aar > max_aar:
        fail("allow_aar_upper_exceeded", ReasonCode.DENY_AAR_UPPER_BOUND, "allow-like verdict exceeds max_allowed_aar_99", (*path, "loss_bounds", "aar_99_upper"))
    if aes > max_aes:
        fail("allow_aes_upper_exceeded", ReasonCode.DENY_AES_UPPER_BOUND, "allow-like verdict exceeds max_allowed_aes_99", (*path, "loss_bounds", "aes_99_upper"))


def _aware_datetime(value: datetime, path: tuple[str, ...]) -> datetime:
    if not isinstance(value, datetime):
        fail("datetime_invalid", ReasonCode.DENY_CONTEXT_STALE, "expected datetime", path)
    if value.tzinfo is None or value.utcoffset() is None:
        fail("datetime_timezone_missing", ReasonCode.DENY_CONTEXT_STALE, "datetime must include a UTC offset", path)
    return value.astimezone(timezone.utc)


def _parse_datetime(value: str, path: tuple[str, ...]) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        fail("datetime_invalid", ReasonCode.DENY_CONTEXT_STALE, "expected RFC3339-compatible date-time", path)
    return _aware_datetime(parsed, path)


__all__ = ["validate_certificate_semantics", "validate_risk_context_semantics"]
