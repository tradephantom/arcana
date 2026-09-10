"""Adversarial regression cases for the represented binary64 matrix contract."""

from dataclasses import replace
from decimal import Decimal, localcontext
from fractions import Fraction
import json
import math
from pathlib import Path
import random

import numpy as np
import pytest

from arcana.decision import evaluate_decision
from arcana.errors import ArcanaValidationError, ReasonCode, Verdict
from arcana.matrices import MatrixBundle, PropagationMatrix, TolerancePolicy, spectral_bounds, spectral_radius
from arcana._numerics import nonnegative_difference_upper, verified_collatz_bounds
from test_decision_reason_codes import _request


def test_extreme_cycle_cannot_be_admitted_as_zero() -> None:
    request = _request()
    values = [[0.0, 1e250], [1e-250, 0.0]]
    matrix = MatrixBundle.from_values(
        values, values, values, node_order=("agent", "tool"), graph_hash=request.graph_hash,
    )
    result = evaluate_decision(replace(request, matrix_bundle=matrix, rho_threshold=0.8))
    assert result.verdict is Verdict.DENY
    assert result.reason_codes == (ReasonCode.DENY_RHO_UPPER_BOUND,)
    assert result.metrics["rho_upper"] >= 1.0
    assert result.metrics["numerical_contract_version"] == "arcana.numerical.v1"


def test_direct_constructor_rejects_negative_matrix() -> None:
    with pytest.raises(ArcanaValidationError, match="nonnegative"):
        PropagationMatrix(np.array([[0.0, -0.2], [-0.2, 0.0]]))


def test_direct_bundle_rejects_missing_members() -> None:
    with pytest.raises(ArcanaValidationError) as error:
        MatrixBundle(None, None, None)
    assert error.value.code == "matrix_bundle_member_invalid"


def test_matrix_storage_cannot_be_made_writeable() -> None:
    source = np.array([[0.0, 0.2], [0.2, 0.0]])
    matrix = PropagationMatrix(source)
    source[0, 1] = 100.0
    assert matrix.values[0, 1] == 0.2
    with pytest.raises(ValueError):
        matrix.values.setflags(write=True)
    with pytest.raises(ValueError):
        matrix.values[0, 1] = 100.0


def test_spectral_radius_of_extreme_cycle_is_not_underestimated() -> None:
    assert spectral_radius([[0.0, 1e250], [1e-250, 0.0]]) >= 1.0


def test_spectral_radius_of_subnormal_self_loop_is_not_zero() -> None:
    tiny = math.ulp(0.0)
    assert spectral_radius([[tiny]]) == tiny


@pytest.mark.parametrize("exponent", [-300, -250, -100, 0, 100, 250, 300])
def test_two_cycle_bounds_enclose_high_precision_analytic_oracle(exponent: int) -> None:
    b, c = 10.0**exponent, 10.0**-exponent
    bound = spectral_bounds([[0, b], [c, 0]])
    with localcontext() as context:
        context.prec = 160
        oracle = (Decimal.from_float(b) * Decimal.from_float(c)).sqrt()
        assert Decimal.from_float(bound.lower) <= oracle <= Decimal.from_float(bound.upper)
    assert bound.upper - bound.lower < 1e-12


def test_seeded_two_by_two_bounds_against_exact_characteristic_polynomial() -> None:
    rng = random.Random(20260910)
    for _ in range(128):
        values = [[10.0**rng.randint(-300, 300) * rng.uniform(0.1, 1) for _ in range(2)] for _ in range(2)]
        bounds = spectral_bounds(values)
        a, b, c, d = [Fraction(value) for row in values for value in row]
        trace = a + d
        discriminant = (a - d)**2 + 4 * b * c
        upper_test = 2 * Fraction(bounds.upper) - trace
        lower_test = 2 * Fraction(bounds.lower) - trace
        assert upper_test >= 0 and upper_test**2 >= discriminant
        assert lower_test <= 0 or lower_test**2 <= discriminant


@pytest.mark.parametrize("radius", [0.25, 0.75, 1.0, 1.25])
@pytest.mark.parametrize("size", [2, 4, 8])
def test_diagonal_similarity_preserves_verified_enclosure(radius: float, size: int) -> None:
    exponents = np.linspace(-400, 400, size, dtype=int)
    matrix = np.array([[math.ldexp(radius / size, int(a - b)) for b in exponents] for a in exponents])
    bounds = spectral_bounds(matrix)
    assert bounds.lower <= radius <= bounds.upper
    assert math.isclose(bounds.upper, radius, rel_tol=1e-12)


def test_reducible_blocks_and_large_transient_edges() -> None:
    matrix = [[0.25, 1e300, 0], [0, 0, 1e250], [0, 1e-250, 0]]
    bounds = spectral_bounds(matrix)
    assert bounds.lower <= 1 <= bounds.upper
    assert math.isclose(bounds.upper, 1, rel_tol=1e-12)
    assert spectral_radius([[0, 1e300, 0], [0, 0, 1e300], [0, 0, 0]]) == 0


