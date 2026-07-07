from __future__ import annotations

import math

import pytest

from arcana.errors import ArcanaValidationError, ReasonCode
from arcana.matrices import MatrixBundle, PropagationMatrix, TolerancePolicy, spectral_radius


def test_nonnegative_square_matrix_spectral_radius() -> None:
    matrix = PropagationMatrix.from_values([[0.0, 0.5], [0.2, 0.0]], node_order=("agent", "tool"))

    assert math.isclose(matrix.spectral_radius(), math.sqrt(0.1), rel_tol=1e-12)
    assert math.isclose(spectral_radius(matrix), math.sqrt(0.1), rel_tol=1e-12)


def test_matrix_rejects_non_square_shape() -> None:
    with pytest.raises(ArcanaValidationError) as exc_info:
        PropagationMatrix.from_values([[0.0, 0.1, 0.2], [0.3, 0.0, 0.4]])

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "matrix_not_square"


def test_matrix_rejects_negative_values() -> None:
    with pytest.raises(ArcanaValidationError) as exc_info:
        PropagationMatrix.from_values([[0.0, -0.1], [0.2, 0.0]])

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "matrix_value_negative"


def test_matrix_rejects_nonfinite_values() -> None:
    with pytest.raises(ArcanaValidationError) as exc_info:
        PropagationMatrix.from_values([[0.0, math.inf], [0.2, 0.0]])

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "matrix_value_nonfinite"


def test_matrix_rejects_nonnumeric_values() -> None:
    with pytest.raises(ArcanaValidationError) as exc_info:
        PropagationMatrix.from_values([[0.0, "0.1"], [0.2, 0.0]])

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "matrix_value_invalid"


def test_node_order_must_match_matrix_size_and_be_unique() -> None:
    with pytest.raises(ArcanaValidationError) as size_exc:
        PropagationMatrix.from_values([[0.0, 0.1], [0.2, 0.0]], node_order=("agent",))

    assert size_exc.value.code == "matrix_node_order_size_mismatch"

    with pytest.raises(ArcanaValidationError) as unique_exc:
        PropagationMatrix.from_values([[0.0, 0.1], [0.2, 0.0]], node_order=("agent", "agent"))

    assert unique_exc.value.code == "matrix_node_order_not_unique"


def test_matrix_bundle_validates_interval_order_and_spectral_radii() -> None:
    bundle = MatrixBundle.from_values(
        lower=[[0.0, 0.1], [0.1, 0.0]],
        mean=[[0.0, 0.2], [0.1, 0.0]],
        upper=[[0.0, 0.4], [0.2, 0.0]],
        node_order=("agent", "tool"),
    )

    interval = bundle.spectral_radii(threshold=0.8)

    assert interval.lower <= interval.mean <= interval.upper
    assert math.isclose(interval.upper, math.sqrt(0.08), rel_tol=1e-12)
    assert interval.threshold == 0.8


def test_matrix_bundle_rejects_interval_order_violation() -> None:
    with pytest.raises(ArcanaValidationError) as exc_info:
        MatrixBundle.from_values(
            lower=[[0.0, 0.3], [0.1, 0.0]],
            mean=[[0.0, 0.2], [0.1, 0.0]],
            upper=[[0.0, 0.4], [0.2, 0.0]],
        )

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "matrix_interval_order_invalid"


def test_tolerance_policy_blocks_near_threshold_allow() -> None:
    policy = TolerancePolicy(abs_tolerance=0.01, rel_tolerance=0.0)

    assert policy.below_threshold_with_margin(0.78, 0.8)
    assert not policy.below_threshold_with_margin(0.795, 0.8)


def test_tolerance_policy_rejects_invalid_values() -> None:
    with pytest.raises(ArcanaValidationError) as exc_info:
        TolerancePolicy(abs_tolerance=-0.1)

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "number_invalid"


def test_public_rho_threshold_must_not_exceed_subcritical_limit() -> None:
    bundle = MatrixBundle.from_values(
        lower=[[0.0, 0.05], [0.05, 0.0]],
        mean=[[0.0, 0.1], [0.1, 0.0]],
        upper=[[0.0, 0.2], [0.2, 0.0]],
    )

    with pytest.raises(ArcanaValidationError) as exc_info:
        bundle.spectral_radii(threshold=1.01)

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "number_out_of_range"
