"""Typed loss contract arcana.loss.v1: unit, horizon, source and method bound to AaR/AES bounds.

The contract binds a loss estimate to the risk model, calibration profile, decision horizon, unit
and evidence that produced it. Two methods are supported:

- ``declared_upper_bounds``: the supplier states AaR_99 and AES_99 upper bounds and the probability
  that they fail. ARCANA checks domains, the AES >= AaR normal form and the bindings, not the values.
- ``dkw_empirical_upper``: ARCANA computes the bounds from n i.i.d. losses with declared support
  [0, B]. Off the Dvoretzky-Kiefer-Wolfowitz-Massart event, whose probability is at most
  delta = 2 exp(-2 n eps^2), the true CDF is at least F_n - eps. Moving mass eps from the lowest
  observations to B gives a law that stochastically dominates the true one, so its quantile and
  expected shortfall bound AaR_99 and AES_99 together.

Quantiles use q_u = inf{z : F(z) >= u} and AES_alpha = integral from alpha to 1 of q_u du / (1 - alpha),
which handles atoms and ties; alpha is the exact rational 99/100. Statistical validity still rests on
the declared sampling premises; ARCANA does not verify them.
"""

from __future__ import annotations

import hmac
import math
from functools import lru_cache
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from fractions import Fraction
from typing import Any

from arcana._numerics import outward_float
from arcana._validation import (
    expect_bool, expect_calibration_profile_id, expect_datetime_string, expect_enum, expect_mapping,
    expect_non_empty_string, expect_number_min, expect_number_range, expect_risk_model_version, expect_sha256, fail,
)
from arcana.errors import LossMethod, LossSource, ReasonCode
from arcana.increments import _hash
from arcana.loss import LossBoundEvaluation
from arcana.model import DecisionHorizon, LossBounds, LossPolicy, validate_loss_tail_order

LOSS_CONTRACT_VERSION = "arcana.loss.v1"
LOSS_ALPHA = 0.99
QUANTILE_CONVENTION = "lower_quantile_integral"
MAX_LOSS_SAMPLES = 100_000

_ALPHA = Fraction(99, 100)
# Relative inflation of eps that dominates the rounding of log, division and sqrt in binary64.
_EPSILON_INFLATION = 1 + Fraction(1, 2**40)
_INVALID = ReasonCode.DENY_LOSS_MODEL_INVALID
_STALE = ReasonCode.DENY_CONTEXT_STALE
_REQUIRED = {"schema_version", "risk_model_version", "calibration_profile_id", "decision_horizon", "unit", "method",
             "failure_probability_upper", "evidence_hash", "evidence_source_id", "source_kind", "valid_from", "expires_at",
             "alpha", "quantile_convention", "binding_hash"}
_OPTIONAL = {"aar_99_upper", "aes_99_upper", "sample", "support_upper"}


def _time(value: Any, path: tuple) -> datetime:
    value = expect_datetime_string(value, path, _STALE)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        fail("loss_time_timezone_missing", _STALE, "use a timezone-aware time", path)
    return parsed


def _nonblank(value: Any, name: str) -> str:
    value = expect_non_empty_string(value, ("loss", name), _INVALID)
    if not value.strip():
        fail(f"loss_{name}_blank", _INVALID, f"identify the {name}", ("loss", name))
    return value


@dataclass(frozen=True)
class LossEstimate:
    aar_99_upper: Fraction
    aes_99_upper: Fraction
    aar_99_empirical: Fraction | None = None
    aes_99_empirical: Fraction | None = None
    epsilon: Fraction | None = None


