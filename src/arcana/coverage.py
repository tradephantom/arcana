"""Conditional finite-family coverage accounting, not empirical qualification."""

from __future__ import annotations

import hmac
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from fractions import Fraction
from typing import Any

import numpy as np

from arcana._numerics import outward_float
from arcana._validation import (
    expect_bool, expect_calibration_profile_id, expect_datetime_string, expect_enum,
    expect_mapping, expect_non_empty_string, expect_number_range, expect_risk_model_version,
    expect_sha256, fail,
)
from arcana.errors import CoverageMethod, CoverageSource, IncrementScope, ReasonCode
from arcana.increments import IncrementContract, _hash, _matrix, _matrix_identity, _matrix_wire
from arcana.matrices import PropagationMatrix
from arcana.model import CoveragePolicy, DecisionHorizon
from arcana.temporal import TemporalContract


COVERAGE_CONTRACT_VERSION = "arcana.coverage.v1"
MAX_COVERAGE_NODES = 64
MAX_COVERAGE_TERMS = 2 * MAX_COVERAGE_NODES ** 2 + 1
_INVALID = ReasonCode.DENY_MODEL_INPUT_INVALID
_EVIDENCE = ReasonCode.DENY_CALIBRATION_INSUFFICIENT


def _fields(value: Any, required: set[str], optional: set[str], path: tuple) -> dict:
    data = expect_mapping(value, path, _INVALID)
    for name in sorted(required):
        if name not in data:
            fail(f"coverage_{name}_missing", _INVALID, f"provide the required {name}", (*path, name))
    if set(data) - required - optional:
        fail("coverage_field_unknown", _INVALID, "remove unsupported coverage fields", path)
    return dict(data)


def _time(value: Any, path: tuple) -> datetime:
    value = expect_datetime_string(value, path, ReasonCode.DENY_CONTEXT_STALE)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        fail("coverage_time_timezone_missing", ReasonCode.DENY_CONTEXT_STALE, "use a timezone-aware time", path)
    return parsed


def _nonblank(value: Any, name: str) -> str:
    value = expect_non_empty_string(value, ("coverage", name), _EVIDENCE)
    if not value.strip():
        fail(f"coverage_{name}_blank", _EVIDENCE, f"identify the {name}", ("coverage", name))
    return value


def _claim_ids(size: int, before_lower: bool, temporal: bool) -> tuple[str, ...]:
    claims = [f"current_upper:{i}:{j}" for i in range(size) for j in range(size)]
    if before_lower:
        claims.extend(f"before_lower:{i}:{j}" for i in range(size) for j in range(size))
    if temporal:
        claims.append("temporal_joint_premises")
    return tuple(claims)


def _bounded_matrix(value: Any) -> PropagationMatrix:
    if (isinstance(value, PropagationMatrix) and isinstance(value.values, np.ndarray)
            and any(n > MAX_COVERAGE_NODES for n in value.values.shape)):
        fail("coverage_node_limit_exceeded", _INVALID, "use at most 64 nodes in this reference contract", ("coverage", "current_upper"))
    matrix = _matrix(value, ("coverage", "current_upper"))
    if matrix.size > MAX_COVERAGE_NODES:
        fail("coverage_node_limit_exceeded", _INVALID, "use at most 64 nodes in this reference contract", ("coverage", "current_upper"))
    return matrix


@dataclass(frozen=True)
class CoverageFailureBound:
    claim_id: str
    failure_probability_upper: float

    def __post_init__(self) -> None:
        _nonblank(self.claim_id, "claim_id")
        object.__setattr__(self, "failure_probability_upper", expect_number_range(
            self.failure_probability_upper, 0, 1, ("coverage", "failure_probability_upper"), _EVIDENCE))

    @classmethod
    def from_mapping(cls, value: Any) -> CoverageFailureBound:
        return cls(**_fields(value, {"claim_id", "failure_probability_upper"}, set(), ("coverage", "bounds")))


