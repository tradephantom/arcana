"""arcana.ledger.v1: linearizable admission against one committed graph state."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from admission_support import complete_admission
import test_decision_reason_codes as main_api
import test_fastgate as fastgate_api
from arcana.errors import ReasonCode, Verdict
from arcana.fastgate import SparseDeltaEntry, SparseMatrixDelta, compute_sparse_delta_hash, evaluate_fastgate
from arcana.ledger import LEDGER_CONTRACT_VERSION, ReferenceAdmissionLedger
from arcana.matrices import PropagationMatrix

A_TO_B = (0, 1)
B_TO_A = (1, 0)


def _zero() -> PropagationMatrix:
    return PropagationMatrix.from_values([[0.0, 0.0], [0.0, 0.0]], node_order=("agent", "tool"),
                                         graph_hash=fastgate_api.GRAPH_HASH)


def _edge_request(before: PropagationMatrix, edge: tuple[int, int], weight: float = 0.95):
    entries = (SparseDeltaEntry(row=edge[0], column=edge[1], value=weight),)
    horizon = fastgate_api._horizon()
    delta = SparseMatrixDelta(
        compute_sparse_delta_hash(graph_hash=fastgate_api.GRAPH_HASH, decision_horizon=horizon, entries=entries),
        fastgate_api.GRAPH_HASH, horizon, entries,
    )
    request = complete_admission(fastgate_api._request(before_upper=before, delta_upper=delta))
    seed = tuple(1.0 if index == edge[0] else 0.0 for index in range(before.size))
    return replace(request, temporal=replace(request.temporal, initial_upper=seed))


def test_each_half_cycle_alone_is_admissible_against_the_same_baseline() -> None:
    for edge in (A_TO_B, B_TO_A):
        evaluation = evaluate_fastgate(_edge_request(_zero(), edge))
        assert evaluation.allowed
        assert evaluation.decision.metrics["rho_after_upper"] == 0.0


def test_audit_f3_split_cycle_is_denied_once_the_first_half_is_committed() -> None:
    ledger = ReferenceAdmissionLedger(_zero())
    first = ledger.admit_fastgate(_edge_request(ledger.current().upper, A_TO_B), expected_version=0)
    assert first.committed and first.state.version == 1
    assert first.decision.metrics["ledger_contract_version"] == LEDGER_CONTRACT_VERSION

    stale = ledger.admit_fastgate(_edge_request(_zero(), B_TO_A), expected_version=0)
    assert not stale.committed
    assert stale.decision.reason_codes == (ReasonCode.DENY_CONTEXT_STALE,)
    assert stale.decision.metrics["issue_code"] == "ledger_graph_version_conflict"

    wrong_base = ledger.admit_fastgate(_edge_request(_zero(), B_TO_A), expected_version=1)
    assert wrong_base.decision.metrics["issue_code"] == "ledger_before_state_mismatch"

    rebuilt = ledger.admit_fastgate(_edge_request(ledger.current().upper, B_TO_A), expected_version=1)
    assert rebuilt.decision.verdict is Verdict.DENY
    assert rebuilt.decision.reason_codes == (ReasonCode.DENY_RHO_UPPER_BOUND,)
    assert rebuilt.decision.metrics["temporal_envelope_rho_upper"] >= 0.8
    assert not rebuilt.committed
    assert ledger.current().version == 1
    assert ledger.current().upper.values[1][0] == 0.0


def test_concurrent_admissions_from_one_baseline_commit_exactly_once() -> None:
    ledger = ReferenceAdmissionLedger(_zero())
    requests = [_edge_request(_zero(), edge) for edge in (A_TO_B, B_TO_A)] * 8
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda request: ledger.admit_fastgate(request, expected_version=0), requests))
    assert sum(outcome.committed for outcome in outcomes) == 1
    assert ledger.current().version == 1
    for outcome in outcomes:
        if not outcome.committed:
            assert outcome.decision.metrics["issue_code"] == "ledger_graph_version_conflict"


def test_only_allow_like_verdicts_are_committed() -> None:
    ledger = ReferenceAdmissionLedger(fastgate_api._before_matrix())
    legacy = ledger.admit_fastgate(fastgate_api._request(), expected_version=0)
    assert legacy.decision.verdict is Verdict.OBSERVE_ONLY
    assert not legacy.committed and ledger.current().version == 0
    admitted = ledger.admit_fastgate(complete_admission(fastgate_api._request()), expected_version=0)
    assert admitted.committed and admitted.evaluation is not None
    assert admitted.state.upper.values[0][1] == admitted.evaluation.after_upper.values[0][1]


def test_main_evaluator_commits_only_when_its_increment_is_bound_to_the_committed_state() -> None:
    request = complete_admission(main_api._request())
    ledger = ReferenceAdmissionLedger(request.increment.before.upper)
    unbound = ledger.admit_decision(main_api._request(), expected_version=0)
    assert unbound.decision.metrics["issue_code"] == "ledger_before_state_unbound"
    outcome = ledger.admit_decision(request, expected_version=0)
    assert outcome.decision.verdict is Verdict.ALLOW_BOUNDED_AUTONOMY
    assert outcome.committed and ledger.current().version == 1


@pytest.mark.parametrize("expected_version", [-1, "0", 1.5, True])
def test_malformed_expected_version_is_denied_without_commit(expected_version) -> None:
    ledger = ReferenceAdmissionLedger(_zero())
    outcome = ledger.admit_fastgate(_edge_request(_zero(), A_TO_B), expected_version=expected_version)
    assert outcome.decision.verdict is Verdict.DENY
    assert not outcome.committed and ledger.current().version == 0


def test_committed_state_is_an_immutable_snapshot() -> None:
    ledger = ReferenceAdmissionLedger(_zero())
    state = ledger.current()
    with pytest.raises(ValueError):
        state.upper.values[0][1] = 1.0
    assert ledger.current().state_hash == state.state_hash