@dataclass(frozen=True)
class LossContract:
    risk_model_version: str
    calibration_profile_id: str
    decision_horizon: DecisionHorizon
    unit: str
    method: LossMethod
    failure_probability_upper: float
    evidence_hash: str
    evidence_source_id: str
    source_kind: LossSource
    valid_from: str
    expires_at: str
    aar_99_upper: float | None = None
    aes_99_upper: float | None = None
    sample: tuple[float, ...] = ()
    support_upper: float | None = None
    alpha: float = LOSS_ALPHA
    quantile_convention: str = QUANTILE_CONVENTION
    schema_version: str = LOSS_CONTRACT_VERSION
    binding_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != LOSS_CONTRACT_VERSION:
            fail("loss_version_unsupported", _INVALID, "use arcana.loss.v1", ("loss", "schema_version"))
        expect_risk_model_version(self.risk_model_version, ("loss", "risk_model_version"))
        expect_calibration_profile_id(self.calibration_profile_id, ("loss", "calibration_profile_id"))
        if not isinstance(self.decision_horizon, DecisionHorizon):
            fail("loss_horizon_invalid", ReasonCode.DENY_DECISION_HORIZON_MISMATCH, "provide a DecisionHorizon", ("loss", "decision_horizon"))
        object.__setattr__(self, "decision_horizon", DecisionHorizon.from_mapping(vars(self.decision_horizon), ("loss", "decision_horizon")))
        for name in ("unit", "evidence_source_id"):
            _nonblank(getattr(self, name), name)
        expect_sha256(self.evidence_hash, ("loss", "evidence_hash"), _INVALID)
        method = expect_enum(LossMethod, self.method, ("loss", "method"), _INVALID)
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "source_kind", expect_enum(LossSource, self.source_kind, ("loss", "source_kind"), _INVALID))
        if expect_number_range(self.alpha, 0, 1, ("loss", "alpha"), _INVALID) != LOSS_ALPHA:
            fail("loss_alpha_unsupported", _INVALID, "this reference supports alpha = 0.99 only", ("loss", "alpha"))
        if self.quantile_convention != QUANTILE_CONVENTION:
            fail("loss_quantile_convention_unsupported", _INVALID,
                 "use the lower quantile and the quantile-integral expected shortfall", ("loss", "quantile_convention"))
        if _time(self.valid_from, ("loss", "valid_from")) >= _time(self.expires_at, ("loss", "expires_at")):
            fail("loss_window_invalid", _STALE, "expires_at must follow valid_from", ("loss", "expires_at"))
        delta = expect_number_range(self.failure_probability_upper, 0, 1, ("loss", "failure_probability_upper"), _INVALID)
        if delta == 1:
            fail("loss_failure_probability_vacuous", _INVALID, "a failure probability of one bounds nothing",
                 ("loss", "failure_probability_upper"))
        object.__setattr__(self, "failure_probability_upper", delta)
        if method is LossMethod.DECLARED_UPPER_BOUNDS:
            self._check_declared()
        else:
            self._check_sample(delta)
        object.__setattr__(self, "binding_hash", _hash(self._identity()))

    def _check_declared(self) -> None:
        if self.support_upper is not None or not (isinstance(self.sample, (tuple, list)) and len(self.sample) == 0):
            fail("loss_sample_unexpected", _INVALID, "declared bounds carry no sample", ("loss", "sample"))
        bounds = [expect_number_min(getattr(self, name), 0, ("loss", name), _INVALID) for name in ("aar_99_upper", "aes_99_upper")]
        validate_loss_tail_order(*bounds, ("loss", "aes_99_upper"))
        object.__setattr__(self, "aar_99_upper", bounds[0])
        object.__setattr__(self, "aes_99_upper", bounds[1])

    def _check_sample(self, delta: float) -> None:
        if self.aar_99_upper is not None or self.aes_99_upper is not None:
            fail("loss_declared_bounds_unexpected", _INVALID, "the estimator computes the bounds; omit them", ("loss", "aar_99_upper"))
        if delta == 0:
            fail("loss_failure_probability_invalid", _INVALID, "the estimator needs a positive failure probability",
                 ("loss", "failure_probability_upper"))
        support = expect_number_min(self.support_upper, 0, ("loss", "support_upper"), _INVALID)
        if isinstance(self.sample, (str, bytes)) or not isinstance(self.sample, Sequence):
            fail("loss_sample_invalid", _INVALID, "provide a finite sequence of losses", ("loss", "sample"))
        if not 1 <= len(self.sample) <= MAX_LOSS_SAMPLES:
            fail("loss_sample_size_invalid", _INVALID, "provide 1 to 100000 losses", ("loss", "sample"))
        sample = tuple(expect_number_min(value, 0, ("loss", "sample", index), _INVALID) for index, value in enumerate(self.sample))
        if max(sample) > support:
            fail("loss_sample_outside_support", _INVALID, "every loss must lie in [0, support_upper]", ("loss", "sample"))
        object.__setattr__(self, "support_upper", support)
        object.__setattr__(self, "sample", sample)

    def _wire(self) -> dict[str, Any]:
        wire = {"schema_version": self.schema_version, "risk_model_version": self.risk_model_version,
                "calibration_profile_id": self.calibration_profile_id, "decision_horizon": vars(self.decision_horizon),
                "unit": self.unit, "method": self.method.value, "failure_probability_upper": self.failure_probability_upper,
                "evidence_hash": self.evidence_hash, "evidence_source_id": self.evidence_source_id,
                "source_kind": self.source_kind.value, "valid_from": self.valid_from, "expires_at": self.expires_at,
                "alpha": self.alpha, "quantile_convention": self.quantile_convention}
        if self.method is LossMethod.DECLARED_UPPER_BOUNDS:
            wire.update(aar_99_upper=self.aar_99_upper, aes_99_upper=self.aes_99_upper)
        else:
            wire.update(sample=list(self.sample), support_upper=self.support_upper)
        return wire

    def _identity(self) -> dict[str, Any]:
        wire = self._wire()
        for name in ("failure_probability_upper", "alpha", "aar_99_upper", "aes_99_upper", "support_upper"):
            if name in wire:
                wire[name] = float(wire[name]).hex()
        if "sample" in wire:
            wire["sample"] = [value.hex() for value in self.sample]
        return wire

    def validated_snapshot(self) -> LossContract:
        contract = replace(self)
        supplied = expect_sha256(self.binding_hash, ("loss", "binding_hash"), _INVALID)
        if not hmac.compare_digest(contract.binding_hash, supplied):
            fail("loss_binding_hash_mismatch", _INVALID, "rebuild the loss contract after changing inputs", ("loss",))
        return contract

    def to_mapping(self) -> dict[str, Any]:
        contract = self.validated_snapshot()
        return {**contract._wire(), "binding_hash": contract.binding_hash}

    @classmethod
    def from_mapping(cls, value: Any, path: tuple = ("loss",)) -> LossContract:
        data = expect_mapping(value, path, _INVALID)
        for name in sorted(_REQUIRED):
            if name not in data:
                fail(f"loss_{name}_missing", _INVALID, f"provide the required {name}", (*path, name))
        if set(data) - _REQUIRED - _OPTIONAL:
            fail("loss_field_unknown", _INVALID, "remove unsupported loss fields", path)
        data = dict(data)
        supplied = expect_sha256(data.pop("binding_hash"), (*path, "binding_hash"), _INVALID)
        data["decision_horizon"] = DecisionHorizon.from_mapping(data["decision_horizon"], (*path, "decision_horizon"))
        if "sample" in data:
            if isinstance(data["sample"], (str, bytes)) or not isinstance(data["sample"], Sequence):
                fail("loss_sample_invalid", _INVALID, "provide an array of losses", (*path, "sample"))
            data["sample"] = tuple(data["sample"])
        contract = cls(**data)
        if not hmac.compare_digest(contract.binding_hash, supplied):
            fail("loss_binding_hash_mismatch", _INVALID, "hash must bind the complete loss contract", (*path, "binding_hash"))
        return contract


