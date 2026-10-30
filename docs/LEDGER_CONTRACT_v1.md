# Ledger Contract v1

Status: local unreleased reference candidate, 2026-10-30.
Contract identifier: `arcana.ledger.v1`.

This contract makes admissions linearizable against one committed graph
state. It is not an empirical calibration claim or a production authorization.

## Problem

Budgets and spectral bounds are evaluated per request. Two requests built on
the same baseline can each be admissible while their combination is not: two
opposite edges of weight 0.95 each leave an acyclic graph with spectral radius
zero, but together they close a cycle with spectral radius 0.95. Without a
shared committed state, both can be admitted.

## Invariants

1. One committed upper matrix exists, with a version that starts at `0` and
   increases by one on every commit.
2. A request names the version it was built on (`expected_version`). A
   different current version denies with `ARCANA_DENY_CONTEXT_STALE`
   (`ledger_graph_version_conflict`); the caller re-reads the state and
   re-evaluates.
3. The request's baseline must be the committed matrix: FastGate
   `before_upper`, or the increment `before` snapshot on the main evaluator.
   A missing baseline denies with `ledger_before_state_unbound`; a different
   one with `ledger_before_state_mismatch`.
4. Evaluation and commit happen in one critical section. Only allow-like
   verdicts commit; the committed matrix is the evaluated after matrix.
5. Every result reports `ledger_contract_version`, `ledger_version`,
   `ledger_state_hash`, `ledger_version_before` and `ledger_committed`.

## Reference Implementation

`src/arcana/ledger.py` provides `ReferenceAdmissionLedger`, an in-memory,
thread-safe implementation with `current()`, `admit_fastgate()` and
`admit_decision()`. Integrations implement the same invariants on a durable
store, for example a row holding version and state hash updated with a
conditional write.

## Limits

- The ledger serializes admissions; it does not decide which concurrent
  request should win. The first committed request wins and the others must
  re-evaluate on the new state.
- Resource counters (external requests, memory writes, output bytes) are
  still checked per request; debiting them across requests remains an
  integration responsibility.
- The committed matrix is only as complete as the graph the integrator
  builds. Unmodeled edges are outside this contract.

## Verification

`tests/test_ledger_contract.py` covers the split-cycle counterexample, sixteen
concurrent admissions from one baseline (exactly one commits), stale and
mismatched baselines, commit-only-on-allow and malformed versions.
