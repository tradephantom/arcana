"""Versioned, conditional increment accounting for represented matrix envelopes."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
import hashlib
import hmac
import json
from typing import Any, Mapping

import numpy as np

from arcana._numerics import nonnegative_difference_upper
from arcana._validation import (
    expect_calibration_profile_id, expect_datetime_string, expect_enum,
    expect_mapping, expect_non_empty_string, expect_risk_model_version,
    expect_sha256, fail,
)
from arcana.errors import IncrementScope, ReasonCode
from arcana.matrices import PropagationMatrix, spectral_bounds
from arcana.model import AutonomyBudget, DecisionHorizon


INCREMENT_CONTRACT_VERSION = "arcana.increment.v1"
_INVALID = ReasonCode.DENY_MODEL_INPUT_INVALID
_EVIDENCE = ReasonCode.DENY_CALIBRATION_INSUFFICIENT


def _hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _fields(value: Any, required: set[str], optional: set[str], path: tuple) -> Mapping[str, Any]:
    data = expect_mapping(value, path, _INVALID)
    for key in sorted(required):
        if key not in data:
            fail(f"increment_{key}_missing", _INVALID, f"provide the required {key}", (*path, key))
    if set(data) - required - optional:
        fail("increment_field_unknown", _INVALID, "remove unsupported increment fields", path)
    return data


def _matrix(value: Any, path: tuple) -> PropagationMatrix:
    if not isinstance(value, PropagationMatrix):
        fail("increment_matrix_invalid", _INVALID, "provide a PropagationMatrix", path)
    matrix = PropagationMatrix(value.values, value.node_order, value.graph_hash)
    if not matrix.node_order:
        fail("increment_node_order_missing", _INVALID, "declare matrix node ordering", (*path, "node_order"))
    if matrix.graph_hash is None:
        fail("increment_graph_hash_missing", ReasonCode.DENY_GRAPH_HASH_MISMATCH,
             "bind the matrix to a graph", (*path, "graph_hash"))
    return matrix


def _matrix_wire(matrix: PropagationMatrix) -> dict[str, Any]:
    return {"values": matrix.values.tolist(), "node_order": list(matrix.node_order), "graph_hash": matrix.graph_hash}


def _matrix_identity(matrix: PropagationMatrix) -> dict[str, Any]:
    return {"binary64_hex": [[float(value).hex() for value in row] for row in matrix.values],
            "node_order": list(matrix.node_order), "graph_hash": matrix.graph_hash}


def _matrix_from_mapping(value: Any, path: tuple) -> PropagationMatrix:
    data = _fields(value, {"values", "node_order", "graph_hash"}, set(), path)
    return PropagationMatrix.from_values(data["values"], node_order=data["node_order"], graph_hash=data["graph_hash"], path=path)


def _timestamp(value: Any, path: tuple) -> datetime:
    text = expect_datetime_string(value, path, ReasonCode.DENY_CONTEXT_STALE)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        fail("increment_time_timezone_missing", ReasonCode.DENY_CONTEXT_STALE,
             "use a timezone-aware timestamp", path)
    return parsed


@dataclass(frozen=True)
class IncrementSnapshot:
    upper: PropagationMatrix
    lower: PropagationMatrix | None = None
    snapshot_hash: str = field(init=False)

    def __post_init__(self) -> None:
        upper = _matrix(self.upper, ("increment_snapshot", "upper"))
        lower = None if self.lower is None else _matrix(self.lower, ("increment_snapshot", "lower"))
        if lower is not None:
            if lower.values.shape != upper.values.shape:
                fail("increment_interval_shape_mismatch", _INVALID,
                     "align lower and upper matrix dimensions", ("increment_snapshot",))
            if lower.node_order != upper.node_order:
                fail("increment_interval_node_order_mismatch", _INVALID,
                     "align lower and upper node ordering", ("increment_snapshot",))
            if lower.graph_hash != upper.graph_hash:
                fail("increment_interval_graph_mismatch", ReasonCode.DENY_GRAPH_HASH_MISMATCH,
                     "bind both interval endpoints to the same graph", ("increment_snapshot",))
            if not np.all(lower.values <= upper.values):
                fail("increment_interval_order_invalid", _INVALID,
                     "provide an entrywise lower matrix no greater than the upper matrix", ("increment_snapshot",))
        object.__setattr__(self, "upper", upper)
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "snapshot_hash", _hash({
            "domain": "arcana.increment.snapshot.v1", "upper": _matrix_identity(upper),
            "lower": None if lower is None else _matrix_identity(lower),
        }))

    def validated_snapshot(self) -> IncrementSnapshot:
        snapshot = replace(self)
        supplied = expect_sha256(self.snapshot_hash, ("increment_snapshot", "snapshot_hash"), _INVALID)
        if not hmac.compare_digest(snapshot.snapshot_hash, supplied):
            fail("increment_snapshot_hash_mismatch", _INVALID,
                 "rebuild the snapshot after changing its matrix content", ("increment_snapshot", "snapshot_hash"))
        return snapshot

    def _wire(self) -> dict[str, Any]:
        data = {"upper": _matrix_wire(self.upper), "snapshot_hash": self.snapshot_hash}
        if self.lower is not None:
            data["lower"] = _matrix_wire(self.lower)
        return data

    def to_mapping(self) -> dict[str, Any]:
        return self.validated_snapshot()._wire()

    @classmethod
    def from_mapping(cls, value: Any, path: tuple = ("increment_snapshot",)) -> IncrementSnapshot:
        data = _fields(value, {"upper", "snapshot_hash"}, {"lower"}, path)
        snapshot = cls(_matrix_from_mapping(data["upper"], (*path, "upper")),
                       _matrix_from_mapping(data["lower"], (*path, "lower")) if "lower" in data else None)
        supplied = expect_sha256(data["snapshot_hash"], (*path, "snapshot_hash"), _INVALID)
        if not hmac.compare_digest(snapshot.snapshot_hash, supplied):
            fail("increment_snapshot_hash_mismatch", _INVALID,
                 "snapshot hash does not match represented matrix content", (*path, "snapshot_hash"))
        return snapshot


@dataclass(frozen=True)
class IncrementContract:
    scope: IncrementScope
    risk_model_version: str
    calibration_profile_id: str
    decision_horizon: DecisionHorizon
    before: IncrementSnapshot
    after: IncrementSnapshot
    evidence_hash: str
    evidence_source_id: str
    evidence_scope: str
    valid_from: str
    expires_at: str
    schema_version: str = INCREMENT_CONTRACT_VERSION
    binding_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != INCREMENT_CONTRACT_VERSION:
            fail("increment_version_unsupported", _INVALID,
                 "use the supported versioned increment contract", ("increment", "schema_version"))
        scope = expect_enum(IncrementScope, self.scope, ("increment", "scope"), _INVALID)
        object.__setattr__(self, "scope", scope)
        expect_risk_model_version(self.risk_model_version, ("increment", "risk_model_version"))
        expect_calibration_profile_id(self.calibration_profile_id, ("increment", "calibration_profile_id"))
        if not isinstance(self.decision_horizon, DecisionHorizon):
            fail("increment_horizon_invalid", ReasonCode.DENY_DECISION_HORIZON_MISMATCH,
                 "provide a DecisionHorizon", ("increment", "decision_horizon"))
        horizon = DecisionHorizon.from_mapping(vars(self.decision_horizon), ("increment", "decision_horizon"))
        object.__setattr__(self, "decision_horizon", horizon)
        for name in ("before", "after"):
            snapshot = getattr(self, name)
            if not isinstance(snapshot, IncrementSnapshot):
                fail(f"increment_{name}_snapshot_invalid", _INVALID,
                     f"provide an IncrementSnapshot for {name}", ("increment", name))
            object.__setattr__(self, name, snapshot.validated_snapshot())
        if self.before.upper.values.shape != self.after.upper.values.shape:
            fail("increment_transition_shape_mismatch", _INVALID,
                 "use equal dimensions for before and after matrices", ("increment",))
        if self.before.upper.node_order != self.after.upper.node_order:
            fail("increment_transition_node_order_mismatch", _INVALID,
                 "use the same node ordering for before and after matrices", ("increment",))
        expect_sha256(self.evidence_hash, ("increment", "evidence_hash"), _EVIDENCE)
        source = expect_non_empty_string(self.evidence_source_id, ("increment", "evidence_source_id"), _EVIDENCE)
        if not source.strip():
            fail("increment_evidence_source_blank", _EVIDENCE,
                 "identify the evidence source", ("increment", "evidence_source_id"))
        if scope is IncrementScope.UPPER_MODEL:
            expected_evidence_scope = "represented_snapshot_pair"
        elif scope is IncrementScope.CALIBRATION_ENVELOPE:
            expected_evidence_scope = "joint_before_after_envelope"
        else:
            fail("increment_scope_unsupported", _INVALID, "select a supported increment scope", ("increment", "scope"))
        if self.evidence_scope != expected_evidence_scope:
            fail("increment_evidence_scope_mismatch", _EVIDENCE,
                 f"declare evidence covering {expected_evidence_scope}; labels do not prove coverage", ("increment", "evidence_scope"))
        if _timestamp(self.valid_from, ("increment", "valid_from")) >= _timestamp(self.expires_at, ("increment", "expires_at")):
            fail("increment_evidence_window_invalid", ReasonCode.DENY_CONTEXT_STALE,
                 "expires_at must be after valid_from", ("increment", "expires_at"))
        object.__setattr__(self, "binding_hash", _hash(self._identity()))

    def _identity(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "scope": self.scope.value,
                "risk_model_version": self.risk_model_version, "calibration_profile_id": self.calibration_profile_id,
                "decision_horizon": vars(self.decision_horizon),
                "before_snapshot_hash": self.before.snapshot_hash, "after_snapshot_hash": self.after.snapshot_hash,
                "evidence_hash": self.evidence_hash, "evidence_source_id": self.evidence_source_id,
                "evidence_scope": self.evidence_scope, "valid_from": self.valid_from, "expires_at": self.expires_at}

    def validated_snapshot(self) -> IncrementContract:
        contract = replace(self)
        supplied = expect_sha256(self.binding_hash, ("increment", "binding_hash"), _INVALID)
        if not hmac.compare_digest(contract.binding_hash, supplied):
            fail("increment_binding_hash_mismatch", _INVALID,
                 "rebuild the increment binding after changing its inputs", ("increment", "binding_hash"))
        return contract

    def to_mapping(self) -> dict[str, Any]:
        contract = self.validated_snapshot()
        data = contract._identity()
        del data["before_snapshot_hash"], data["after_snapshot_hash"]
        return {**data, "before": contract.before._wire(), "after": contract.after._wire(), "binding_hash": contract.binding_hash}

    @classmethod
    def from_mapping(cls, value: Any, path: tuple = ("increment",)) -> IncrementContract:
        keys = {"schema_version", "scope", "risk_model_version", "calibration_profile_id", "decision_horizon",
                "before", "after", "evidence_hash", "evidence_source_id", "evidence_scope", "valid_from", "expires_at", "binding_hash"}
        data = _fields(value, keys, set(), path)
        contract = cls(
            scope=data["scope"], risk_model_version=data["risk_model_version"], calibration_profile_id=data["calibration_profile_id"],
            decision_horizon=DecisionHorizon.from_mapping(
                _fields(data["decision_horizon"], {"id", "duration_seconds", "context"}, set(), (*path, "decision_horizon")),
                (*path, "decision_horizon")),
            before=IncrementSnapshot.from_mapping(data["before"], (*path, "before")),
            after=IncrementSnapshot.from_mapping(data["after"], (*path, "after")),
            evidence_hash=data["evidence_hash"], evidence_source_id=data["evidence_source_id"], evidence_scope=data["evidence_scope"],
            valid_from=data["valid_from"], expires_at=data["expires_at"], schema_version=data["schema_version"],
        )
        supplied = expect_sha256(data["binding_hash"], (*path, "binding_hash"), _INVALID)
        if not hmac.compare_digest(contract.binding_hash, supplied):
            fail("increment_binding_hash_mismatch", _INVALID,
                 "binding hash does not match the complete increment contract", (*path, "binding_hash"))
        return contract


def required_increment_scope(budget: AutonomyBudget) -> IncrementScope | None:
    if not isinstance(budget, AutonomyBudget):
        fail("autonomy_budget_invalid", ReasonCode.DENY_BUDGET_EXHAUSTED,
             "autonomy_budget must be AutonomyBudget", ("autonomy_budget",))
    if budget.increment_scope is None:
        return None
    scope = expect_enum(IncrementScope, budget.increment_scope, ("autonomy_budget", "increment_scope"), ReasonCode.DENY_BUDGET_EXHAUSTED)
    if budget.max_delta_rho_upper is None:
        fail("increment_budget_limit_missing", ReasonCode.DENY_BUDGET_EXHAUSTED,
             "a scoped increment budget requires max_delta_rho_upper", ("autonomy_budget", "max_delta_rho_upper"))
    return scope


def validate_increment_binding(
    contract: IncrementContract | None, *, required_scope: IncrementScope | None,
    risk_model_version: str, calibration_profile_id: str, decision_horizon: DecisionHorizon,
    decision_time: datetime, after_upper: PropagationMatrix, before_upper: PropagationMatrix | None = None,
    after_lower: PropagationMatrix | None = None, evidence_hash: str | None = None,
    evidence_source_id: str | None = None,
) -> IncrementContract | None:
    if required_scope is None:
        if contract is not None:
            fail("increment_budget_scope_missing", ReasonCode.DENY_BUDGET_EXHAUSTED,
                 "declare the required increment scope in autonomy_budget", ("autonomy_budget", "increment_scope"))
        return None
    if contract is None:
        fail("increment_contract_missing", _INVALID,
             "provide the typed before/after increment contract required by this budget", ("increment",))
    if not isinstance(contract, IncrementContract):
        fail("increment_contract_invalid", _INVALID,
             "parse or construct an IncrementContract before evaluation", ("increment",))
    checked = contract.validated_snapshot()
    checks = (
        (checked.scope, required_scope, "scope", ReasonCode.DENY_BUDGET_EXHAUSTED),
        (checked.risk_model_version, risk_model_version, "risk_model", ReasonCode.DENY_RISK_MODEL_UNSUPPORTED),
        (checked.calibration_profile_id, calibration_profile_id, "calibration_profile", _EVIDENCE),
        (checked.decision_horizon, decision_horizon, "horizon", ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
    )
    for actual, expected, name, reason in checks:
        if actual != expected:
            fail(f"increment_{name}_mismatch", reason,
                 f"increment {name} must match the current decision requirement", ("increment", name))
    if decision_time.tzinfo is None:
        fail("increment_decision_time_timezone_missing", ReasonCode.DENY_CONTEXT_STALE,
             "provide a timezone-aware decision time", ("decision_time",))
    if decision_time < _timestamp(checked.valid_from, ("increment", "valid_from")):
        fail("increment_evidence_not_yet_valid", ReasonCode.DENY_CONTEXT_STALE,
             "do not use evidence before its validity window", ("increment", "valid_from"))
    if decision_time >= _timestamp(checked.expires_at, ("increment", "expires_at")):
        fail("increment_evidence_expired", ReasonCode.DENY_CONTEXT_STALE,
             "refresh the bound evidence before evaluating this increment", ("increment", "expires_at"))
    for name, actual, expected in (("evidence_hash", checked.evidence_hash, evidence_hash),
                                   ("evidence_source_id", checked.evidence_source_id, evidence_source_id)):
        if expected is not None and actual != expected:
            fail(f"increment_{name}_mismatch", _EVIDENCE,
                 f"bind the increment to the current {name}", ("increment", name))
    pairs = [("after_upper", checked.after.upper, after_upper)]
    if before_upper is not None:
        pairs.append(("before_upper", checked.before.upper, before_upper))
    if after_lower is not None and checked.after.lower is not None:
        pairs.append(("after_lower", checked.after.lower, after_lower))
    for name, actual, expected in pairs:
        expected = _matrix(expected, ("increment", name))
        if actual.graph_hash != expected.graph_hash:
            fail(f"increment_{name}_graph_mismatch", ReasonCode.DENY_GRAPH_HASH_MISMATCH,
                 f"bind the increment {name} to the current graph identity", ("increment", name, "graph_hash"))
        if actual.values.shape != expected.values.shape:
            fail(f"increment_{name}_shape_mismatch", _INVALID,
                 f"match the current {name} matrix dimensions", ("increment", name))
        if actual.node_order != expected.node_order:
            fail(f"increment_{name}_node_order_mismatch", _INVALID,
                 f"match the current {name} node ordering", ("increment", name, "node_order"))
        if _matrix_identity(actual) != _matrix_identity(expected):
            fail(f"increment_{name}_mismatch", _INVALID,
                 f"bind the increment to the actual evaluator {name} matrix", ("increment", name))
    return checked


def _baseline(contract: IncrementContract) -> tuple[float, str]:
    if contract.scope is IncrementScope.UPPER_MODEL:
        return spectral_bounds(contract.before.upper).lower, "upper_model_numerical_lower"
    if contract.scope is IncrementScope.CALIBRATION_ENVELOPE:
        if contract.before.lower is None:
            return 0.0, "nonnegative_zero_fallback"
        return spectral_bounds(contract.before.lower).lower, "calibration_matrix_numerical_lower"
    fail("increment_scope_unsupported", _INVALID, "select a supported increment scope", ("increment", "scope"))


def _metrics_from_verified_bound(contract: IncrementContract, after_upper_bound: float) -> dict[str, Any]:
    # Only evaluator-computed spectral/Collatz bounds may enter this internal path.
    lower, source = _baseline(contract)
    return {"increment_contract_version": INCREMENT_CONTRACT_VERSION,
            "increment_scope": contract.scope.value, "increment_binding_hash": contract.binding_hash,
            "increment_before_snapshot_hash": contract.before.snapshot_hash,
            "increment_after_snapshot_hash": contract.after.snapshot_hash,
            "increment_baseline_source": source, "increment_before_lower": lower,
            "increment_after_upper": after_upper_bound,
            "increment_evidence_assurance": "declared_premises_not_empirically_verified",
            "delta_rho_upper": nonnegative_difference_upper(after_upper_bound, lower)}


def evaluate_increment(contract: IncrementContract, *, decision_time: str) -> dict[str, Any]:
    if not isinstance(contract, IncrementContract):
        fail("increment_contract_invalid", _INVALID, "provide an IncrementContract", ("increment",))
    checked = contract.validated_snapshot()
    checked = validate_increment_binding(
        checked, required_scope=checked.scope, risk_model_version=checked.risk_model_version,
        calibration_profile_id=checked.calibration_profile_id, decision_horizon=checked.decision_horizon,
        decision_time=_timestamp(decision_time, ("decision_time",)), after_upper=checked.after.upper,
    )
    assert checked is not None
    return _metrics_from_verified_bound(checked, spectral_bounds(checked.after.upper).upper)