def loss_estimate(contract: LossContract) -> LossEstimate:
    """Exact upper bounds (and, for the estimator, the plug-in values) of AaR_99 and AES_99."""
    if not isinstance(contract, LossContract):
        fail("loss_contract_invalid", _INVALID, "provide a typed LossContract", ("loss",))
    return _estimate(contract.validated_snapshot())


@lru_cache(maxsize=4)
def _estimate(checked: LossContract) -> LossEstimate:
    """Memoized by content: FastGate evaluates the same contract before and after the matrix update."""
    if checked.method is LossMethod.DECLARED_UPPER_BOUNDS:
        return LossEstimate(Fraction(checked.aar_99_upper), Fraction(checked.aes_99_upper))
    n = len(checked.sample)
    epsilon = dkw_epsilon(n, checked.failure_probability_upper)
    mass = Fraction(1, n)
    observed = sorted(Fraction(value) for value in checked.sample)
    empirical = tail_metrics([(value, mass) for value in observed])
    remaining, shifted = epsilon, []
    for value in observed:
        taken = min(mass, remaining)
        remaining -= taken
        if mass > taken:
            shifted.append((value, mass - taken))
    shifted.append((Fraction(checked.support_upper), epsilon))
    upper = tail_metrics(shifted)
    return LossEstimate(upper[0], upper[1], empirical[0], empirical[1], epsilon)


