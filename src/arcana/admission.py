"""Admission contract policy shared by the main evaluator and FastGate.

Allow-like verdicts require verified accounting: a calibration profile bound to
its evidence by hash, a typed loss contract when loss is in scope, a bound increment contract
(no caller-declared spectral increment) and an evaluated temporal contract
whose initial state seeds every node whose outgoing propagation the increment
changes (finite-horizon cascade limits, which a spectral radius alone does not
provide). Requests that pass every check without them
are reported as observe-only, never as admission.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from arcana.calibration import CalibrationProfile
from arcana.errors import ReasonCode, Verdict
from arcana.increments import IncrementContract
from arcana.loss_contract import LossContract
from arcana.model import DecisionResult
from arcana.temporal import TemporalContract

ADMISSION_CONTRACT_POLICY = "arcana.admission.v1"


@dataclass(frozen=True)
class AdmissionTail:
    contract_gaps: tuple[str, ...]
    required_controls: tuple[str, ...] = ()
    available_controls: tuple[str, ...] = ()
    human_gate_required: bool = False
    scope_reduction_required: bool = False
    info_codes: tuple[ReasonCode, ...] = ()


def admission_contract_gaps(
    increment: IncrementContract | None,
    temporal: TemporalContract | None,
    *,
    calibration_profile: CalibrationProfile | None,
    loss_in_scope: bool,
    loss: LossContract | None,
) -> tuple[str, ...]:
    gaps = []
    if calibration_profile is None:
        gaps.append("calibration_profile_missing")
    elif calibration_profile.evidence_hash is None:
        gaps.append("calibration_evidence_hash_missing")
    if loss_in_scope and loss is None:
        gaps.append("loss_contract_missing")
    if increment is None:
        gaps.append("increment_contract_missing")
    if temporal is None:
        gaps.append("temporal_contract_missing")
    elif not any(value > 0 for value in temporal.initial_upper):
        gaps.append("temporal_initial_state_zero")
    elif increment is not None and any(temporal.initial_upper[source] <= 0 for source in changed_sources(increment)):
        gaps.append("temporal_seed_misses_changed_source")
    return tuple(gaps)


def changed_sources(increment: IncrementContract) -> tuple[int, ...]:
    """Rows (source nodes) whose outgoing propagation differs between the bound snapshots."""
    before, after = increment.before.upper.values, increment.after.upper.values
    return tuple(int(index) for index in np.flatnonzero(np.any(before != after, axis=1)))


def finalize_admission(tail: AdmissionTail, metrics: Mapping[str, Any]) -> DecisionResult:
    """Apply the shared decision tail once every risk, loss and budget check passed."""
    metrics = {**metrics, "admission_contract_policy": ADMISSION_CONTRACT_POLICY,
               "admission_contract_gaps": tail.contract_gaps}
    if tail.scope_reduction_required:
        return _result(Verdict.REQUIRE_SCOPE_REDUCTION, (ReasonCode.REQUIRE_SCOPE_REDUCTION, *tail.info_codes),
                       {**metrics, "issue_code": "scope_reduction_required"},
                       caveats=("requested capability envelope must be reduced before admission.",))
    if tail.human_gate_required:
        return _result(Verdict.REQUIRE_HUMAN_GATE, (ReasonCode.REQUIRE_HUMAN_GATE, *tail.info_codes),
                       {**metrics, "issue_code": "human_gate_required"}, tail.required_controls,
                       caveats=("human or policy approval is required before admission.",))
    missing_controls = tuple(control for control in tail.required_controls if control not in tail.available_controls)
    if missing_controls:
        return _result(Verdict.REQUIRE_HUMAN_GATE, (ReasonCode.REQUIRE_HUMAN_GATE, *tail.info_codes),
                       {**metrics, "issue_code": "required_controls_unavailable", "missing_controls": missing_controls},
                       tail.required_controls, caveats=("required controls are not declared available.",))
    if tail.contract_gaps:
        return _result(Verdict.OBSERVE_ONLY, (ReasonCode.REQUIRE_OBSERVE_ONLY, *tail.info_codes),
                       {**metrics, "issue_code": "admission_contracts_missing"}, tail.required_controls,
                       caveats=("allow-like admission requires a hash-bound calibration profile, bound increment "
                                "and temporal contracts and, when loss is in scope, a typed loss contract; legacy "
                                "caller-declared accounting is observe-only.",))
    if tail.required_controls:
        return _result(Verdict.ALLOW_WITH_CONTROLS, (ReasonCode.ALLOW_WITH_CONTROLS, *tail.info_codes),
                       metrics, tail.required_controls)
    return _result(Verdict.ALLOW_BOUNDED_AUTONOMY, (ReasonCode.ALLOW_BOUNDED_AUTONOMY, *tail.info_codes), metrics)


def _result(
    verdict: Verdict,
    reason_codes: Sequence[ReasonCode],
    metrics: Mapping[str, Any],
    required_controls: Sequence[str] = (),
    *,
    caveats: Sequence[str] = (),
) -> DecisionResult:
    return DecisionResult(
        verdict=verdict,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        metrics=dict(metrics),
        required_controls=tuple(required_controls),
        caveats=tuple(caveats),
    )


__all__ = ["ADMISSION_CONTRACT_POLICY", "AdmissionTail", "admission_contract_gaps", "changed_sources", "finalize_admission"]
