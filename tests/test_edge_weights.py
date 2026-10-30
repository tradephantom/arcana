"""arcana.edge_weight.v1: one interval formula for K entries (audit F7, F8)."""

from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
import random

import pytest

from admission_support import complete_admission
import test_decision_reason_codes as main_api
from arcana.decision import evaluate_decision
from arcana.edge_weights import (
    EDGE_WEIGHT_MODEL_VERSION,
    UNKNOWN_PROBABILITY,
    EdgeControl,
    EdgeFactors,
    FactorInterval,
    edge_weight,
    exact_edge_weight,
    propagation_bundle,
)
from arcana.errors import ArcanaValidationError, FactorSemantics, ReasonCode, Verdict
from arcana.model import DecisionHorizon, GraphEdge, GraphNode, GraphState, NodeClass

CORPUS = json.loads((Path(__file__).parent / "fixtures" / "edge_weight_v1.json").read_text())
HORIZON = main_api._horizon()
P = FactorInterval.point
CHAIN, MARGINAL = FactorSemantics.CONDITIONAL_CHAIN, FactorSemantics.UNKNOWN_DEPENDENCE


def _factors(source="agent", target="tool", edge_type="delegation", *, semantics=CHAIN, activation=P(1.0),
             p_unsafe=P(1.0), exposure=P(1.0), capability=P(1.0), scope=P(1.0), controls=(), horizon=HORIZON):
    return EdgeFactors(source, target, edge_type, horizon, semantics, activation, p_unsafe, exposure, capability, scope,
                       tuple(controls))


def _graph(*edges: tuple[str, str, str]) -> GraphState:
    return GraphState(main_api.GRAPH_HASH, (GraphNode("agent", NodeClass.AGENT), GraphNode("tool", NodeClass.TOOL)),
                      tuple(GraphEdge(*edge) for edge in edges))


def _code(callable_, *args) -> tuple[str, ReasonCode]:
    with pytest.raises(ArcanaValidationError) as error:
        callable_(*args)
    return error.value.code, error.value.primary_issue.reason_code


# F7: one versioned formula


def test_conformance_corpus_is_reproduced_exactly() -> None:
    assert CORPUS["contract_version"] == EDGE_WEIGHT_MODEL_VERSION
    for case in CORPUS["cases"]:
        factors = EdgeFactors.from_mapping(case["factors"])
        exact = exact_edge_weight(factors)
        rounded = edge_weight(factors)
        for position, name in enumerate(("lower", "mean", "upper")):
            assert exact[position] == Fraction(case["expected"]["exact"][name]), (case["id"], name)
            assert getattr(rounded, name) == float.fromhex(case["expected"]["binary64_hex"][name]), (case["id"], name)


def test_conditional_chain_multiplies_every_factor() -> None:
    weight = exact_edge_weight(_factors(activation=P(2.0), p_unsafe=P(0.5), exposure=P(0.5), scope=P(0.5),
                                        controls=(EdgeControl("review", P(0.5)),)))
    assert weight == (Fraction(1, 8),) * 3


def test_reversibility_is_not_a_propagation_factor() -> None:
    assert not hasattr(_factors(), "reversibility")
    assert not hasattr(_factors(), "detectability")
    assert not hasattr(_factors(), "gate_effectiveness")


# F8: no independence assumption without a declared conditional chain


def test_identical_marginal_events_are_not_squared() -> None:
    marginal = exact_edge_weight(_factors(semantics=MARGINAL, p_unsafe=P(0.5), exposure=P(0.5)))
    chain = exact_edge_weight(_factors(semantics=CHAIN, p_unsafe=P(0.5), exposure=P(0.5)))
    assert marginal == (Fraction(0), Fraction(1, 4), Fraction(1, 2))
    assert chain == (Fraction(1, 4),) * 3