def test_wrong_or_failed_eigensolver_cannot_certify_false_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    def wrong(values):
        return np.zeros(2), np.ones((2, 2))

    monkeypatch.setattr(np.linalg, "eig", wrong)
    assert spectral_radius([[0, 1e250], [1e-250, 0]]) >= 1

    def failed(values):
        raise np.linalg.LinAlgError("test solver failure")

    monkeypatch.setattr(np.linalg, "eig", failed)
    assert math.isclose(spectral_radius([[0, 0.5], [0.125, 0]]), 0.25, rel_tol=1e-12)


@pytest.mark.parametrize("values,code", [
    ([[1, 2]], "matrix_not_square"),
    ([[math.nan]], "matrix_value_nonfinite"),
    ([[math.inf]], "matrix_value_nonfinite"),
    ([[True]], "matrix_value_invalid"),
    ([[1j]], "matrix_value_invalid"),
    ([[10**400]], "matrix_value_nonfinite"),
    (np.array([[1]], dtype="datetime64[D]"), "matrix_value_invalid"),
])
def test_direct_constructor_validates_all_entry_paths(values, code) -> None:
    with pytest.raises(ArcanaValidationError) as error:
        PropagationMatrix(values)
    assert error.value.code == code


def test_evaluator_revalidates_corrupted_bundle_without_attribute_error() -> None:
    request = _request()
    object.__setattr__(request.matrix_bundle, "upper", None)
    result = evaluate_decision(request)
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == "matrix_bundle_member_invalid"


def test_evaluator_revalidates_corrupted_values_before_use() -> None:
    request = _request()
    object.__setattr__(request.matrix_bundle.upper, "values", np.array([[0, -0.2], [-0.2, 0]]))
    result = evaluate_decision(request)
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == "matrix_value_negative"


def test_bundle_constructor_rejects_reversed_interval() -> None:
    with pytest.raises(ArcanaValidationError) as error:
        MatrixBundle(PropagationMatrix([[0.3]]), PropagationMatrix([[0.2]]), PropagationMatrix([[0.1]]))
    assert error.value.code == "matrix_interval_order_invalid"


def test_readonly_storage_has_no_writeable_base_alias() -> None:
    matrix = PropagationMatrix([[0.2]])
    with pytest.raises(ValueError):
        matrix.values.base.setflags(write=True)


@pytest.mark.parametrize("scale", [math.ulp(0.0), 1e-300, 1, 1e300, float(np.finfo(float).max)])
def test_collatz_certificate_is_invariant_to_extreme_vector_scale(scale: float) -> None:
    values = np.array([[0.75, 0.75], [0.75, 0.75]])
    bounds = verified_collatz_bounds(values, np.array([scale, scale]))
    assert bounds.lower == bounds.upper == 1.5


def test_collatz_does_not_erase_subnormal_products() -> None:
    tiny = math.ulp(0.0)
    bounds = verified_collatz_bounds(np.array([[tiny]]), np.array([tiny]))
    assert bounds.lower == bounds.upper == tiny


def test_unrepresentable_bound_has_explicit_failure() -> None:
    with pytest.raises(ArcanaValidationError) as error:
        spectral_bounds(np.full((2, 2), np.finfo(float).max))
    assert error.value.code == "spectral_bound_unrepresentable"


def test_delta_bound_subtracts_lower_endpoint_with_outward_rounding() -> None:
    result = nonnegative_difference_upper(0.7, 0.2)
    assert Fraction(result) >= Fraction(0.7) - Fraction(0.2)


def test_default_threshold_comparison_uses_exact_sum() -> None:
    policy = TolerancePolicy()
    for threshold in [0.1, 0.5, 0.8, 1.0]:
        cutoff = threshold - policy.margin(threshold)
        for value in [math.nextafter(cutoff, 0), cutoff, math.nextafter(cutoff, math.inf)]:
            expected = Fraction(value) + Fraction(policy.margin(threshold)) < Fraction(threshold)
            assert policy.below_threshold_with_margin(value, threshold) == expected


CORPUS = json.loads((Path(__file__).parent / "fixtures" / "numerical_contract_v1.json").read_text())


@pytest.mark.parametrize("case", CORPUS["threshold_cases"], ids=lambda case: case["id"])
def test_shared_threshold_conformance(case) -> None:
    assert TolerancePolicy().below_threshold_with_margin(case["upper"], case["threshold"]) == case["allowed"]


@pytest.mark.parametrize("case", CORPUS["matrix_cases"], ids=lambda case: case["id"])
def test_shared_matrix_admission_conformance(case) -> None:
    request = _request()
    matrix = MatrixBundle.from_values(
        case["matrix"], case["matrix"], case["matrix"], node_order=("agent", "tool"), graph_hash=request.graph_hash,
    )
    result = evaluate_decision(replace(request, matrix_bundle=matrix, rho_threshold=case["threshold"]))
    assert (result.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY) == case["allowed"]
    if case["rho"] is not None:
        assert result.metrics["rho_lower"] <= case["rho"] <= result.metrics["rho_upper"]
