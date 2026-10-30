# Loss Contract v1

Status: local unreleased reference candidate (R3.4, finding C05), 2026-10-30.
Contract identifier: `arcana.loss.v1`.
Implementation: `src/arcana/loss_contract.py`; schema `schemas/ARCANA_Loss.schema.v1.json`.

The legacy `LossBounds` input is four caller-declared numbers with no unit,
horizon, source or method. This contract binds AaR_99 and AES_99 upper bounds to
the evaluation that uses them and adds one reference estimator whose premises
are stated. It does not establish that real losses satisfy those premises.

## Conventions

```text
q_u(L)  = inf { z : P(L <= z) >= u }
AaR_99  = q_alpha(L)
AES_99  = integral from alpha to 1 of q_u(L) du / (1 - alpha)
alpha   = 99/100 exactly
```

The quantile-integral form handles atoms and ties. The reference supports
`alpha = 0.99` only (`loss_alpha_unsupported`) and the convention label
`lower_quantile_integral` only.

## Contract

| Field | Meaning |
| --- | --- |
| `risk_model_version`, `calibration_profile_id`, `decision_horizon` | must equal the evaluation's; mismatches deny with the risk-model, calibration or horizon reason code |
| `unit` | loss unit; must equal the policy unit |
| `method` | `declared_upper_bounds` or `dkw_empirical_upper` |
| `failure_probability_upper` | probability that the bounds fail; must not exceed the policy budget |
| `evidence_hash`, `evidence_source_id`, `source_kind` | evidence binding; hash and source must equal the policy's; `source_kind` is `synthetic_fixture` or `external_unverified` |
| `valid_from`, `expires_at` | evidence validity; must cover the whole decision horizon |
| `aar_99_upper`, `aes_99_upper` | declared method only; `aes >= aar` |
| `sample`, `support_upper` | estimator only: 1 to 100000 losses in `[0, support_upper]` |
| `binding_hash` | SHA-256 of the canonical content, binary64 values as hex |

The budget carries a `LossPolicy`: `unit`, `max_allowed_aar_99`,
`max_allowed_aes_99`, `max_failure_probability`, `evidence_hash`,
`evidence_source_id` and `require_empirical_qualification`. Limits and the
accepted evidence live in the policy, so the request cannot pick its own
sample; estimates live in the contract.

## Methods

`declared_upper_bounds`: the supplier states the bounds and their failure
probability. ARCANA checks domains, the AES >= AaR normal form and the bindings,
not the values.

`dkw_empirical_upper` (reference estimator): premises are `n` independent losses
from the loss law of the bound horizon, supported in `[0, B]`. With

```text
eps = sqrt(ln(2 / delta) / (2 n))      (rounded up, capped at 1)
```

the Dvoretzky-Kiefer-Wolfowitz-Massart inequality gives
`P(sup |F_n - F| > eps) <= delta`. Off that event `F >= F_n - eps`, so the law
obtained by moving mass `eps` from the lowest observations to `B` dominates the
true law stochastically. Its AaR_99 and AES_99 therefore bound the true values
together, with failure probability at most `delta`. All arithmetic is exact
over the binary64 inputs; `eps` is inflated by a relative `2^-40` to dominate
the rounding of `log`, division and `sqrt`; the results are rounded up. Only
atoms at or above the 99% level enter the tail sum, and the last four estimates
are memoized by contract content (about 0.5 s for 100000 losses on a laptop).

The bound is informative only when `eps < 1 - alpha`, that is
`n > ln(2 / delta) / (2 * 0.01^2)`, about 18,445 losses for `delta = 0.05`.
Smaller samples return `B` for both metrics. That is valid and deliberately
uninformative.

## Evaluation

| Situation | Outcome |
| --- | --- |
| loss in scope, contract bound | bounds computed, compared with the policy limits (`aar_upper_bound_exceeded`, `aes_upper_bound_exceeded`) |
| loss in scope, legacy `loss_bounds` only | legacy checks; admission gap `loss_contract_missing` (`observe_only`) |
| policy present, loss in scope, no contract | deny `loss_contract_missing` |
| contract without policy, contract with `loss_in_scope = false`, contract plus `loss_bounds` | deny `loss_policy_missing`, `loss_contract_out_of_scope`, `loss_scalar_override_forbidden` |
| evidence other than the policy's | deny `loss_evidence_hash_mismatch`, `loss_evidence_source_mismatch` |
| failure probability above budget, empirical qualification required | deny `loss_failure_budget_exceeded`, `loss_empirical_review_required` |
| evidence window | deny `loss_not_yet_valid`, `loss_expired`, `loss_horizon_not_covered` (`ARCANA_DENY_CONTEXT_STALE`) |

Binding failures are checked with the other contract bindings, before any
spectral check. Results report `loss_contract_version`, `loss_binding_hash`,
`loss_policy_hash`, `loss_method`, `loss_unit`, `loss_source_kind`,
`loss_failure_probability_upper`, the upper bounds and, for the estimator,
`loss_sample_size`, `loss_dkw_epsilon` and the plug-in values. Context and
certificate v0.2 artifacts cannot carry a loss policy
(`legacy_artifact_loss_policy_unsupported`).

## Limits

- Independence, stationarity over the horizon and the support bound are
  declared premises. The estimator cannot detect dependent or drifting losses.
- No source kind satisfies empirical qualification yet, as for coverage.
- Loss failure probability is reported, not composed with coverage or
  calibration failure probabilities.
- Reversibility and other consequence modifiers belong to the loss law that
  produced the sample or the declared bounds (Edge Weight Contract v1).
- FastGate cache bindings do not bind the loss contract yet.
- `loss_in_scope` must be a boolean; truthy non-boolean values are now rejected
  as invalid input, as for the other request flags.

## Verification

`tests/test_loss_contract.py` checks the tail metrics against the independent
Acerbi-Tasche formula on 500 random discrete laws and on atom and tie edge
cases, `eps` against an 80-digit oracle, ordering, support cap, monotonicity in
confidence and in the sample, translation equivariance, coverage of a known law
in repeated draws, contract and policy validation, round trip, tamper detection,
the public example, and every binding failure on the main evaluator and FastGate.