def test_detection_and_gate_are_not_discounted_twice() -> None:
    controls = (EdgeControl("detection", P(0.5)), EdgeControl("gate", P(0.5)))
    lower, _, upper = exact_edge_weight(_factors(semantics=MARGINAL, controls=controls))
    assert upper == Fraction(1, 2)  # the legacy (1 - d)(1 - g) gave 1/4
    assert lower == 0
    joint = exact_edge_weight(_factors(semantics=MARGINAL, controls=(EdgeControl("detect_then_gate", P(0.75)),)))
    assert joint == (Fraction(3, 4),) * 3


def test_frechet_lower_bound() -> None:
    lower, _, upper = exact_edge_weight(_factors(semantics=MARGINAL, p_unsafe=P(0.75), exposure=P(0.75)))
    assert (lower, upper) == (Fraction(1, 2), Fraction(3, 4))


def test_unknown_probability_gives_no_credit() -> None:
    assert exact_edge_weight(_factors(p_unsafe=UNKNOWN_PROBABILITY)) == (Fraction(0), Fraction(1), Fraction(1))


def test_random_intervals_are_enclosed_and_ordered() -> None:
    generator = random.Random(20261030)

    def interval(scale: float = 1.0) -> FactorInterval:
        lower, mean, upper = sorted(generator.random() * scale for _ in range(3))
        return FactorInterval(lower, mean, upper)

    for _ in range(300):
        controls = tuple(EdgeControl(f"c{index}", interval()) for index in range(generator.randrange(4)))
        base = dict(activation=interval(5.0), p_unsafe=interval(), exposure=interval(), capability=interval(),
                    scope=interval(), controls=controls)
        chain, marginal = (exact_edge_weight(_factors(semantics=semantics, **base)) for semantics in (CHAIN, MARGINAL))
        assert marginal[0] <= chain[0] and chain[2] <= marginal[2]  # Frechet bounds enclose the chain product
        assert chain[1] == marginal[1]
        for exact, semantics in ((chain, CHAIN), (marginal, MARGINAL)):
            rounded = edge_weight(_factors(semantics=semantics, **base))
            assert Fraction(rounded.lower) <= exact[0] <= exact[1] <= exact[2] <= Fraction(rounded.upper)
            assert rounded.lower <= rounded.mean <= rounded.upper
            extra = (*controls, EdgeControl("extra", interval()))
            assert exact_edge_weight(_factors(semantics=semantics, **{**base, "controls": extra}))[2] <= exact[2]


# Matrix construction


def test_bundle_sums_parallel_edges_and_binds_the_graph() -> None:
    graph = _graph(("agent", "tool", "delegation"), ("agent", "tool", "memory_write"), ("tool", "agent", "result"))
    factors = (_factors(edge_type="delegation", p_unsafe=P(0.25)), _factors(edge_type="memory_write", p_unsafe=P(0.125)),
               _factors("tool", "agent", "result", semantics=MARGINAL, p_unsafe=P(0.5), exposure=P(0.5)))
    bundle = propagation_bundle(graph, factors, HORIZON)
    assert bundle.upper.node_order == ("agent", "tool")
    assert bundle.upper.graph_hash == main_api.GRAPH_HASH
    assert bundle.upper.values.tolist() == [[0.0, 0.375], [0.5, 0.0]]
    assert bundle.mean.values.tolist() == [[0.0, 0.375], [0.25, 0.0]]
    assert bundle.lower.values.tolist() == [[0.0, 0.375], [0.0, 0.0]]
    shuffled = propagation_bundle(graph, tuple(reversed(factors)), HORIZON)
    assert all((getattr(shuffled, name).values == getattr(bundle, name).values).all() for name in ("lower", "mean", "upper"))


