# Admission Contract v1

Status: local unreleased reference candidate, 2026-10-30.
Policy identifier: `arcana.admission.v1`.

This contract decides when an evaluation may return an allow-like verdict. It
does not change any spectral, loss, budget, increment, temporal or coverage
check. It removes legacy caller-declared accounting from the admission path.
It is not an empirical calibration claim or a production authorization.

## Rule

An evaluation that passes every other check returns `allow_bounded_autonomy`
or `allow_with_controls` only when all of the following hold:

1. An increment contract (`arcana.increment.v1`) is bound under the budget's
   increment scope. The spectral increment is recomputed from bound snapshots;
   a caller-supplied `delta_rho_upper` can never reach admission.
2. A temporal contract (`arcana.temporal.v1`) is bound and evaluated under the
   budget's temporal policy. Its initial state is nonzero and seeds every node
   whose outgoing propagation the bound increment changes, so finite-horizon
   peak and cumulative activations of the action's own cascade are limited.
3. On FastGate, a calibration profile is supplied. It must match the declared
   profile id, calibration level, risk model version and decision horizon, and
   pass the main evaluator's evidence freshness rule.
4. The calibration profile is bound to its evidence by `evidence_hash`
   (`sha256:<64 hex>`), on the main evaluator and on FastGate.

Otherwise the verdict is `observe_only` with `ARCANA_REQUIRE_OBSERVE_ONLY`,
issue code `admission_contracts_missing`, and the metric
`admission_contract_gaps` naming what is missing:

| Gap | Meaning |
| --- | --- |
| `increment_contract_missing` | no bound increment contract |
| `temporal_contract_missing` | no bound and evaluated temporal contract |
| `temporal_initial_state_zero` | the temporal contract seeds no activation, so it bounds nothing |
| `temporal_seed_misses_changed_source` | a node whose outgoing propagation changes has no seed, so its cascade is not charged |
| `calibration_profile_missing` | FastGate request without a calibration profile |
| `calibration_evidence_hash_missing` | the calibration profile is not bound to its evidence by hash |

Every result produced by the shared tail also reports
`admission_contract_policy = arcana.admission.v1`.

## Rationale

- The spectral radius of an acyclic propagation matrix is zero for any edge
  weights, so a single high-weight action could be admitted on `rho_upper`
  alone. The temporal contract charges the cascade that the action seeds.
- A caller-declared spectral increment could avoid the increment budget.
- FastGate accepted a self-declared calibration level and did not check the
  supported risk model versions.

## Calibration Support Checks

These checks deny instead of degrading to `observe_only`, because they show that
the profile cannot support the operator being admitted. They apply to the main
evaluator and, when a profile is supplied, to every FastGate path. A0 profiles
keep returning `observe_only` before either check.

| Check | Rule | Issue code |
| --- | --- | --- |
| Confidence floor | `profile.confidence >= min_calibration_confidence` (request field, default `0.5`, must lie in `(0, 1]`) | `calibration_confidence_below_minimum` |
| Profile-rho coherence, upper | verified `rho_upper` (FastGate: the after-state bound) `<= profile.uncertainty.rho_upper + margin` | `rho_upper_above_calibration_profile` |
| Profile-rho coherence, lower | verified `rho_upper + margin >= profile.uncertainty.rho_lower` | `rho_upper_below_calibration_profile` |

Both deny with `ARCANA_DENY_CALIBRATION_INSUFFICIENT`. The margin is
`max(abs_tolerance, rel_tolerance * profile rho_upper)` from the request's
tolerance policy. An invalid floor denies with `ARCANA_DENY_MODEL_INPUT_INVALID`
(`min_calibration_confidence_invalid`). The confidence check runs right after
the calibration level check; coherence runs after the spectral threshold check,
so a threshold breach keeps `ARCANA_DENY_RHO_UPPER_BOUND`.

The default floor is a policy floor, not a statistical claim: it rejects
profiles that rate their own interval no better than a coin flip, including the
zero-confidence profile of the external audit. Integrators should raise it.
Coherence means the operator under evaluation lies inside the rho interval the
profile was calibrated for. Above it the operator is outside the calibrated
regime; below its lower end the matrices claim less propagation than the
calibration evidence supports, which also catches an acyclic high-weight action
when the profile declares a positive floor.

## Shared Decision Tail

The main evaluator and every FastGate path (Collatz bound, exact recompute,
fallback) apply the same order once risk, loss, budget and temporal checks pass:

1. `scope_reduction_required` gives `require_scope_reduction`;
2. `human_gate_required` gives `require_human_gate`;
3. required controls that are not available give `require_human_gate`;
4. any contract gap gives `observe_only`;
5. required controls that are available give `allow_with_controls`;
6. otherwise `allow_bounded_autonomy`.

## FastGate Request Additions

| Field | Behavior |
| --- | --- |
| `supported_risk_model_versions` | Enforced. An unsupported version denies with `ARCANA_DENY_RISK_MODEL_UNSUPPORTED` (`fastgate_risk_model_version_unsupported`). |
| `min_calibration_confidence` | Same floor and validation as the main evaluator. |
| `calibration_profile` | Optional; absence only blocks admission. Mismatches deny with `fastgate_calibration_profile_id_mismatch`, `fastgate_calibration_level_mismatch`, `fastgate_calibration_risk_model_mismatch` or `fastgate_calibration_horizon_mismatch`; stale evidence uses the main evaluator issue codes. |
| `required_controls`, `available_controls`, `human_gate_required`, `scope_reduction_required` | Same semantics as the main evaluator. |

## Limits

- Contracts bind declared premises; they do not prove them. The operator
  family and initial state must come from the integrator's calibrated graph,
  not from the agent under evaluation.
- Budgets remain per request. Composition across requests evaluated against
  the same baseline is handled by the committed graph state of
  [Ledger Contract v1](LEDGER_CONTRACT_v1.md).
- On the main evaluator the increment `before` snapshot is bound only when the
  request goes through the ledger, which requires it to equal the committed
  graph; a direct `evaluate_decision` call cannot prevent a caller from
  declaring `before` equal to `after`.
- Increment evidence must now cover the whole decision horizon
  (`increment_evidence_horizon_not_covered`), as temporal evidence already did.
- The coverage contract remains optional.
- The profile `evidence_hash` names evidence; ARCANA does not fetch or verify
  that evidence, and the confidence value remains a declared premise.
- The public reason-code registry is unchanged; only issue codes are added.

## Compatibility

Legacy requests whose checks all pass now return `observe_only` instead of an
allow-like verdict. Profiles without `evidence_hash` now also stay
`observe_only`; profiles below the confidence floor or incoherent with the
verified `rho_upper` now deny, and loss bounds with `AES_99_upper <
AaR_99_upper` deny as an invalid loss model. `human_gate_required` and `scope_reduction_required` must be
booleans; other truthy values are rejected as invalid input. Other deny and
require outcomes are unchanged. Package version
`0.2.0.dev0` identifies this unreleased development line.

## Verification

`tests/test_admission_contract.py` covers the rule, the shared tail, the
FastGate profile binding and the external audit reproducers for an acyclic
high-weight action, each half of a split cycle, a caller-declared increment
and an unsupported FastGate risk model version.
`tests/test_calibration_admission.py` covers the confidence floor, profile-rho
coherence, the profile evidence hash and the loss tail order on the main
evaluator, FastGate exact recompute and the FastGate Collatz bound, including
the audit reproducers for a zero-confidence profile and `AES < AaR`.