@dataclass(frozen=True)
class CoverageContract:
    risk_model_version: str
    calibration_profile_id: str
    decision_horizon: DecisionHorizon
    current_upper: PropagationMatrix
    method: CoverageMethod
    bounds: tuple[CoverageFailureBound, ...]
    population_id: str
    design_hash: str
    evidence_hash: str
    evidence_source_id: str
    source_kind: CoverageSource
    valid_from: str
    expires_at: str
    selection_protocol: str
    factor_semantics: str
    dependence: str
    increment_binding_hash: str | None = None
    before_lower_required: bool = False
    temporal_binding_hash: str | None = None
    schema_version: str = COVERAGE_CONTRACT_VERSION
    binding_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != COVERAGE_CONTRACT_VERSION:
            fail("coverage_version_unsupported", _INVALID, "use arcana.coverage.v1", ("coverage", "schema_version"))
        expect_risk_model_version(self.risk_model_version, ("coverage", "risk_model_version"))
        expect_calibration_profile_id(self.calibration_profile_id, ("coverage", "calibration_profile_id"))
        if not isinstance(self.decision_horizon, DecisionHorizon):
            fail("coverage_horizon_invalid", ReasonCode.DENY_DECISION_HORIZON_MISMATCH,
                 "provide a DecisionHorizon", ("coverage", "decision_horizon"))
        object.__setattr__(self, "decision_horizon", DecisionHorizon.from_mapping(vars(self.decision_horizon)))
        matrix = _bounded_matrix(self.current_upper)
        object.__setattr__(self, "current_upper", matrix)
        object.__setattr__(self, "method", expect_enum(CoverageMethod, self.method, ("coverage", "method"), _EVIDENCE))
        object.__setattr__(self, "source_kind", expect_enum(CoverageSource, self.source_kind, ("coverage", "source_kind"), _EVIDENCE))
        for name in ("population_id", "evidence_source_id"):
            _nonblank(getattr(self, name), name)
        for name in ("design_hash", "evidence_hash"):
            expect_sha256(getattr(self, name), ("coverage", name), _EVIDENCE)
        for name in ("increment_binding_hash", "temporal_binding_hash"):
            if getattr(self, name) is not None:
                expect_sha256(getattr(self, name), ("coverage", name), _EVIDENCE)
        expect_bool(self.before_lower_required, ("coverage", "before_lower_required"), _INVALID)
        if self.before_lower_required and self.increment_binding_hash is None:
            fail("coverage_baseline_binding_missing", _EVIDENCE, "bind the calibrated increment baseline", ("coverage",))
        for name, expected, guidance in (
            ("selection_protocol", "fixed_prespecified_family", "adaptive/anytime selection requires a different reviewed contract"),
            ("factor_semantics", "direct_operator_bounds", "factor products do not establish operator bounds; supply direct bounds"),
            ("dependence", "arbitrary", "do not assume independence; use union or full joint bounds"),
        ):
            if getattr(self, name) != expected:
                fail(f"coverage_{name}_unsupported", _EVIDENCE, guidance, ("coverage", name))
        if _time(self.valid_from, ("coverage", "valid_from")) >= _time(self.expires_at, ("coverage", "expires_at")):
            fail("coverage_window_invalid", ReasonCode.DENY_CONTEXT_STALE,
                 "expires_at must follow valid_from", ("coverage", "expires_at"))
        if isinstance(self.bounds, (str, bytes)) or not isinstance(self.bounds, Sequence):
            fail("coverage_bounds_invalid", _EVIDENCE, "provide a finite sequence of CoverageFailureBound", ("coverage", "bounds"))
        if not 1 <= len(self.bounds) <= MAX_COVERAGE_TERMS:
            fail("coverage_term_count_invalid", _EVIDENCE, "provide 1 to 8193 bounds", ("coverage", "bounds"))
        bounds = []
        for index, bound in enumerate(self.bounds):
            if not isinstance(bound, CoverageFailureBound):
                fail("coverage_bound_invalid", _EVIDENCE, "provide a CoverageFailureBound", ("coverage", "bounds", index))
            bounds.append(replace(bound))
        ids = [bound.claim_id for bound in bounds]
        if len(ids) != len(set(ids)):
            fail("coverage_claim_duplicate", _EVIDENCE, "provide one bound per required claim", ("coverage", "bounds"))
        if self.method is CoverageMethod.UNION_BOUND:
            expected = set(self.claim_ids)
        elif self.method is CoverageMethod.JOINT_BOUND:
            expected = {"complete_family"}
        else:
            fail("coverage_method_unsupported", _EVIDENCE, "select a supported composition method", ("coverage", "method"))
        if set(ids) - expected:
            fail("coverage_claim_unknown", _EVIDENCE, "remove claims outside the bound finite family", ("coverage", "bounds"))
        if expected - set(ids):
            fail("coverage_claim_missing", _EVIDENCE, "cover every required claim, including zero matrix entries", ("coverage", "bounds"))
        object.__setattr__(self, "bounds", tuple(sorted(bounds, key=lambda item: item.claim_id)))
        object.__setattr__(self, "binding_hash", _hash(self._identity()))

    @property
    def claim_ids(self) -> tuple[str, ...]:
        return _claim_ids(self.current_upper.size, self.before_lower_required, self.temporal_binding_hash is not None)

    def _wire(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "risk_model_version": self.risk_model_version,
                "calibration_profile_id": self.calibration_profile_id, "decision_horizon": vars(self.decision_horizon),
                "current_upper": _matrix_wire(self.current_upper), "method": self.method.value,
                "bounds": [vars(bound) for bound in self.bounds], "population_id": self.population_id,
                "design_hash": self.design_hash, "evidence_hash": self.evidence_hash,
                "evidence_source_id": self.evidence_source_id, "source_kind": self.source_kind.value,
                "valid_from": self.valid_from, "expires_at": self.expires_at,
                "selection_protocol": self.selection_protocol, "factor_semantics": self.factor_semantics,
                "dependence": self.dependence, "increment_binding_hash": self.increment_binding_hash,
                "before_lower_required": self.before_lower_required, "temporal_binding_hash": self.temporal_binding_hash}

    def _identity(self) -> dict[str, Any]:
        wire = self._wire()
        wire["current_upper"] = _matrix_identity(self.current_upper)
        wire["bounds"] = [{"claim_id": b.claim_id, "binary64_hex": b.failure_probability_upper.hex()} for b in self.bounds]
        return wire

    def validated_snapshot(self) -> CoverageContract:
        contract = replace(self)
        supplied = expect_sha256(self.binding_hash, ("coverage", "binding_hash"), _EVIDENCE)
        if not hmac.compare_digest(contract.binding_hash, supplied):
            fail("coverage_binding_hash_mismatch", _EVIDENCE, "rebuild the coverage contract after changing inputs", ("coverage",))
        return contract

    def to_mapping(self) -> dict[str, Any]:
        contract = self.validated_snapshot()
        return {**contract._wire(), "binding_hash": contract.binding_hash}

    @classmethod
    def from_mapping(cls, value: Any, path: tuple = ("coverage",)) -> CoverageContract:
        required = {"schema_version", "risk_model_version", "calibration_profile_id", "decision_horizon", "current_upper",
                    "method", "bounds", "population_id", "design_hash", "evidence_hash", "evidence_source_id", "source_kind",
                    "valid_from", "expires_at", "selection_protocol", "factor_semantics", "dependence",
                    "increment_binding_hash", "before_lower_required", "temporal_binding_hash", "binding_hash"}
        data = _fields(value, required, set(), path)
        supplied = expect_sha256(data.pop("binding_hash"), (*path, "binding_hash"), _EVIDENCE)
        data["decision_horizon"] = DecisionHorizon.from_mapping(_fields(
            data["decision_horizon"], {"id", "duration_seconds", "context"}, set(), (*path, "decision_horizon")))
        matrix_path = (*path, "current_upper")
        matrix = _fields(data["current_upper"], {"values", "node_order", "graph_hash"}, set(), matrix_path)
        values = matrix["values"]
        if isinstance(values, Sequence) and len(values) > MAX_COVERAGE_NODES:
            fail("coverage_node_limit_exceeded", _INVALID, "use at most 64 nodes in this reference contract", matrix_path)
        if isinstance(values, Sequence):
            for index, row in enumerate(values):
                if isinstance(row, Sequence) and len(row) > MAX_COVERAGE_NODES:
                    fail("coverage_node_limit_exceeded", _INVALID, "use at most 64 columns", (*matrix_path, index))
        data["current_upper"] = PropagationMatrix.from_values(
            values, node_order=matrix["node_order"], graph_hash=matrix["graph_hash"], path=matrix_path)
        bounds = data["bounds"]
        if isinstance(bounds, (str, bytes)) or not isinstance(bounds, Sequence):
            fail("coverage_bounds_invalid", _EVIDENCE, "provide a finite array of bounds", (*path, "bounds"))
        if not 1 <= len(bounds) <= MAX_COVERAGE_TERMS:
            fail("coverage_term_count_invalid", _EVIDENCE, "provide 1 to 8193 bounds", (*path, "bounds"))
        data["bounds"] = tuple(CoverageFailureBound.from_mapping(b) for b in bounds)
        contract = cls(**data)
        if not hmac.compare_digest(contract.binding_hash, supplied):
            fail("coverage_binding_hash_mismatch", _EVIDENCE, "hash must bind the complete coverage contract", (*path, "binding_hash"))
        return contract