def test_parallel_edges_round_once_per_entry() -> None:
    graph = _graph(("agent", "tool", "a"), ("agent", "tool", "b"), ("agent", "tool", "c"))
    factors = tuple(_factors(edge_type=name, p_unsafe=P(0.1)) for name in ("a", "b", "c"))
    upper = propagation_bundle(graph, factors, HORIZON).upper.values[0, 1]
    exact = 3 * Fraction(0.1)
    assert Fraction(upper) >= exact and Fraction(float(upper)) - exact < Fraction(2) ** -52


def test_built_bundle_feeds_the_evaluator() -> None:
    graph = _graph(("agent", "tool", "delegation"), ("tool", "agent", "result"))
    factors = (_factors(p_unsafe=P(0.5), scope=P(0.5)), _factors("tool", "agent", "result", p_unsafe=P(0.25)))
    request = main_api._request(matrix_bundle=propagation_bundle(graph, factors, HORIZON))
    allowed = evaluate_decision(complete_admission(request))
    assert allowed.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY
    assert allowed.metrics["rho_upper"] == pytest.approx(0.25)
    hot = (_factors(activation=P(16.0), p_unsafe=P(0.5)), factors[1])
    denied = evaluate_decision(complete_admission(main_api._request(matrix_bundle=propagation_bundle(graph, hot, HORIZON))))
    assert denied.reason_codes[0] is ReasonCode.DENY_RHO_UPPER_BOUND


def test_graph_edge_without_factors_cannot_default() -> None:
    graph = _graph(("agent", "tool", "delegation"), ("tool", "agent", "result"))
    assert _code(propagation_bundle, graph, (_factors(),), HORIZON) == ("edge_factors_missing", ReasonCode.DENY_CALIBRATION_INSUFFICIENT)


@pytest.mark.parametrize("factors,code,reason", [
    ((_factors(), _factors()), "edge_factors_duplicate", ReasonCode.DENY_MODEL_INPUT_INVALID),
    ((_factors(edge_type="unknown"),), "edge_factors_unknown_edge", ReasonCode.DENY_MODEL_INPUT_INVALID),
    ((_factors(horizon=DecisionHorizon("other", 60, "other")),), "edge_factors_horizon_mismatch",
     ReasonCode.DENY_DECISION_HORIZON_MISMATCH),
])
def test_factor_sets_must_match_graph_edges_one_to_one(factors, code, reason) -> None:
    assert _code(propagation_bundle, _graph(("agent", "tool", "delegation")), factors, HORIZON) == (code, reason)


@pytest.mark.parametrize("changes,code", [
    ({"p_unsafe": FactorInterval(0.2, 0.5, 1.5)}, "edge_factor_probability_out_of_range"),
    ({"exposure": FactorInterval(0.6, 0.5, 0.7)}, "edge_factor_interval_order_invalid"),
    ({"activation": FactorInterval(-1.0, 0.0, 1.0)}, "number_invalid"),
    ({"scope": FactorInterval(0.0, float("nan"), 1.0)}, "number_invalid"),
    ({"capability": 0.5}, "edge_factor_invalid"),
    ({"semantics": "independent"}, "enum_invalid"),
    ({"controls": (EdgeControl("gate", P(0.5)), EdgeControl("gate", P(0.4)))}, "edge_control_duplicate"),
    ({"controls": (EdgeControl("", P(0.5)),)}, "string_invalid"),
    ({"controls": ("gate",)}, "edge_control_invalid"),
])
def test_invalid_factors_are_model_input_errors(changes, code) -> None:
    issue_code, reason = _code(exact_edge_weight, replace(_factors(), **changes))
    assert reason is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert issue_code == code


def test_unrepresentable_weight_is_an_explicit_failure() -> None:
    graph = _graph(("agent", "tool", "a"), ("agent", "tool", "b"))
    factors = tuple(_factors(edge_type=name, activation=P(1.7e308)) for name in ("a", "b"))
    assert _code(propagation_bundle, graph, factors, HORIZON) == ("edge_weight_unrepresentable", ReasonCode.DENY_MODEL_INPUT_INVALID)
