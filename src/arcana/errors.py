"""Public ARCANA reason codes, verdicts, and validation errors."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class ReasonCode(str, Enum):
    ALLOW_BOUNDED_AUTONOMY = "ARCANA_ALLOW_BOUNDED_AUTONOMY"
    ALLOW_WITH_CONTROLS = "ARCANA_ALLOW_WITH_CONTROLS"
    DENY_CALIBRATION_INSUFFICIENT = "ARCANA_DENY_CALIBRATION_INSUFFICIENT"
    DENY_RISK_MODEL_UNSUPPORTED = "ARCANA_DENY_RISK_MODEL_UNSUPPORTED"
    DENY_MODEL_INPUT_INVALID = "ARCANA_DENY_MODEL_INPUT_INVALID"
    DENY_CONTEXT_STALE = "ARCANA_DENY_CONTEXT_STALE"
    DENY_GRAPH_HASH_MISMATCH = "ARCANA_DENY_GRAPH_HASH_MISMATCH"
    DENY_DECISION_HORIZON_MISMATCH = "ARCANA_DENY_DECISION_HORIZON_MISMATCH"
    DENY_RHO_UPPER_BOUND = "ARCANA_DENY_RHO_UPPER_BOUND"
    DENY_AAR_UPPER_BOUND = "ARCANA_DENY_AAR_UPPER_BOUND"
    DENY_LOSS_MODEL_INVALID = "ARCANA_DENY_LOSS_MODEL_INVALID"
    DENY_AES_UPPER_BOUND = "ARCANA_DENY_AES_UPPER_BOUND"
    DENY_BUDGET_EXHAUSTED = "ARCANA_DENY_BUDGET_EXHAUSTED"
    DENY_FASTGATE_UNCERTAIN = "ARCANA_DENY_FASTGATE_UNCERTAIN"
    DENY_FASTGATE_VECTOR_INVALID = "ARCANA_DENY_FASTGATE_VECTOR_INVALID"
    DENY_DISTILLATION_RISK = "ARCANA_DENY_DISTILLATION_RISK"
    REQUIRE_HUMAN_GATE = "ARCANA_REQUIRE_HUMAN_GATE"
    REQUIRE_SCOPE_REDUCTION = "ARCANA_REQUIRE_SCOPE_REDUCTION"
    REQUIRE_OBSERVE_ONLY = "ARCANA_REQUIRE_OBSERVE_ONLY"
    INFO_A0_NON_CERTIFIABLE = "ARCANA_INFO_A0_NON_CERTIFIABLE"
    INFO_SYNTHETIC_FIXTURE = "ARCANA_INFO_SYNTHETIC_FIXTURE"


class Verdict(str, Enum):
    ALLOW_BOUNDED_AUTONOMY = "allow_bounded_autonomy"
    ALLOW_WITH_CONTROLS = "allow_with_controls"
    REQUIRE_SCOPE_REDUCTION = "require_scope_reduction"
    REQUIRE_HUMAN_GATE = "require_human_gate"
    OBSERVE_ONLY = "observe_only"
    DENY = "deny"


class CalibrationLevel(str, Enum):
    A0 = "A0"
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"


class CertificationStatus(str, Enum):
    NON_CERTIFIABLE = "non_certifiable"
    CERTIFIABLE_UNDER_PROFILE = "certifiable_under_profile"


class FastGateMode(str, Enum):
    PERRON_COLLATZ_BOUND = "perron_collatz_bound"
    EXACT_RECOMPUTE = "exact_recompute"
    OBSERVE_ONLY = "observe_only"


class PositiveVectorMethod(str, Enum):
    IRREDUCIBLE_PERRON_VECTOR = "irreducible_perron_vector"
    SCC_DECOMPOSITION = "scc_decomposition"
    EPSILON_FLOOR = "epsilon_floor"
    COMPONENT_LOCAL_GATE = "component_local_gate"
    FALLBACK_EXACT = "fallback_exact"


class SchemaVersion(str, Enum):
    CALIBRATION_PROFILE_V02 = "arcana.calibration_profile.v0.2"
    CONTEXT_V02 = "arcana.context.v0.2"
    CERTIFICATE_V02 = "arcana.certificate.v0.2"
    BENCHMARK_SCENARIO_V02 = "arcana.benchmark_scenario.v0.2"
    BENCHMARK_EXECUTION_SUITE_V01 = "arcana.benchmark_execution_suite.v0.1"


PathPart = str | int


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    reason_code: ReasonCode
    message: str
    path: tuple[PathPart, ...] = ()

    @property
    def path_text(self) -> str:
        if not self.path:
            return "$"
        rendered = "$"
        for part in self.path:
            if isinstance(part, int):
                rendered += f"[{part}]"
            else:
                rendered += f".{part}"
        return rendered


class ArcanaValidationError(ValueError):
    """Validation failure carrying stable ARCANA reason codes."""

    def __init__(self, issues: ValidationIssue | Iterable[ValidationIssue]):
        if isinstance(issues, ValidationIssue):
            normalized = (issues,)
        else:
            normalized = tuple(issues)
        if not normalized:
            normalized = (
                ValidationIssue(
                    code="validation_failed",
                    reason_code=ReasonCode.DENY_MODEL_INPUT_INVALID,
                    message="validation failed without a concrete issue",
                ),
            )
        self.issues = normalized
        self.primary_issue = normalized[0]
        super().__init__(self._message())

    @property
    def reason_code(self) -> ReasonCode:
        return self.primary_issue.reason_code

    @property
    def code(self) -> str:
        return self.primary_issue.code

    def _message(self) -> str:
        issue = self.primary_issue
        return f"{issue.reason_code.value} {issue.code} at {issue.path_text}: {issue.message}"


__all__ = [
    "ArcanaValidationError",
    "CalibrationLevel",
    "CertificationStatus",
    "FastGateMode",
    "PathPart",
    "PositiveVectorMethod",
    "ReasonCode",
    "SchemaVersion",
    "ValidationIssue",
    "Verdict",
]
