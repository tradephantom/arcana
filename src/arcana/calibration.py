"""Typed calibration profile contracts for ARCANA."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arcana._validation import (
    expect_bool,
    expect_calibration_profile_id,
    expect_datetime_string,
    expect_enum,
    expect_mapping,
    expect_number_min,
    expect_number_range,
    expect_risk_model_version,
    expect_string_list,
    fail,
    require_value,
)
from arcana.errors import CalibrationLevel, CertificationStatus, ReasonCode
from arcana.model import DecisionHorizon


ALLOWED_CALIBRATION_SOURCES = {
    "synthetic_demo",
    "static_conservative_prior",
    "controlled_redteam",
    "adversarial_replay",
    "public_benchmark",
    "runtime_observation",
}


@dataclass(frozen=True)
class EvidenceWindow:
    observed_after: str
    observed_before: str
    max_age_seconds: int

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("evidence_window",)) -> "EvidenceWindow":
        data = expect_mapping(value, path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
        max_age = require_value(data, "max_age_seconds", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
        if not isinstance(max_age, int) or isinstance(max_age, bool) or max_age < 1:
            fail("evidence_window_max_age_invalid", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "max_age_seconds must be integer >= 1", (*path, "max_age_seconds"))
        return cls(
            observed_after=expect_datetime_string(
                require_value(data, "observed_after", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
                (*path, "observed_after"),
                ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            ),
            observed_before=expect_datetime_string(
                require_value(data, "observed_before", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
                (*path, "observed_before"),
                ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            ),
            max_age_seconds=max_age,
        )


@dataclass(frozen=True)
class CalibrationUncertainty:
    rho_lower: float
    rho_mean: float
    rho_upper: float

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("uncertainty",)) -> "CalibrationUncertainty":
        data = expect_mapping(value, path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
        uncertainty = cls(
            rho_lower=expect_number_min(require_value(data, "rho_lower", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), 0, (*path, "rho_lower"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
            rho_mean=expect_number_min(require_value(data, "rho_mean", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), 0, (*path, "rho_mean"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
            rho_upper=expect_number_min(require_value(data, "rho_upper", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), 0, (*path, "rho_upper"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
        )
        if not uncertainty.rho_lower <= uncertainty.rho_mean <= uncertainty.rho_upper:
            fail("calibration_uncertainty_order_invalid", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "expected rho_lower <= rho_mean <= rho_upper", path)
        return uncertainty


@dataclass(frozen=True)
class EdgeWeightPolicy:
    unknown_means_risky: bool
    use_upper_bound_for_risk: bool
    use_lower_bound_for_controls: bool

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("edge_weight_policy",)) -> "EdgeWeightPolicy":
        data = expect_mapping(value, path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
        policy = cls(
            unknown_means_risky=expect_bool(require_value(data, "unknown_means_risky", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "unknown_means_risky"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
            use_upper_bound_for_risk=expect_bool(require_value(data, "use_upper_bound_for_risk", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "use_upper_bound_for_risk"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
            use_lower_bound_for_controls=expect_bool(require_value(data, "use_lower_bound_for_controls", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "use_lower_bound_for_controls"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
        )
        if not policy.unknown_means_risky:
            fail("edge_weight_policy_unknown_not_risky", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "unknown_means_risky must be true", (*path, "unknown_means_risky"))
        if not policy.use_upper_bound_for_risk:
            fail("edge_weight_policy_risk_not_upper_bound", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "use_upper_bound_for_risk must be true", (*path, "use_upper_bound_for_risk"))
        if not policy.use_lower_bound_for_controls:
            fail("edge_weight_policy_controls_not_lower_bound", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "use_lower_bound_for_controls must be true", (*path, "use_lower_bound_for_controls"))
        return policy


@dataclass(frozen=True)
class CalibrationProfile:
    profile_id: str
    risk_model_version: str
    level: CalibrationLevel
    decision_horizon: DecisionHorizon
    source: tuple[str, ...]
    evidence_window: EvidenceWindow
    confidence: float
    uncertainty: CalibrationUncertainty
    edge_weight_policy: EdgeWeightPolicy
    caveats: tuple[str, ...]
    certification_status: CertificationStatus
    last_updated_at: str | None = None

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ()) -> "CalibrationProfile":
        data = expect_mapping(value, path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT)
        level = expect_enum(
            CalibrationLevel,
            require_value(data, "level", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
            (*path, "level"),
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
        )
        status = expect_enum(
            CertificationStatus,
            require_value(data, "certification_status", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
            (*path, "certification_status"),
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
        )
        if level is CalibrationLevel.A0 and status is not CertificationStatus.NON_CERTIFIABLE:
            fail("a0_must_be_non_certifiable", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "A0 calibration must be non_certifiable", (*path, "certification_status"))
        last_updated = data.get("last_updated_at")
        sources = expect_string_list(
            require_value(data, "source", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
            (*path, "source"),
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            min_items=1,
            unique=True,
        )
        for index, source in enumerate(sources):
            if source not in ALLOWED_CALIBRATION_SOURCES:
                fail("calibration_source_unsupported", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "unsupported calibration source", (*path, "source", index))
        return cls(
            profile_id=expect_calibration_profile_id(require_value(data, "profile_id", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "profile_id")),
            risk_model_version=expect_risk_model_version(require_value(data, "risk_model_version", path, ReasonCode.DENY_RISK_MODEL_UNSUPPORTED), (*path, "risk_model_version")),
            level=level,
            decision_horizon=DecisionHorizon.from_mapping(require_value(data, "decision_horizon", path, ReasonCode.DENY_DECISION_HORIZON_MISMATCH), (*path, "decision_horizon")),
            source=sources,
            evidence_window=EvidenceWindow.from_mapping(require_value(data, "evidence_window", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "evidence_window")),
            confidence=expect_number_range(require_value(data, "confidence", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), 0, 1, (*path, "confidence"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
            uncertainty=CalibrationUncertainty.from_mapping(require_value(data, "uncertainty", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "uncertainty")),
            edge_weight_policy=EdgeWeightPolicy.from_mapping(require_value(data, "edge_weight_policy", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "edge_weight_policy")),
            caveats=expect_string_list(require_value(data, "caveats", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT), (*path, "caveats"), ReasonCode.DENY_CALIBRATION_INSUFFICIENT, min_items=1),
            certification_status=status,
            last_updated_at=expect_datetime_string(last_updated, (*path, "last_updated_at"), ReasonCode.DENY_CONTEXT_STALE) if last_updated is not None else None,
        )


__all__ = [
    "ALLOWED_CALIBRATION_SOURCES",
    "CalibrationProfile",
    "CalibrationUncertainty",
    "EdgeWeightPolicy",
    "EvidenceWindow",
]
