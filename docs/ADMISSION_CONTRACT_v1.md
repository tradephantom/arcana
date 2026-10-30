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
   budget's temporal policy, and its initial state is nonzero. Finite-horizon
   peak and cumulative activations are therefore limited.
3. On FastGate, a calibration profile is supplied. It must match the declared
   profile id, calibration level, risk model version and decision horizon, and
   pass the main evaluator's evidence freshness rule.

Otherwise the verdict is `observe_only` with `ARCANA_REQUIRE_OBSERVE_ONLY`,
issue code `admission_contracts_missing`, and the metric
`admission_contract_gaps` naming what is missing:

| Gap | Meaning |
| --- | --- |
| `increment_contract_missing` | no bound increment contract |
| `temporal_contract_missing` | no bound and evaluated temporal contract |
| `temporal_initial_state_zero` | the temporal contract seeds no activation, so it bounds nothing |
| `calibration_profile_missing` | FastGate request without a calibration profile |

Every result produced by the shared tail also reports
`admission_contract_policy = arcana.admission.v1`.

## Rationale

- The spectral radius of an acyclic propagation matrix is zero for any edge
  weights, so a single high-weight action could be admitted on `rho_upper`
  alone. The temporal contract charges the cascade that the action seeds.
- A caller-declared spectral increment could avoid the increment budget.
- FastGate accepted a self-declared calibration level and did not check the
  supported risk model versions.

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
| `calibration_profile` | Optional; absence only blocks admission. Mismatches deny with `fastgate_calibration_profile_id_mismatch`, `fastgate_calibration_level_mismatch`, `fastgate_calibration_risk_model_mismatch` or `fastgate_calibration_horizon_mismatch`; stale evidence uses the main evaluator issue codes. |
| `required_controls`, `available_controls`, `human_gate_required`, `scope_reduction_required` | Same semantics as the main evaluator. |

## Limits

- Contracts bind declared premises; they do not prove them. The operator
  family and initial state must come from the integrator's calibrated graph,
  not from the agent under evaluation.
- Budgets remain per request. Composition across concurrent requests evaluated
  against the same baseline needs a committed graph version in the integration.
- The coverage contract remains optional.
- The public reason-code registry is unchanged; only issue codes are added.

## Compatibility

Legacy requests whose checks all pass now return `observe_only` instead of an
allow-like verdict. Deny and require outcomes are unchanged. Package version
`0.2.0.dev0` identifies this unreleased development line.

## Verification

`tests/test_admission_contract.py` covers the rule, the shared tail, the
FastGate profile binding and the external audit reproducers for an acyclic
high-weight action, each half of a split cycle, a caller-declared increment
and an unsupported FastGate risk model version.