def coverage_policy_hash(policy: CoveragePolicy) -> str:
    if not isinstance(policy, CoveragePolicy):
        fail("coverage_policy_invalid", _EVIDENCE, "provide a CoveragePolicy", ("coverage_policy",))
    checked = replace(policy)
    data = {**vars(checked), "max_failure_probability": checked.max_failure_probability.hex()}
    return _hash({"domain": "arcana.coverage.policy.v1", **data})


def validate_coverage_binding(
    contract: CoverageContract | None, policy: CoveragePolicy | None, *, risk_model_version: str,
    calibration_profile_id: str, decision_horizon: DecisionHorizon, decision_time: datetime,
    current_upper: PropagationMatrix, increment: IncrementContract | None = None,
    temporal: TemporalContract | None = None, evidence_hash: str | None = None, evidence_source_id: str | None = None,
) -> CoverageContract | None:
    if policy is None:
        if contract is not None:
            fail("coverage_policy_missing", _EVIDENCE, "declare an independent coverage requirement in the budget", ("coverage_policy",))
        return None
    coverage_policy_hash(policy)
    if contract is None:
        fail("coverage_contract_missing", _EVIDENCE, "provide the required coverage contract", ("coverage",))
    if not isinstance(contract, CoverageContract):
        fail("coverage_contract_invalid", _EVIDENCE, "provide a typed CoverageContract", ("coverage",))
    checked = contract.validated_snapshot()
    for name, actual, expected in (
        ("risk_model", checked.risk_model_version, risk_model_version),
        ("calibration_profile", checked.calibration_profile_id, calibration_profile_id),
        ("horizon", checked.decision_horizon, decision_horizon),
        ("population", checked.population_id, policy.population_id),
        ("design_hash", checked.design_hash, policy.design_hash),
        ("evidence_hash", checked.evidence_hash, policy.evidence_hash),
        ("evidence_source", checked.evidence_source_id, policy.evidence_source_id),
    ):
        if actual != expected:
            fail(f"coverage_{name}_mismatch", _EVIDENCE, f"bind coverage to the current {name}", ("coverage", name))
    if not isinstance(decision_time, datetime) or decision_time.tzinfo is None:
        fail("coverage_decision_time_invalid", ReasonCode.DENY_CONTEXT_STALE,
             "provide a timezone-aware decision time", ("decision_time",))
    try:
        end = decision_time + timedelta(seconds=checked.decision_horizon.duration_seconds)
    except OverflowError:
        fail("coverage_horizon_end_unrepresentable", ReasonCode.DENY_CONTEXT_STALE,
             "use a representable decision horizon", ("decision_horizon",))
    if decision_time < _time(checked.valid_from, ("coverage", "valid_from")):
        fail("coverage_not_yet_valid", ReasonCode.DENY_CONTEXT_STALE, "wait for evidence validity", ("coverage",))
    expires = _time(checked.expires_at, ("coverage", "expires_at"))
    if decision_time >= expires:
        fail("coverage_expired", ReasonCode.DENY_CONTEXT_STALE, "refresh coverage evidence", ("coverage",))
    if end > expires:
        fail("coverage_horizon_not_covered", ReasonCode.DENY_CONTEXT_STALE,
             "evidence must cover the entire half-open decision horizon", ("coverage",))
    current = _bounded_matrix(current_upper)
    if _matrix_identity(current) != _matrix_identity(checked.current_upper):
        fail("coverage_current_matrix_mismatch", _EVIDENCE, "bind the actual evaluated upper matrix and coordinates", ("coverage",))
    for name, value, cls in (("increment", increment, IncrementContract), ("temporal", temporal, TemporalContract)):
        if value is not None and not isinstance(value, cls):
            fail(f"coverage_{name}_invalid", _EVIDENCE, f"provide a typed {name} contract", ("coverage", name))
        verified = None if value is None else value.validated_snapshot()
        actual = getattr(checked, name + "_binding_hash")
        expected = None if verified is None else verified.binding_hash
        if actual != expected:
            fail(f"coverage_{name}_binding_mismatch", _EVIDENCE, f"cover exactly the evaluated {name} contract", ("coverage", name))
        if verified is not None:
            for key in ("risk_model_version", "calibration_profile_id", "decision_horizon"):
                if getattr(verified, key) != getattr(checked, key):
                    fail(f"coverage_{name}_{key}_mismatch", _EVIDENCE,
                         f"align the {name} {key} with the coverage family", ("coverage", name, key))
            if name == "increment":
                if _matrix_identity(verified.after.upper) != _matrix_identity(current):
                    fail("coverage_increment_current_mismatch", _EVIDENCE,
                         "the increment after-state must equal the covered current matrix", ("coverage", name))
            elif name == "temporal":
                if not any(_matrix_identity(op) == _matrix_identity(current) for op in verified.operators):
                    fail("coverage_temporal_current_mismatch", _EVIDENCE,
                         "include the covered current matrix in the temporal family", ("coverage", name))
            if decision_time < _time(verified.valid_from, (name, "valid_from")) or end > _time(verified.expires_at, (name, "expires_at")):
                fail(f"coverage_{name}_window_incomplete", ReasonCode.DENY_CONTEXT_STALE,
                     f"{name} evidence must cover the full decision horizon", ("coverage", name))
    before_lower = increment is not None and increment.scope is IncrementScope.CALIBRATION_ENVELOPE and increment.before.lower is not None
    if checked.before_lower_required != before_lower:
        fail("coverage_baseline_scope_mismatch", _EVIDENCE,
             "include the calibrated before-lower claims exactly when used; zero fallback is deterministic", ("coverage",))
    for name, actual, expected in (("evidence_hash", checked.evidence_hash, evidence_hash),
                                   ("evidence_source", checked.evidence_source_id, evidence_source_id)):
        if expected is not None and actual != expected:
            fail(f"coverage_request_{name}_mismatch", _EVIDENCE, f"match request {name}", ("coverage", name))
    return checked