def dkw_epsilon(n: int, delta: float) -> Fraction:
    """Rational upper bound of sqrt(ln(2 / delta) / (2 n)), capped at 1."""
    ratio = 2 / delta
    if not math.isfinite(ratio):
        return Fraction(1)
    return min(Fraction(1), Fraction(math.sqrt(math.log(ratio) / (2 * n))) * _EPSILON_INFLATION)


def tail_metrics(atoms: list[tuple[Fraction, Fraction]], alpha: Fraction = _ALPHA) -> tuple[Fraction, Fraction]:
    """(q_alpha, AES_alpha) of a discrete law given as ascending (value, mass) atoms of total mass 1."""
    cumulative, quantile, integral = Fraction(0), None, Fraction(0)
    for value, mass in atoms:
        low, high = cumulative, cumulative + mass
        cumulative = high
        if high < alpha:  # entirely below the tail
            continue
        if quantile is None:
            quantile = value
        integral += value * (high - max(low, alpha))
    if quantile is None or cumulative != 1:
        fail("loss_distribution_invalid", _INVALID, "atoms must carry total mass one", ("loss",))
    return quantile, integral / (1 - alpha)


def loss_policy_hash(policy: LossPolicy) -> str:
    if not isinstance(policy, LossPolicy):
        fail("loss_policy_invalid", _INVALID, "provide a LossPolicy", ("loss_policy",))
    checked = replace(policy)
    data = {**vars(checked), **{name: float(getattr(checked, name)).hex()
                                for name in ("max_allowed_aar_99", "max_allowed_aes_99", "max_failure_probability")}}
    return _hash({"domain": "arcana.loss.policy.v1", **data})


