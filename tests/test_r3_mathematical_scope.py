"""Exact analytic oracles and counterexamples to claims outside model scope.

These tests do not supply empirical calibration or an independent review.
The oracles use rational identities, not the implementation's eigensolver.
"""

from fractions import Fraction
from itertools import product
import math

import numpy as np
import pytest

from arcana.errors import CalibrationLevel, FastGateMode, PositiveVectorMethod, Verdict
from arcana.fastgate import (
    FastGateRequest,
    PositiveVector,
    SparseDeltaEntry,
    SparseMatrixDelta,
    compute_sparse_delta_hash,
    evaluate_fastgate,
)
from arcana.matrices import PropagationMatrix, spectral_bounds
from arcana.model import AutonomyBudget, DecisionHorizon


def _rational(values):
    return tuple(tuple(Fraction(value) for value in row) for row in values)


def _identity(size):
    return tuple(tuple(Fraction(i == j) for j in range(size)) for i in range(size))


def _multiply(left, right):
    assert len(left[0]) == len(right)
    return tuple(
        tuple(sum((a * b for a, b in zip(row, column, strict=True)), Fraction(0))
              for column in zip(*right, strict=True))
        for row in left
    )


@pytest.mark.parametrize("size", [3, 5, 7])
@pytest.mark.parametrize("radius", [Fraction(1, 2), Fraction(1), Fraction(5, 4)])
@pytest.mark.parametrize("transpose", [False, True])
def test_periodic_scaled_cycles_enclose_exact_oracle(size, radius, transpose):
    exponents = [-400 + (800 * i) // (size - 1) for i in range(size)]
    values = [[0.0] * size for _ in range(size)]
    for i in range(size):
        j = (i + 1) % size
        values[i][j] = math.ldexp(float(radius), exponents[i] - exponents[j])
    if transpose:
        values = list(map(list, zip(*values, strict=True)))

    # A^n = r^n I proves every eigenvalue has modulus r, with no float oracle.
    exact = _rational(values)
    power = _identity(size)
    for _ in range(size):
        power = _multiply(power, exact)
    expected = tuple(tuple(radius**size * cell for cell in row) for row in _identity(size))
    assert power == expected
    bounds = spectral_bounds(values)
    assert Fraction(bounds.lower) <= radius <= Fraction(bounds.upper)


def test_periodic_oracle_survives_failed_candidate_eigensolver(monkeypatch):
    def failed(_values):
        raise np.linalg.LinAlgError("synthetic candidate failure")

    monkeypatch.setattr(np.linalg, "eig", failed)
    values = [[0.0, 2.0**200, 0.0], [0.0, 0.0, 0.5], [2.0**-202, 0.0, 0.0]]
    # The product around the cycle is 1/8, so rho = 1/2.
    bounds = spectral_bounds(values)
    assert Fraction(bounds.lower) <= Fraction(1, 2) <= Fraction(bounds.upper)


def test_zero_radius_does_not_bound_finite_horizon_transient():
    scale = 2**200
    values = [[0, scale, 0], [0, 0, scale], [0, 0, 0]]
    exact = _rational(values)
    square = _multiply(exact, exact)
    cube = _multiply(square, exact)
    assert square[0][2] == 2**400
    assert all(cell == 0 for row in cube for cell in row)
    bounds = spectral_bounds(values)
    assert bounds.lower == bounds.upper == 0.0


def test_individually_subcritical_snapshots_do_not_prove_switching_stability():
    left = [[0, 2], [0, 0]]
    right = [[0, 0], [2, 0]]
    assert spectral_bounds(left).upper == spectral_bounds(right).upper == 0.0
    combined = _multiply(_rational(left), _rational(right))
    assert combined == _rational([[4, 0], [0, 0]])
    assert spectral_bounds([[float(cell) for cell in row] for row in combined]).lower == 4.0


def test_common_entrywise_dominator_bounds_all_declared_switching_words():
    left = _rational([[0, Fraction(1, 2)], [0, 0]])
    right = _rational([[0, 0], [Fraction(1, 4), 0]])
    upper = _rational([[0, Fraction(1, 2)], [Fraction(1, 4), 0]])
    upper_power = _identity(2)
    for length in range(1, 7):
        upper_power = _multiply(upper_power, upper)
        for word in product((left, right), repeat=length):
            actual = _identity(2)
            for matrix in word:
                actual = _multiply(actual, matrix)
            for row, envelope in zip(actual, upper_power, strict=True):
                assert all(value <= bound for value, bound in zip(row, envelope, strict=True))
                assert sum(row) <= Fraction(1, 2)**length


def test_finite_sum_does_not_require_subcriticality():
    radius = Fraction(5, 4)
    assert sum(radius**generation for generation in range(4)) == Fraction(369, 64)
    assert spectral_bounds([[float(radius)]]).lower > 1.0


def _budget_scope_request(mode):
    graph_hash = "sha256:" + "1" * 64
    horizon = DecisionHorizon("r3_scope", 300, "synthetic mathematical scope")
    entries = (SparseDeltaEntry(1, 0, 0.28125),)
    delta = SparseMatrixDelta(
        delta_hash=compute_sparse_delta_hash(graph_hash=graph_hash, decision_horizon=horizon, entries=entries),
        graph_hash=graph_hash,
        decision_horizon=horizon,
        entries=entries,
    )
    return FastGateRequest(
        mode=mode,
        risk_model_version="arcana.risk.v0.2",
        calibration_profile_id="arcana.cal.r3_scope_a1",
        calibration_level=CalibrationLevel.A1,
        required_calibration_level=CalibrationLevel.A1,
        decision_horizon=horizon,
        decision_time="2026-09-10T10:00:00Z",
        graph_hash=graph_hash,
        before_upper=PropagationMatrix([[0.0, 0.5], [0.5, 0.0]], ("a", "b"), graph_hash),
        delta_upper=delta,
        threshold=0.9,
        autonomy_budget=AutonomyBudget("2026-09-10T11:00:00Z", 0.25, 0, 0, 0),
        positive_vector=PositiveVector(
            (1.0, 1.25), ("a", "b"), graph_hash,
            PositiveVectorMethod.IRREDUCIBLE_PERRON_VECTOR, irreducible_declared=True,
        ),
        evidence_hash="sha256:" + "2" * 64,
    )


@pytest.mark.parametrize("mode,metric", [
    (FastGateMode.EXACT_RECOMPUTE, "delta_rho_upper"),
    (FastGateMode.PERRON_COLLATZ_BOUND, "delta_rho_upper_bound"),
])
def test_fastgate_increment_bounds_upper_model_not_unknown_baseline(mode, metric):
    request = _budget_scope_request(mode)
    result = evaluate_fastgate(request).decision
    assert result.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY
    reported = Fraction(result.metrics[metric])

    # Upper model: sqrt((1/2)*(25/32)) - 1/2 = 1/8.
    assert Fraction(1, 2) * Fraction(25, 32) == Fraction(5, 8)**2
    assert Fraction(1, 8) <= reported <= Fraction(1, 4)

    # Compatible actual baseline: [[0,1/2],[0,0]], same additive delta 9/32.
    # Its radius rises from zero to 3/8, beyond the declared 1/4 budget.
    assert Fraction(1, 2) * Fraction(9, 32) == Fraction(3, 8)**2
    actual_before = np.array([[0.0, 0.5], [0.0, 0.0]])
    assert np.all(actual_before <= request.before_upper.values)
    assert Fraction(3, 8) > Fraction(request.autonomy_budget.max_delta_rho_upper)
    assert reported < Fraction(3, 8)


def test_dependent_factor_marginals_do_not_bound_joint_probability_by_product():
    outcomes = (0, 1)
    first = {1}
    second = {1}
    marginal_product = Fraction(len(first), len(outcomes)) * Fraction(len(second), len(outcomes))
    joint = Fraction(len(first & second), len(outcomes))
    assert joint == Fraction(1, 2) > marginal_product == Fraction(1, 4)


def test_marginal_coverage_does_not_supply_same_simultaneous_coverage():
    outcomes = set(range(100))
    first_covered = outcomes - {0}
    second_covered = outcomes - {1}
    assert Fraction(len(first_covered), 100) == Fraction(99, 100)
    assert Fraction(len(second_covered), 100) == Fraction(99, 100)
    assert Fraction(len(first_covered & second_covered), 100) == Fraction(98, 100)


def test_discrete_expected_shortfall_is_not_strict_exceedance_mean():
    # Four equally likely losses: at alpha=1/2, the quantile is 1 and the
    # upper half of probability mass consists of one 1 and one 5.
    losses = (1, 1, 1, 5)
    quantile = 1
    quantile_integral_tail_mean = Fraction(losses[2] + losses[3], 2)
    exceedances = tuple(value for value in losses if value > quantile)
    strict_exceedance_mean = Fraction(sum(exceedances), len(exceedances))
    assert quantile_integral_tail_mean == 3
    assert strict_exceedance_mean == 5
    assert quantile_integral_tail_mean != strict_exceedance_mean
