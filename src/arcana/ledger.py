"""Reference committed-graph ledger with compare-and-swap admission.

Per-request budgets cannot see other requests: two actions evaluated against
the same baseline can each add zero spectral increment while together closing
a supercritical cycle. The ledger evaluates every admission against the single
committed graph state and commits the admitted state in the same critical
section, so admissions are linearizable. It is an in-memory reference for the
`arcana.ledger.v1` contract; integrations implement the same invariants on
their own durable store.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import threading
from typing import Any, Mapping

from arcana._validation import expect_int_min, fail
from arcana.decision import DecisionEvaluationRequest, evaluate_decision
from arcana.errors import ArcanaValidationError, ReasonCode, Verdict
from arcana.fastgate import FastGateEvaluation, FastGateRequest, evaluate_fastgate
from arcana.increments import IncrementSnapshot
from arcana.matrices import PropagationMatrix
from arcana.model import DecisionResult

LEDGER_CONTRACT_VERSION = "arcana.ledger.v1"
_ALLOW = frozenset({Verdict.ALLOW_BOUNDED_AUTONOMY, Verdict.ALLOW_WITH_CONTROLS})


@dataclass(frozen=True)
class CommittedGraphState:
    version: int
    upper: PropagationMatrix
    state_hash: str


@dataclass(frozen=True)
class LedgerOutcome:
    decision: DecisionResult
    committed: bool
    state: CommittedGraphState
    evaluation: FastGateEvaluation | None = None


class ReferenceAdmissionLedger:
    """Thread-safe in-memory ledger; one committed upper matrix, versioned."""

    def __init__(self, initial_upper: PropagationMatrix) -> None:
        self._lock = threading.Lock()
        self._state = _state(0, _committable(initial_upper))

    def current(self) -> CommittedGraphState:
        with self._lock:
            return self._state

    def admit_fastgate(self, request: FastGateRequest, *, expected_version: int) -> LedgerOutcome:
        with self._lock:
            failure = self._precondition_failure(expected_version, getattr(request, "before_upper", None))
            if failure is not None:
                return LedgerOutcome(failure, False, self._state)
            evaluation = evaluate_fastgate(request)
            return self._commit(evaluation.decision, evaluation.after_upper, evaluation)

    def admit_decision(self, request: DecisionEvaluationRequest, *, expected_version: int) -> LedgerOutcome:
        with self._lock:
            increment = getattr(request, "increment", None)
            before = None if increment is None else increment.before.upper
            failure = self._precondition_failure(expected_version, before)
            if failure is not None:
                return LedgerOutcome(failure, False, self._state)
            decision = evaluate_decision(request)
            after = getattr(getattr(request, "matrix_bundle", None), "upper", None)
            return self._commit(decision, after)

    def _precondition_failure(self, expected_version: Any, before: Any) -> DecisionResult | None:
        try:
            expected = expect_int_min(expected_version, 0, ("expected_version",), ReasonCode.DENY_CONTEXT_STALE)
        except ArcanaValidationError as exc:
            return _deny(exc.code, exc.primary_issue.message, self._state)
        if expected != self._state.version:
            return _deny("ledger_graph_version_conflict",
                         "re-read the committed graph state and re-evaluate the request", self._state,
                         {"ledger_expected_version": expected})
        if not isinstance(before, PropagationMatrix):
            return _deny("ledger_before_state_unbound",
                         "bind the request to the committed graph state (FastGate before_upper or increment before)",
                         self._state)
        if _hash(before) != self._state.state_hash:
            return _deny("ledger_before_state_mismatch",
                         "the request was built on a graph state that is not the committed one", self._state)
        return None

    def _commit(self, decision: DecisionResult, after: PropagationMatrix | None,
                evaluation: FastGateEvaluation | None = None) -> LedgerOutcome:
        before = self._state
        committed = decision.verdict in _ALLOW and isinstance(after, PropagationMatrix)
        if committed:
            self._state = _state(before.version + 1, _committable(after))
        metrics = {**decision.metrics, **_metrics(self._state), "ledger_version_before": before.version,
                   "ledger_committed": committed}
        return LedgerOutcome(replace(decision, metrics=metrics), committed, self._state, evaluation)


def _committable(matrix: Any) -> PropagationMatrix:
    if not isinstance(matrix, PropagationMatrix):
        fail("ledger_state_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID,
             "the committed state must be a PropagationMatrix", ("ledger", "upper"))
    if not matrix.node_order or matrix.graph_hash is None:
        fail("ledger_state_unbound", ReasonCode.DENY_MODEL_INPUT_INVALID,
             "the committed state needs node_order and graph_hash", ("ledger", "upper"))
    return PropagationMatrix(matrix.values, matrix.node_order, matrix.graph_hash)


def _hash(matrix: PropagationMatrix) -> str:
    return IncrementSnapshot(matrix).snapshot_hash


def _state(version: int, upper: PropagationMatrix) -> CommittedGraphState:
    return CommittedGraphState(version, upper, _hash(upper))


def _metrics(state: CommittedGraphState) -> dict[str, Any]:
    return {"ledger_contract_version": LEDGER_CONTRACT_VERSION, "ledger_version": state.version,
            "ledger_state_hash": state.state_hash}


def _deny(issue_code: str, message: str, state: CommittedGraphState,
          extra: Mapping[str, Any] | None = None) -> DecisionResult:
    return DecisionResult(
        verdict=Verdict.DENY,
        reason_codes=(ReasonCode.DENY_CONTEXT_STALE,),
        metrics={**_metrics(state), **(extra or {}), "issue_code": issue_code,
                 "ledger_version_before": state.version, "ledger_committed": False},
        caveats=(message,),
    )


__all__ = ["LEDGER_CONTRACT_VERSION", "CommittedGraphState", "LedgerOutcome", "ReferenceAdmissionLedger"]
