"""Conditional, finite-generation propagation under a common nonnegative envelope."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from fractions import Fraction
import hashlib
import hmac
import json
from typing import Any

import numpy as np

from arcana._numerics import NUMERICAL_CONTRACT_VERSION, outward_float
from arcana._validation import (
    expect_calibration_profile_id, expect_datetime_string, expect_enum, expect_int_min,
    expect_mapping, expect_non_empty_string, expect_number_min, expect_number_range,
    expect_risk_model_version, expect_sha256, fail,
)
from arcana.errors import ArcanaValidationError, ReasonCode, TemporalMode
from arcana.matrices import PropagationMatrix, TolerancePolicy, spectral_bounds
from arcana.model import DecisionHorizon, MAX_TEMPORAL_GENERATIONS, TemporalPolicy


TEMPORAL_CONTRACT_VERSION = "arcana.temporal.v1"
MAX_TEMPORAL_NODES = 64
MAX_TEMPORAL_OPERATORS = 64
_INVALID = ReasonCode.DENY_MODEL_INPUT_INVALID
_EVIDENCE = ReasonCode.DENY_CALIBRATION_INSUFFICIENT


def _hash(data: Mapping[str, Any]) -> str:
    wire = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return "sha256:" + hashlib.sha256(wire.encode("ascii")).hexdigest()


def _fields(value: Any, keys: set[str], path: tuple) -> Mapping[str, Any]:
    data = expect_mapping(value, path, _INVALID)
    for key in sorted(keys):
        if key not in data:
            fail(f"temporal_{key}_missing", _INVALID, f"provide temporal {key}", (*path, key))
    if set(data) - keys:
        fail("temporal_field_unknown", _INVALID, "remove unsupported temporal fields", path)
    return data


def _time(value: Any, path: tuple) -> datetime:
    text = expect_datetime_string(value, path, ReasonCode.DENY_CONTEXT_STALE)
    instant = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        fail("temporal_time_timezone_missing", ReasonCode.DENY_CONTEXT_STALE,
             "provide an explicit timezone offset", path)
    return instant


def _matrix(value: Any, path: tuple) -> PropagationMatrix:
    if not isinstance(value, PropagationMatrix):
        fail("temporal_matrix_invalid", _INVALID, "provide a PropagationMatrix", path)
    matrix = PropagationMatrix(value.values, value.node_order, value.graph_hash)
    if matrix.size > MAX_TEMPORAL_NODES:
        fail("temporal_node_limit_exceeded", _INVALID, "use a reviewed implementation for more than 64 nodes", path)
    if not matrix.node_order:
        fail("temporal_node_order_missing", _INVALID, "declare matrix node ordering", path)
    if matrix.graph_hash is None:
        fail("temporal_graph_hash_missing", ReasonCode.DENY_GRAPH_HASH_MISMATCH, "bind the matrix to a graph", path)
    return matrix


def _matrix_wire(matrix: PropagationMatrix) -> dict[str, Any]:
    return {"values": matrix.values.tolist(), "node_order": list(matrix.node_order), "graph_hash": matrix.graph_hash}


def _matrix_identity(matrix: PropagationMatrix) -> dict[str, Any]:
    return {"binary64_hex": [[float(x).hex() for x in row] for row in matrix.values],
            "node_order": list(matrix.node_order), "graph_hash": matrix.graph_hash}


def _matrix_from_mapping(value: Any, path: tuple) -> PropagationMatrix:
    data = _fields(value, {"values", "node_order", "graph_hash"}, path)
    values = data["values"]
    if isinstance(values, Sequence) and len(values) > MAX_TEMPORAL_NODES:
        fail("temporal_node_limit_exceeded", _INVALID, "use a reviewed implementation for more than 64 nodes", path)
    return PropagationMatrix.from_values(values, node_order=data["node_order"], graph_hash=data["graph_hash"], path=path)


def _policy(policy: Any) -> TemporalPolicy:
    if policy is None:
        fail("temporal_policy_missing", ReasonCode.DENY_BUDGET_EXHAUSTED,
             "declare a TemporalPolicy with mode, generation count and both activation limits", ("temporal_policy",))
    if not isinstance(policy, TemporalPolicy):
        fail("temporal_policy_invalid", ReasonCode.DENY_BUDGET_EXHAUSTED,
             "parse or construct a TemporalPolicy", ("temporal_policy",))
    return replace(policy)


def temporal_policy_hash(policy: TemporalPolicy) -> str:
    checked = _policy(policy)
    return _hash({"domain": "arcana.temporal.policy.v1", "mode": checked.mode.value,
                  "generations": checked.generations,
                  "max_peak_activations_upper_hex": checked.max_peak_activations_upper.hex(),
                  "max_cumulative_activations_upper_hex": checked.max_cumulative_activations_upper.hex()})


@dataclass(frozen=True)
class TemporalContract:
    mode: TemporalMode
    risk_model_version: str
    calibration_profile_id: str
    decision_horizon: DecisionHorizon
    generations: int
    operators: tuple[PropagationMatrix, ...]
    envelope_upper: PropagationMatrix
    initial_upper: tuple[float, ...]
    operator_semantics: str
    state_units: str
    exogenous_input: str
    evidence_hash: str
    evidence_source_id: str
    evidence_scope: str
    valid_from: str
    expires_at: str
    schema_version: str = TEMPORAL_CONTRACT_VERSION
    binding_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != TEMPORAL_CONTRACT_VERSION:
            fail("temporal_version_unsupported", _INVALID, "use arcana.temporal.v1", ("temporal", "schema_version"))
        mode = expect_enum(TemporalMode, self.mode, ("temporal", "mode"), _INVALID)
        object.__setattr__(self, "mode", mode)
        expect_risk_model_version(self.risk_model_version, ("temporal", "risk_model_version"))
        expect_calibration_profile_id(self.calibration_profile_id, ("temporal", "calibration_profile_id"))
        if not isinstance(self.decision_horizon, DecisionHorizon):
            fail("temporal_horizon_invalid", ReasonCode.DENY_DECISION_HORIZON_MISMATCH,
                 "provide a DecisionHorizon", ("temporal", "decision_horizon"))
        object.__setattr__(self, "decision_horizon", DecisionHorizon.from_mapping(vars(self.decision_horizon)))
        expect_int_min(self.generations, 1, ("temporal", "generations"), _INVALID)
        if self.generations > MAX_TEMPORAL_GENERATIONS:
            fail("temporal_generation_limit_exceeded", _INVALID, "use a reviewed implementation beyond 256 generations", ("temporal", "generations"))
        for name, expected in (("operator_semantics", "per_generation_expected_offspring"),
                               ("state_units", "expected_unsafe_activations"),
                               ("exogenous_input", "none_after_initial")):
            if getattr(self, name) != expected:
                fail(f"temporal_{name}_unsupported", _INVALID,
                     f"this model requires {expected}; do not relabel incompatible inputs", ("temporal", name))
        envelope = _matrix(self.envelope_upper, ("temporal", "envelope_upper"))
        if not isinstance(self.operators, tuple):
            fail("temporal_operators_invalid", _INVALID, "provide a tuple of declared operators", ("temporal", "operators"))
        if not self.operators:
            fail("temporal_operators_empty", _INVALID, "declare at least one covered operator", ("temporal", "operators"))
        if len(self.operators) > MAX_TEMPORAL_OPERATORS:
            fail("temporal_operator_limit_exceeded", _INVALID, "use a reviewed implementation beyond 64 operators", ("temporal", "operators"))
        operators = tuple(_matrix(value, ("temporal", "operators", index)) for index, value in enumerate(self.operators))
        seen = set()
        for index, operator in enumerate(operators):
            if operator.values.shape != envelope.values.shape:
                fail("temporal_operator_shape_mismatch", _INVALID, "align family and envelope dimensions", ("temporal", "operators", index))
            if operator.node_order != envelope.node_order:
                fail("temporal_operator_node_order_mismatch", _INVALID, "align family and envelope coordinates", ("temporal", "operators", index))
            if np.any(operator.values > envelope.values):
                fail("temporal_operator_outside_envelope", _INVALID,
                     "supply an envelope covering every declared operator entry", ("temporal", "operators", index))
            identity = _hash(_matrix_identity(operator))
            if identity in seen:
                fail("temporal_operator_duplicate", _INVALID, "declare each operator identity only once", ("temporal", "operators", index))
            seen.add(identity)
        if mode is TemporalMode.FIXED_OPERATOR:
            if len(operators) != 1:
                fail("temporal_fixed_operator_count_invalid", _INVALID, "fixed mode requires exactly one operator", ("temporal", "operators"))
            if _matrix_identity(operators[0]) != _matrix_identity(envelope):
                fail("temporal_fixed_envelope_mismatch", _INVALID, "fixed mode envelope must equal its bound operator", ("temporal", "envelope_upper"))
        elif mode is not TemporalMode.COMMON_ENVELOPE:
            fail("temporal_mode_unsupported", _INVALID, "select a supported temporal mode", ("temporal", "mode"))
        if not isinstance(self.initial_upper, Sequence) or isinstance(self.initial_upper, (str, bytes)):
            fail("temporal_initial_state_invalid", _INVALID, "provide a nonnegative initial vector in node order", ("temporal", "initial_upper"))
        if len(self.initial_upper) != envelope.size:
            fail("temporal_initial_state_dimension_mismatch", _INVALID, "initial vector length must match node count", ("temporal", "initial_upper"))
        initial = tuple(expect_number_min(x, 0, ("temporal", "initial_upper", i), _INVALID) for i, x in enumerate(self.initial_upper))
        object.__setattr__(self, "operators", operators)
        object.__setattr__(self, "envelope_upper", envelope)
        object.__setattr__(self, "initial_upper", initial)
        expect_sha256(self.evidence_hash, ("temporal", "evidence_hash"), _EVIDENCE)
        source = expect_non_empty_string(self.evidence_source_id, ("temporal", "evidence_source_id"), _EVIDENCE)
        if not source.strip():
            fail("temporal_evidence_source_blank", _EVIDENCE, "identify the generation evidence source", ("temporal", "evidence_source_id"))
        if self.evidence_scope != "joint_generation_envelope":
            fail("temporal_evidence_scope_mismatch", _EVIDENCE,
                 "declare joint generation-envelope evidence; marginal snapshots do not establish it", ("temporal", "evidence_scope"))
        if _time(self.valid_from, ("temporal", "valid_from")) >= _time(self.expires_at, ("temporal", "expires_at")):
            fail("temporal_evidence_window_invalid", ReasonCode.DENY_CONTEXT_STALE,
                 "expires_at must be later than valid_from", ("temporal", "expires_at"))
        object.__setattr__(self, "binding_hash", _hash(self._identity()))

    def _identity(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "mode": self.mode.value,
                "risk_model_version": self.risk_model_version, "calibration_profile_id": self.calibration_profile_id,
                "decision_horizon": vars(self.decision_horizon), "generations": self.generations,
                "operators": [_matrix_identity(value) for value in self.operators],
                "envelope_upper": _matrix_identity(self.envelope_upper),
                "initial_upper": [x.hex() for x in self.initial_upper],
                "operator_semantics": self.operator_semantics, "state_units": self.state_units,
                "exogenous_input": self.exogenous_input, "evidence_hash": self.evidence_hash,
                "evidence_source_id": self.evidence_source_id, "evidence_scope": self.evidence_scope,
                "valid_from": self.valid_from, "expires_at": self.expires_at}

    def validated_snapshot(self) -> TemporalContract:
        checked = replace(self)
        supplied = expect_sha256(self.binding_hash, ("temporal", "binding_hash"), _INVALID)
        if not hmac.compare_digest(checked.binding_hash, supplied):
            fail("temporal_binding_hash_mismatch", _INVALID, "rebuild the contract after changing bound inputs", ("temporal", "binding_hash"))
        return checked

    def to_mapping(self) -> dict[str, Any]:
        checked = self.validated_snapshot()
        data = checked._identity()
        data.update(operators=[_matrix_wire(value) for value in checked.operators],
                    envelope_upper=_matrix_wire(checked.envelope_upper), initial_upper=list(checked.initial_upper),
                    binding_hash=checked.binding_hash)
        return data

    @classmethod
    def from_mapping(cls, value: Any, path: tuple = ("temporal",)) -> TemporalContract:
        keys = {"schema_version", "mode", "risk_model_version", "calibration_profile_id", "decision_horizon", "generations",
                "operators", "envelope_upper", "initial_upper", "operator_semantics", "state_units", "exogenous_input",
                "evidence_hash", "evidence_source_id", "evidence_scope", "valid_from", "expires_at", "binding_hash"}
        data = dict(_fields(value, keys, path))
        if not isinstance(data["operators"], list):
            fail("temporal_operators_invalid", _INVALID, "operators must be a JSON array", (*path, "operators"))
        if len(data["operators"]) > MAX_TEMPORAL_OPERATORS:
            fail("temporal_operator_limit_exceeded", _INVALID, "use a reviewed implementation beyond 64 operators", (*path, "operators"))
        data["operators"] = tuple(_matrix_from_mapping(x, (*path, "operators", i)) for i, x in enumerate(data["operators"]))
        data["envelope_upper"] = _matrix_from_mapping(data["envelope_upper"], (*path, "envelope_upper"))
        horizon = _fields(data["decision_horizon"], {"id", "duration_seconds", "context"}, (*path, "decision_horizon"))
        data["decision_horizon"] = DecisionHorizon.from_mapping(horizon)
        supplied = expect_sha256(data.pop("binding_hash"), (*path, "binding_hash"), _INVALID)
        contract = cls(**data)
        if not hmac.compare_digest(contract.binding_hash, supplied):
            fail("temporal_binding_hash_mismatch", _INVALID, "binding hash must match the complete temporal input", (*path, "binding_hash"))
        return contract


def validate_temporal_binding(
    contract: TemporalContract | None, policy: TemporalPolicy | None, *, risk_model_version: str,
    calibration_profile_id: str, decision_horizon: DecisionHorizon, decision_time: datetime,
    current_upper: PropagationMatrix, evidence_hash: str | None = None, evidence_source_id: str | None = None,
) -> TemporalContract | None:
    if policy is None and contract is None:
        return None
    required = _policy(policy)
    if contract is None:
        fail("temporal_contract_missing", _INVALID, "provide the temporal contract required by the budget", ("temporal",))
    if not isinstance(contract, TemporalContract):
        fail("temporal_contract_invalid", _INVALID, "parse or construct a TemporalContract", ("temporal",))
    checked = contract.validated_snapshot()
    for name, actual, expected, reason in (
        ("mode", checked.mode, required.mode, ReasonCode.DENY_BUDGET_EXHAUSTED),
        ("generations", checked.generations, required.generations, ReasonCode.DENY_BUDGET_EXHAUSTED),
        ("risk_model", checked.risk_model_version, risk_model_version, ReasonCode.DENY_RISK_MODEL_UNSUPPORTED),
        ("calibration_profile", checked.calibration_profile_id, calibration_profile_id, _EVIDENCE),
        ("horizon", checked.decision_horizon, decision_horizon, ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
    ):
        if actual != expected:
            fail(f"temporal_{name}_mismatch", reason, f"match the current temporal {name} requirement", ("temporal", name))
    if not isinstance(decision_time, datetime):
        fail("temporal_decision_time_invalid", ReasonCode.DENY_CONTEXT_STALE,
             "provide a timezone-aware datetime at the binding boundary", ("decision_time",))
    instant = _time(decision_time.isoformat(), ("decision_time",))
    if instant < _time(checked.valid_from, ("temporal", "valid_from")):
        fail("temporal_evidence_not_yet_valid", ReasonCode.DENY_CONTEXT_STALE, "wait for valid evidence or replace it", ("temporal", "valid_from"))
    expiry = _time(checked.expires_at, ("temporal", "expires_at"))
    if instant >= expiry:
        fail("temporal_evidence_expired", ReasonCode.DENY_CONTEXT_STALE, "refresh expired temporal evidence", ("temporal", "expires_at"))
    try:
        horizon_end = instant + timedelta(seconds=checked.decision_horizon.duration_seconds)
    except OverflowError:
        fail("temporal_horizon_end_unrepresentable", ReasonCode.DENY_DECISION_HORIZON_MISMATCH,
             "provide a representable decision horizon", ("temporal", "decision_horizon"))
    if horizon_end > expiry:
        fail("temporal_evidence_horizon_not_covered", ReasonCode.DENY_CONTEXT_STALE,
             "evidence validity must cover the entire decision horizon", ("temporal", "expires_at"))
    for name, actual, expected in (("evidence_hash", checked.evidence_hash, evidence_hash),
                                   ("evidence_source_id", checked.evidence_source_id, evidence_source_id)):
        if expected is not None and actual != expected:
            fail(f"temporal_{name}_mismatch", _EVIDENCE, f"bind to the current {name}", ("temporal", name))
    current = _matrix(current_upper, ("temporal", "current_upper"))
    if current.values.shape != checked.envelope_upper.values.shape:
        fail("temporal_current_shape_mismatch", _INVALID, "match current operator dimensions", ("temporal", "current_upper"))
    if current.node_order != checked.envelope_upper.node_order:
        fail("temporal_current_node_order_mismatch", _INVALID, "match current node ordering", ("temporal", "current_upper"))
    if not any(current.graph_hash == operator.graph_hash for operator in checked.operators):
        fail("temporal_current_graph_not_declared", ReasonCode.DENY_GRAPH_HASH_MISMATCH,
             "declare the current operator graph in the covered family", ("temporal", "current_upper"))
    if not any(_matrix_identity(current) == _matrix_identity(operator) for operator in checked.operators):
        fail("temporal_current_operator_not_declared", _INVALID,
             "declare the actual current matrix in the covered family", ("temporal", "current_upper"))
    return checked


@dataclass(frozen=True)
class TemporalEvaluation:
    metrics: Mapping[str, Any]
    reason_code: ReasonCode | None = None
    issue_code: str | None = None
    guidance: str = ""

    @property
    def passed(self) -> bool:
        return self.reason_code is None


def _upper(value: Fraction, code: str, path: tuple) -> float:
    try:
        return outward_float(value, upper=True)
    except ArcanaValidationError as exc:
        if exc.code == "spectral_bound_unrepresentable":
            fail(code, _INVALID, "temporal upper bound exceeds binary64 range; revise the model or deny", path)
        raise


def evaluate_temporal(contract: TemporalContract, policy: TemporalPolicy, *, decision_time: str,
                      rho_threshold: float, tolerance_policy: TolerancePolicy | None = None) -> TemporalEvaluation:
    """Check a conditional model and policy; passing does not authorize admission."""
    try:
        return _evaluate_temporal(contract, policy, decision_time, rho_threshold, tolerance_policy)
    except ArcanaValidationError as exc:
        issue = exc.primary_issue
        return TemporalEvaluation({"validation_path": issue.path_text}, issue.reason_code, issue.code, issue.message)


def _evaluate_temporal(contract, policy, decision_time, rho_threshold, tolerance_policy):
    required = _policy(policy)
    if contract is None:
        fail("temporal_contract_missing", _INVALID, "provide a TemporalContract", ("temporal",))
    if not isinstance(contract, TemporalContract):
        fail("temporal_contract_invalid", _INVALID, "provide a TemporalContract", ("temporal",))
    checked = contract.validated_snapshot()
    validate_temporal_binding(checked, required, risk_model_version=checked.risk_model_version,
                              calibration_profile_id=checked.calibration_profile_id, decision_horizon=checked.decision_horizon,
                              decision_time=_time(decision_time, ("decision_time",)), current_upper=checked.operators[0])
    threshold = expect_number_range(rho_threshold, 0, 1, ("rho_threshold",), _INVALID)
    if tolerance_policy is None:
        tolerance = TolerancePolicy()
    elif isinstance(tolerance_policy, TolerancePolicy):
        tolerance = replace(tolerance_policy)
    else:
        fail("temporal_tolerance_policy_invalid", _INVALID, "provide a TolerancePolicy", ("tolerance_policy",))
    rho = spectral_bounds(checked.envelope_upper).upper
    metrics = {"temporal_contract_version": TEMPORAL_CONTRACT_VERSION,
               "temporal_scope": checked.mode.value, "temporal_binding_hash": checked.binding_hash,
               "temporal_policy_hash": temporal_policy_hash(required), "temporal_generations": checked.generations,
               "temporal_envelope_rho_upper": rho, "temporal_envelope_threshold": threshold,
               "temporal_state_units": checked.state_units,
               "temporal_authority": "conditional_model_check_not_admission",
               "temporal_evidence_assurance": "declared_premises_not_empirically_verified",
               "numerical_contract_version": NUMERICAL_CONTRACT_VERSION}
    if not tolerance.below_threshold_with_margin(rho, threshold):
        return TemporalEvaluation(metrics, ReasonCode.DENY_RHO_UPPER_BOUND, "temporal_envelope_not_subcritical",
                                  "the common envelope must clear the threshold with margin; individual snapshots are insufficient")
    # K is source-row: transpose its exact represented entries for column states.
    rows = tuple(tuple(Fraction(float(x)) for x in column) for column in zip(*checked.envelope_upper.values, strict=True))
    states = [checked.initial_upper]
    totals = []
    cumulative = Fraction(0)
    for generation in range(checked.generations + 1):
        if generation:
            previous = tuple(Fraction(x) for x in states[-1])
            state = tuple(_upper(sum((a * x for a, x in zip(row, previous, strict=True)), Fraction(0)),
                                 "temporal_state_bound_unrepresentable", ("temporal", generation, index))
                          for index, row in enumerate(rows))
            states.append(state)
        total = sum((Fraction(x) for x in states[-1]), Fraction(0))
        totals.append(_upper(total, "temporal_total_bound_unrepresentable", ("temporal", generation)))
        cumulative += Fraction(totals[-1])
    cumulative_upper = _upper(cumulative, "temporal_cumulative_bound_unrepresentable", ("temporal", "cumulative"))
    metrics.update(temporal_generation_states_upper=states, temporal_generation_totals_upper=totals,
                   temporal_peak_activations_upper=max(totals), temporal_cumulative_activations_upper=cumulative_upper,
                   temporal_max_peak_activations_upper=required.max_peak_activations_upper,
                   temporal_max_cumulative_activations_upper=required.max_cumulative_activations_upper)
    if max(totals) > required.max_peak_activations_upper:
        return TemporalEvaluation(metrics, ReasonCode.DENY_BUDGET_EXHAUSTED, "temporal_peak_budget_exceeded",
                                  "reduce initial exposure or capability propagation to meet the peak activation limit")
    if cumulative_upper > required.max_cumulative_activations_upper:
        return TemporalEvaluation(metrics, ReasonCode.DENY_BUDGET_EXHAUSTED, "temporal_cumulative_budget_exceeded",
                                  "reduce total propagated activations or obtain a justified revised cumulative budget")
    return TemporalEvaluation(metrics)
