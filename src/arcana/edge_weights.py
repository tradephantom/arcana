"""Edge weight model arcana.edge_weight.v1: one versioned formula for propagation entries.

    w_e(H) = activation * p_unsafe * exposure * capability * scope * pass_1 * ... * pass_k

Every factor is an interval ``lower <= mean <= upper``. ``pass_i`` is the probability that an
unsafe transition reaching control ``i`` passes it; it replaces ``(1 - detectability)`` and
``(1 - gate_effectiveness)``, so a gate that acts only on detected transitions is one control
with one jointly measured pass-through, not two discounts. Reversibility is not a factor: it
changes the consequence, which belongs to the loss model ``L``, unless it stops propagation
before the target activates, in which case it is a control with its own evidence.

The risk factors and the controls each compose by their own declared semantics:

- ``conditional_chain``: each factor is conditional on all preceding ones in its group, so the
  product is an identity and the endpoints multiply;
- ``unknown_dependence``: only the Frechet bounds hold: the upper endpoint is the minimum of the
  upper endpoints, the lower endpoint is ``max(0, sum(lowers) - (k - 1))``.

The control group multiplies the risk group because each pass-through is defined on unsafe
transitions: P(risk and pass) = P(risk) * P(pass | risk). Endpoints are computed exactly and rounded outward once per matrix entry. The mean is the
product of means under both semantics; it supports analysis, never admission.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import prod
from typing import Any

import numpy as np

from arcana._numerics import outward_float
from arcana._validation import expect_enum, expect_mapping, expect_non_empty_string, expect_number_min, fail, require_value
from arcana.errors import ArcanaValidationError, FactorSemantics, ReasonCode
from arcana.matrices import MatrixBundle
from arcana.model import DecisionHorizon, GraphState

EDGE_WEIGHT_MODEL_VERSION = "arcana.edge_weight.v1"
RISK_FACTORS = ("p_unsafe", "exposure", "capability", "scope")

_INVALID = ReasonCode.DENY_MODEL_INPUT_INVALID
_ENDPOINTS = ("lower", "mean", "upper")


@dataclass(frozen=True)
class FactorInterval:
    lower: float
    mean: float
    upper: float

    @classmethod
    def point(cls, value: float) -> "FactorInterval":
        return cls(value, value, value)

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...]) -> "FactorInterval":
        data = expect_mapping(value, path, _INVALID)
        interval = cls(*(require_value(data, name, path, _INVALID) for name in _ENDPOINTS))
        _interval(interval, path, probability=False)
        return interval


# Unknown means risky: no lower support, no control credit.
UNKNOWN_PROBABILITY = FactorInterval(0.0, 1.0, 1.0)


@dataclass(frozen=True)
class EdgeControl:
    control_id: str
    pass_through: FactorInterval

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...]) -> "EdgeControl":
        data = expect_mapping(value, path, _INVALID)
        return cls(
            control_id=expect_non_empty_string(require_value(data, "control_id", path, _INVALID), (*path, "control_id"), _INVALID),
            pass_through=FactorInterval.from_mapping(require_value(data, "pass_through", path, _INVALID), (*path, "pass_through")),
        )


@dataclass(frozen=True)
class EdgeFactors:
    source: str
    target: str
    edge_type: str
    decision_horizon: DecisionHorizon
    risk_semantics: FactorSemantics
    control_semantics: FactorSemantics
    activation: FactorInterval
    p_unsafe: FactorInterval
    exposure: FactorInterval
    capability: FactorInterval
    scope: FactorInterval
    controls: tuple[EdgeControl, ...] = ()

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ("edge_factors",)) -> "EdgeFactors":
        data = expect_mapping(value, path, _INVALID)
        raw_controls = data.get("controls", [])
        if not isinstance(raw_controls, list):
            fail("edge_controls_invalid", _INVALID, "controls must be an array", (*path, "controls"))
        factors = cls(
            **{name: expect_non_empty_string(require_value(data, name, path, _INVALID), (*path, name), _INVALID)
               for name in ("source", "target", "edge_type")},
            decision_horizon=DecisionHorizon.from_mapping(
                require_value(data, "decision_horizon", path, ReasonCode.DENY_DECISION_HORIZON_MISMATCH), (*path, "decision_horizon")),
            **{name: expect_enum(FactorSemantics, require_value(data, name, path, _INVALID), (*path, name), _INVALID)
               for name in ("risk_semantics", "control_semantics")},
            **{name: FactorInterval.from_mapping(require_value(data, name, path, _INVALID), (*path, name))
               for name in ("activation", *RISK_FACTORS)},
            controls=tuple(EdgeControl.from_mapping(item, (*path, "controls", index)) for index, item in enumerate(raw_controls)),
        )
        exact_edge_weight(factors, path)
        return factors


@dataclass(frozen=True)
class EdgeWeight:
    lower: float
    mean: float
    upper: float


def edge_weight(factors: EdgeFactors, path: tuple[str | int, ...] = ("edge_factors",)) -> EdgeWeight:
    """Outward-rounded weight interval of one edge."""
    return _rounded(exact_edge_weight(factors, path), path)


def exact_edge_weight(factors: EdgeFactors, path: tuple[str | int, ...] = ("edge_factors",)) -> tuple[Fraction, Fraction, Fraction]:
    """Exact (lower, mean, upper) weight of one edge before rounding."""
    if not isinstance(factors, EdgeFactors):
        fail("edge_factors_invalid", _INVALID, "edge factors must be EdgeFactors", path)
    risk_semantics, control_semantics = (expect_enum(FactorSemantics, getattr(factors, name), (*path, name), _INVALID)
                                         for name in ("risk_semantics", "control_semantics"))
    activation = _interval(factors.activation, (*path, "activation"), probability=False)
    risks = [_interval(getattr(factors, name), (*path, name), probability=True) for name in RISK_FACTORS]
    if not isinstance(factors.controls, (tuple, list)):
        fail("edge_controls_invalid", _INVALID, "controls must be a sequence of EdgeControl", (*path, "controls"))
    control_ids, controls = [], []
    for index, control in enumerate(factors.controls):
        control_path = (*path, "controls", index)
        if not isinstance(control, EdgeControl):
            fail("edge_control_invalid", _INVALID, "control must be EdgeControl", control_path)
        control_ids.append(expect_non_empty_string(control.control_id, (*control_path, "control_id"), _INVALID))
        controls.append(_interval(control.pass_through, (*control_path, "pass_through"), probability=True))
    if len(set(control_ids)) != len(control_ids):
        fail("edge_control_duplicate", _INVALID, "control_id values must be unique per edge", (*path, "controls"))
    risk, passed = _compose(risks, risk_semantics), _compose(controls, control_semantics)
    lower, mean, upper = (a * r * c for a, r, c in zip(activation, risk, passed, strict=True))
    return lower, mean, upper


def _compose(factors: list[tuple[Fraction, Fraction, Fraction]], semantics: FactorSemantics) -> tuple[Fraction, Fraction, Fraction]:
    """(lower, mean, upper) of the joint event; an empty group passes everything."""
    if not factors:
        return Fraction(1), Fraction(1), Fraction(1)
    lowers, means, uppers = zip(*factors)
    if semantics is FactorSemantics.CONDITIONAL_CHAIN:
        return prod(lowers), prod(means), prod(uppers)
    return max(Fraction(0), sum(lowers) - (len(lowers) - 1)), prod(means), min(uppers)


def propagation_bundle(
    graph: GraphState,
    edge_factors: Sequence[EdgeFactors],
    decision_horizon: DecisionHorizon,
) -> MatrixBundle:
    """K_lower, K_mean and K_upper with K_ij the sum of the weights of every i -> j edge.

    Every graph edge needs factors and every factor set needs a graph edge: a missing edge
    cannot default, because activation has no conservative upper bound.
    """
    if not isinstance(graph, GraphState):
        fail("graph_state_invalid", _INVALID, "graph must be GraphState", ("graph",))
    if not isinstance(decision_horizon, DecisionHorizon):
        fail("decision_horizon_invalid", ReasonCode.DENY_DECISION_HORIZON_MISMATCH, "decision_horizon must be DecisionHorizon",
             ("decision_horizon",))
    index = {node.node_id: position for position, node in enumerate(graph.nodes)}
    if len(index) != len(graph.nodes):
        fail("graph_node_id_duplicate", _INVALID, "graph node_id values must be unique", ("graph", "nodes"))
    expected = set()
    for position, edge in enumerate(graph.edges):
        if edge.source not in index or edge.target not in index:
            fail("graph_edge_endpoint_unknown", _INVALID, "edge endpoint is not present in nodes", ("graph", "edges", position))
        key = (edge.source, edge.target, edge.edge_type)
        if key in expected:
            fail("graph_edge_duplicate", _INVALID, "graph edges must be unique by source,target,edge_type", ("graph", "edges", position))
        expected.add(key)
    if not isinstance(edge_factors, (list, tuple)):
        fail("edge_factors_invalid", _INVALID, "edge_factors must be a sequence of EdgeFactors", ("edge_factors",))
    cells: dict[tuple[int, int], list[Fraction]] = {}
    seen = set()
    for position, factors in enumerate(edge_factors):
        path = ("edge_factors", position)
        weight = exact_edge_weight(factors, path)
        key = (factors.source, factors.target, factors.edge_type)
        if key in seen:
            fail("edge_factors_duplicate", _INVALID, "each graph edge takes exactly one factor set", path)
        if key not in expected:
            fail("edge_factors_unknown_edge", _INVALID, "factor set does not match a graph edge", path)
        if factors.decision_horizon != decision_horizon:
            fail("edge_factors_horizon_mismatch", ReasonCode.DENY_DECISION_HORIZON_MISMATCH,
                 "edge factors are declared for a different decision horizon", (*path, "decision_horizon"))
        seen.add(key)
        cell = cells.setdefault((index[factors.source], index[factors.target]), [Fraction(0)] * 3)
        for endpoint, value in enumerate(weight):
            cell[endpoint] += value
    if expected - seen:
        fail("edge_factors_missing", ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
             f"{len(expected - seen)} graph edge(s) have no calibrated factors", ("edge_factors",))
    size = len(index)
    matrices = [np.zeros((size, size)) for _ in _ENDPOINTS]
    for (row, column), cell in cells.items():
        rounded = _rounded(tuple(cell), ("K", row, column))
        for matrix, value in zip(matrices, (rounded.lower, rounded.mean, rounded.upper), strict=True):
            matrix[row, column] = value
    return MatrixBundle.from_values(*matrices, node_order=tuple(index), graph_hash=graph.graph_hash)


def _interval(interval: FactorInterval, path: tuple[str | int, ...], *, probability: bool) -> tuple[Fraction, Fraction, Fraction]:
    if not isinstance(interval, FactorInterval):
        fail("edge_factor_invalid", _INVALID, "factor must be FactorInterval", path)
    lower, mean, upper = (expect_number_min(getattr(interval, name), 0, (*path, name), _INVALID) for name in _ENDPOINTS)
    if not lower <= mean <= upper:
        fail("edge_factor_interval_order_invalid", _INVALID, "expected lower <= mean <= upper", path)
    if probability and upper > 1:
        fail("edge_factor_probability_out_of_range", _INVALID, "probability factors must lie in [0, 1]", (*path, "upper"))
    return Fraction(lower), Fraction(mean), Fraction(upper)


def _rounded(exact: tuple[Fraction, Fraction, Fraction], path: tuple[str | int, ...]) -> EdgeWeight:
    lower, mean, upper = exact
    try:
        lower_float, upper_float = outward_float(lower, upper=False), outward_float(upper, upper=True)
    except ArcanaValidationError:
        fail("edge_weight_unrepresentable", _INVALID, "edge weight exceeds binary64 range; rescale activation", path)
    return EdgeWeight(lower_float, min(max(float(mean), lower_float), upper_float), upper_float)


__all__ = [
    "EDGE_WEIGHT_MODEL_VERSION",
    "RISK_FACTORS",
    "UNKNOWN_PROBABILITY",
    "EdgeControl",
    "EdgeFactors",
    "EdgeWeight",
    "FactorInterval",
    "edge_weight",
    "exact_edge_weight",
    "propagation_bundle",
]