def _coverage_metrics(contract: CoverageContract, policy: CoveragePolicy) -> dict[str, Any]:
    """Internal composition after context binding, without empirical promotion."""
    if not isinstance(contract, CoverageContract):
        fail("coverage_contract_invalid", _EVIDENCE, "provide a CoverageContract", ("coverage",))
    checked = contract.validated_snapshot()
    policy_digest = coverage_policy_hash(policy)
    if checked.method is CoverageMethod.UNION_BOUND:
        failure = min(Fraction(1), sum((Fraction(b.failure_probability_upper) for b in checked.bounds), Fraction(0)))
    elif checked.method is CoverageMethod.JOINT_BOUND:
        failure = Fraction(checked.bounds[0].failure_probability_upper)
    else:
        fail("coverage_method_unsupported", _EVIDENCE, "use a supported method", ("coverage", "method"))
    if failure > Fraction(policy.max_failure_probability):
        fail("coverage_failure_budget_exceeded", _EVIDENCE,
             "the composed failure bound exceeds policy; strengthen evidence or reduce the fixed claim family", ("coverage", "bounds"))
    if policy.require_empirical_qualification:
        if checked.source_kind is CoverageSource.SYNTHETIC_FIXTURE:
            fail("coverage_synthetic_not_empirical", _EVIDENCE,
                 "synthetic fixtures cannot satisfy empirical qualification", ("coverage", "source_kind"))
        if checked.source_kind is CoverageSource.EXTERNAL_UNVERIFIED:
            fail("coverage_empirical_review_required", _EVIDENCE,
                 "external hashes/labels are not empirical approval; use a separately qualified evidence gate", ("coverage", "source_kind"))
        fail("coverage_source_unsupported", _EVIDENCE, "use a supported source kind", ("coverage", "source_kind"))
    return {"coverage_contract_version": COVERAGE_CONTRACT_VERSION, "coverage_scope": "conditional_fixed_family",
            "coverage_binding_hash": checked.binding_hash, "coverage_policy_hash": policy_digest,
            "coverage_method": checked.method.value, "coverage_claim_count": len(checked.claim_ids),
            "coverage_failure_probability_upper": outward_float(failure, upper=True),
            "coverage_probability_lower": outward_float(1 - failure, upper=False),
            "coverage_dependence": checked.dependence, "coverage_source_kind": checked.source_kind.value,
            "coverage_empirical_qualification": "not_established",
            "coverage_evidence_assurance": "declared_premises_not_empirically_verified"}


def evaluate_coverage(
    contract: CoverageContract, policy: CoveragePolicy, *, decision_time: str,
    current_upper: PropagationMatrix, increment: IncrementContract | None = None,
    temporal: TemporalContract | None = None,
) -> dict[str, Any]:
    """Evaluate a conditional coverage contract against the supplied source context."""
    if not isinstance(contract, CoverageContract):
        fail("coverage_contract_invalid", _EVIDENCE, "provide a CoverageContract", ("coverage",))
    checked = validate_coverage_binding(
        contract, policy, risk_model_version=contract.risk_model_version,
        calibration_profile_id=contract.calibration_profile_id, decision_horizon=contract.decision_horizon,
        decision_time=_time(decision_time, ("decision_time",)), current_upper=current_upper,
        increment=increment, temporal=temporal,
    )
    assert checked is not None
    return _coverage_metrics(checked, policy)
