"""Loss-bound validation for ARCANA."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from arcana._validation import expect_number_min
from arcana.errors import ReasonCode
from arcana.model import LossBounds, validate_loss_tail_order


@dataclass(frozen=True)
class LossBoundEvaluation:
    metrics: Mapping[str, float]
    reason_code: ReasonCode | None = None
    issue_code: str | None = None

    @property
    def passed(self) -> bool:
        return self.reason_code is None


def evaluate_loss_bounds(loss_bounds: LossBounds | None, *, loss_in_scope: bool) -> LossBoundEvaluation:
    if not loss_in_scope:
        return LossBoundEvaluation(metrics={})
    if not isinstance(loss_bounds, LossBounds):
        return LossBoundEvaluation(
            metrics={},
            reason_code=ReasonCode.DENY_LOSS_MODEL_INVALID,
            issue_code="loss_bounds_missing",
        )

    metrics = validate_loss_bounds(loss_bounds)
    if metrics["aar_99_upper"] > metrics["max_allowed_aar_99"]:
        return LossBoundEvaluation(
            metrics=metrics,
            reason_code=ReasonCode.DENY_AAR_UPPER_BOUND,
            issue_code="aar_upper_bound_exceeded",
        )
    if metrics["aes_99_upper"] > metrics["max_allowed_aes_99"]:
        return LossBoundEvaluation(
            metrics=metrics,
            reason_code=ReasonCode.DENY_AES_UPPER_BOUND,
            issue_code="aes_upper_bound_exceeded",
        )
    return LossBoundEvaluation(metrics=metrics)


def validate_loss_bounds(loss_bounds: LossBounds) -> dict[str, float]:
    """Check the loss model itself (non-negative, AES >= AaR) before any limit is compared."""
    metrics = {
        name: expect_number_min(getattr(loss_bounds, name), 0, ("loss_bounds", name), ReasonCode.DENY_LOSS_MODEL_INVALID)
        for name in ("aar_99_upper", "aes_99_upper", "max_allowed_aar_99", "max_allowed_aes_99")
    }
    validate_loss_tail_order(metrics["aar_99_upper"], metrics["aes_99_upper"], ("loss_bounds", "aes_99_upper"))
    return metrics


__all__ = [
    "LossBoundEvaluation",
    "LossBounds",
    "evaluate_loss_bounds",
    "validate_loss_bounds",
]