def validate_loss_binding(
    contract: LossContract | None, policy: LossPolicy | None, *, loss_in_scope: bool, legacy_bounds: LossBounds | None,
    risk_model_version: str, calibration_profile_id: str, decision_horizon: DecisionHorizon, decision_time: datetime,
) -> LossContract | None:
    """Bind a loss contract to the evaluation context and policy; None keeps the legacy path."""
    in_scope = expect_bool(loss_in_scope, ("loss_in_scope",), _INVALID)
    if contract is None:
        if policy is not None and in_scope:
            fail("loss_contract_missing", _INVALID, "the budget requires a typed loss contract", ("loss",))
        return None
    if not isinstance(contract, LossContract):
        fail("loss_contract_invalid", _INVALID, "provide a typed LossContract", ("loss",))
    if policy is None:
        fail("loss_policy_missing", _INVALID, "declare the loss unit and limits in the budget", ("loss_policy",))
    loss_policy_hash(policy)
    if not in_scope:
        fail("loss_contract_out_of_scope", _INVALID, "set loss_in_scope when supplying a loss contract", ("loss_in_scope",))
    if legacy_bounds is not None:
        fail("loss_scalar_override_forbidden", _INVALID, "omit loss_bounds; the loss contract carries the bounds", ("loss_bounds",))
    checked = contract.validated_snapshot()
    for name, actual, expected, reason in (
        ("risk_model", checked.risk_model_version, risk_model_version, ReasonCode.DENY_RISK_MODEL_UNSUPPORTED),
        ("calibration_profile", checked.calibration_profile_id, calibration_profile_id, ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
        ("horizon", checked.decision_horizon, decision_horizon, ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
        ("unit", checked.unit, policy.unit, _INVALID),
        ("evidence_hash", checked.evidence_hash, policy.evidence_hash, _INVALID),
        ("evidence_source", checked.evidence_source_id, policy.evidence_source_id, _INVALID),
    ):
        if actual != expected:
            fail(f"loss_{name}_mismatch", reason, f"bind the loss estimate to the current {name}", ("loss", name))
    if Fraction(checked.failure_probability_upper) > Fraction(policy.max_failure_probability):
        fail("loss_failure_budget_exceeded", _INVALID,
             "the loss bound fails too often for the policy; add evidence or relax the failure budget", ("loss", "failure_probability_upper"))
    if policy.require_empirical_qualification:
        fail("loss_empirical_review_required", _INVALID,
             "synthetic or externally declared loss evidence is not empirical approval", ("loss", "source_kind"))
    if not isinstance(decision_time, datetime) or decision_time.tzinfo is None:
        fail("loss_decision_time_invalid", _STALE, "provide a timezone-aware decision time", ("decision_time",))
    try:
        end = decision_time + timedelta(seconds=checked.decision_horizon.duration_seconds)
    except OverflowError:
        fail("loss_horizon_end_unrepresentable", _STALE, "use a representable decision horizon", ("decision_horizon",))
    if decision_time < _time(checked.valid_from, ("loss", "valid_from")):
        fail("loss_not_yet_valid", _STALE, "wait for evidence validity", ("loss",))
    expires = _time(checked.expires_at, ("loss", "expires_at"))
    if decision_time >= expires:
        fail("loss_expired", _STALE, "refresh loss evidence", ("loss",))
    if end > expires:
        fail("loss_horizon_not_covered", _STALE, "evidence must cover the entire decision horizon", ("loss",))
    return checked


def evaluate_loss_contract(contract: LossContract, policy: LossPolicy) -> LossBoundEvaluation:
    """Compare the contract's upper bounds with the policy limits (after validate_loss_binding)."""
    checked = contract.validated_snapshot()
    estimate = loss_estimate(checked)
    metrics: dict[str, Any] = {
        "loss_contract_version": LOSS_CONTRACT_VERSION, "loss_binding_hash": checked.binding_hash,
        "loss_policy_hash": loss_policy_hash(policy), "loss_method": checked.method.value, "loss_unit": checked.unit,
        "loss_source_kind": checked.source_kind.value, "loss_failure_probability_upper": checked.failure_probability_upper,
        "aar_99_upper": outward_float(estimate.aar_99_upper, upper=True),
        "aes_99_upper": outward_float(estimate.aes_99_upper, upper=True),
        "max_allowed_aar_99": policy.max_allowed_aar_99, "max_allowed_aes_99": policy.max_allowed_aes_99,
        "loss_empirical_qualification": "not_established",
        "loss_evidence_assurance": "declared_premises_not_empirically_verified",
    }
    if estimate.epsilon is not None:
        metrics.update(loss_sample_size=len(checked.sample), loss_dkw_epsilon=outward_float(estimate.epsilon, upper=True),
                       aar_99_empirical=float(estimate.aar_99_empirical), aes_99_empirical=float(estimate.aes_99_empirical))
    if estimate.aar_99_upper > Fraction(policy.max_allowed_aar_99):
        return LossBoundEvaluation(metrics, ReasonCode.DENY_AAR_UPPER_BOUND, "aar_upper_bound_exceeded")
    if estimate.aes_99_upper > Fraction(policy.max_allowed_aes_99):
        return LossBoundEvaluation(metrics, ReasonCode.DENY_AES_UPPER_BOUND, "aes_upper_bound_exceeded")
    return LossBoundEvaluation(metrics)


__all__ = [
    "LOSS_ALPHA",
    "LOSS_CONTRACT_VERSION",
    "MAX_LOSS_SAMPLES",
    "QUANTILE_CONVENTION",
    "LossContract",
    "LossEstimate",
    "dkw_epsilon",
    "evaluate_loss_contract",
    "loss_estimate",
    "loss_policy_hash",
    "tail_metrics",
    "validate_loss_binding",
]
