from dataclasses import replace
from fractions import Fraction
import math

import pytest

from arcana.errors import FastGateMode, ReasonCode, Verdict
from arcana.fastgate import evaluate_fastgate
from arcana.matrices import PropagationMatrix, SpectralBounds
from test_fastgate import _budget, _delta, _empty_delta, _positive_vector, _request


@pytest.mark.parametrize("mode", [FastGateMode.EXACT_RECOMPUTE, FastGateMode.PERRON_COLLATZ_BOUND])
def test_budget_never_subtracts_a_before_upper_bound(monkeypatch: pytest.MonkeyPatch, mode: FastGateMode) -> None:
    # A loose but valid certificate for the before matrix must not reduce cost.
    monkeypatch.setattr("arcana.fastgate.spectral_bounds", lambda matrix: SpectralBounds(0.0, 0.7))
    evaluation = evaluate_fastgate(_request(mode=mode, positive_vector=_positive_vector(), autonomy_budget=_budget(0.1)))
    assert evaluation.decision.verdict is Verdict.DENY
    assert evaluation.decision.reason_codes == (ReasonCode.DENY_BUDGET_EXHAUSTED,)


def test_after_matrix_addition_rounds_outward() -> None:
    request = _request(delta_upper=_delta(math.ulp(0.2) / 4))
    evaluation = evaluate_fastgate(request)
    assert evaluation.after_upper is not None
    exact = Fraction(0.2) + Fraction(math.ulp(0.2) / 4)
    assert Fraction(float(evaluation.after_upper.values[0, 1])) >= exact


def test_extreme_cycle_exact_recompute_never_allows() -> None:
    request = _request(delta_upper=_empty_delta(), autonomy_budget=_budget(10))
    request = replace(request, before_upper=PropagationMatrix(
        [[0, 1e250], [1e-250, 0]], ("agent", "tool"), request.graph_hash,
    ))
    evaluation = evaluate_fastgate(request)
    assert evaluation.decision.verdict is Verdict.DENY
    assert evaluation.decision.reason_codes == (ReasonCode.DENY_RHO_UPPER_BOUND,)


def test_no_delta_does_not_round_up_the_after_matrix() -> None:
    request = _request(delta_upper=_empty_delta())
    evaluation = evaluate_fastgate(request)
    assert evaluation.after_upper is not None
    assert (evaluation.after_upper.values == request.before_upper.values).all()


def test_overflowing_delta_has_specific_issue_code() -> None:
    maximum = float.fromhex("0x1.fffffffffffffp+1023")
    request = _request(delta_upper=_delta(maximum))
    request = replace(request, before_upper=PropagationMatrix(
        [[0, maximum], [0, 0]], ("agent", "tool"), request.graph_hash,
    ))
    result = evaluate_fastgate(request).decision
    assert result.verdict is Verdict.DENY
    assert result.metrics["issue_code"] == "fastgate_after_entry_unrepresentable"
