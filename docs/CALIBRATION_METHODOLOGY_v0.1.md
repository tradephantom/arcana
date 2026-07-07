# ARCANA Calibration Methodology v0.1

> Status: public calibration methodology v0.1 draft
> Scope: public calibration contract for ARCANA reference work
> Implementation status: no calibration loader or certificate generator is approved by this document

This document defines how public ARCANA calibration profiles should derive edge-weight factors, uncertainty intervals, evidence quality, calibration levels, temporal validity, and certification status.

ARCANA calibration is not proof of safety. It is a declared method for converting evidence and assumptions into model-bounded uncertainty bounds.

## 1. Design Requirements

ARCANA calibration must satisfy these requirements:

- every profile is bound to one risk model version;
- every profile is bound to one decision horizon;
- every profile declares evidence sources and evidence quality;
- every derived value can be traced to an assumption or evidence class;
- unknown risk factors use conservative upper bounds;
- unknown control factors use conservative lower bounds;
- sparse evidence widens uncertainty;
- temporal staleness weakens evidence;
- A0 output is always non-certifiable;
- calibration insufficiency returns a specific reason code.

## 2. Calibration Profile Contract

A calibration profile is:

```text
C = (
  profile_id,
  risk_model_version,
  level,
  decision_horizon,
  source,
  evidence_window,
  confidence,
  uncertainty_policy,
  edge_weight_policy,
  certification_status,
  caveats
)
```

Minimum public machine-readable fields are defined by:

```text
schemas/ARCANA_CalibrationProfile.schema.v0.2.json
```

A calibration profile is valid only for the declared:

- risk model version;
- graph scope or benchmark scenario class;
- decision horizon;
- evidence window;
- source classes;
- uncertainty policy;
- caveats.

A profile must not be reused across incompatible horizons, graph scopes, model versions, policy regimes, tool versions, or evidence classes.

The public `evidence_window` shape is:

```text
evidence_window = (
  observed_after,
  observed_before,
  max_age_seconds
)
```

`observed_after` and `observed_before` bound the evidence collection interval. `max_age_seconds` bounds how old the evidence may be before the profile becomes stale for a decision.

## 3. Calibration Levels

ARCANA uses four public calibration levels.

| Level | Name | Public use | Certification status |
| --- | --- | --- | --- |
| A0 | Heuristic / Demo Only | Synthetic examples, tutorials, paper illustrations. | Always `non_certifiable`. |
| A1 | Static Conservative Prior | Conservative offline estimates from declared static factors. | Public v0.2 default is `non_certifiable`; no certificate-like artifact support. |
| A2 | Empirical / Red-Team Calibration | Controlled adversarial evidence, scenario replay, benchmark evidence. | May be `certifiable_under_profile` only when reviewed coverage, segmentation, freshness, and non-synthetic evidence requirements pass. |
| A3 | Runtime Bayesian Calibration | Segmented runtime distributions with decay, priors, and controlled evidence separation. | May be `certifiable_under_profile` only when runtime evidence is reviewed, calibrated, segmented, fresh, and auditable. |

Level ordering is:

```text
A0 < A1 < A2 < A3
```

If a requested decision requires a stronger level than the supplied profile, ARCANA returns:

```text
ARCANA_DENY_CALIBRATION_INSUFFICIENT
```

or, when policy permits evaluation but not admission:

```text
ARCANA_REQUIRE_OBSERVE_ONLY
```

## 4. A0 - Heuristic / Demo Only

A0 is allowed for:

- synthetic schema examples;
- local demos;
- tutorials;
- paper figures;
- non-operational benchmark fixtures.

A0 is not allowed for:

- production admission;
- commercial certificate issuance;
- high-impact autonomy grants;
- distillation eligibility;
- claims that bounded autonomy has been certified for a real system.

A0 must include:

```text
certification_status = non_certifiable
ARCANA_INFO_A0_NON_CERTIFIABLE
```

A0 profiles can use simple deterministic factors, but every output must remain visibly non-certifiable.

## 5. A1 - Static Conservative Prior

A1 uses documented static assumptions rather than empirical event distributions.

Allowed evidence classes:

- capability family;
- data class;
- execution mode;
- scope width;
- reversibility class;
- detectability class;
- human or policy gate presence;
- public benchmark prior;
- documented synthetic assumption.

A1 requirements:

- every factor has a declared assumption;
- every assumption has a conservative direction;
- risk factors use upper-bound estimates;
- control factors use lower-bound estimates;
- evidence gaps are listed in caveats;
- sparse or ambiguous inputs widen intervals;
- `confidence` remains below empirical levels unless reviewed.

A1 is not empirical proof. It is a conservative static prior suitable for early reference calculations and low-impact public examples.

In the public v0.2 contract, A1 can support bounded reference risk contexts
when all other constraints pass, but A1 remains `non_certifiable` and cannot
support non-demo certificate-like artifacts.

## 6. A2 - Empirical / Red-Team Calibration

A2 uses controlled evidence gathered from repeatable tests.

Allowed evidence classes:

- adversarial prompt-injection test;
- memory-poisoning replay;
- tool-misuse test;
- delegation-cascade test;
- benchmark-gaming test;
- dynamic execution risk test;
- fail-closed test;
- public benchmark scenario run.

A2 requirements:

- evidence IDs are recorded;
- sample sizes are recorded;
- test coverage is recorded;
- pass/fail and near-miss outcomes are separated;
- model, tool, policy, and environment versions are segmented;
- known gaps are recorded;
- stale evidence is decayed or rejected;
- passive absence of incidents is not treated as sufficient evidence.

A2 may support certifiable-under-profile output only when evidence coverage is relevant to the requested decision scope and horizon.

## 7. A3 - Runtime Bayesian Calibration

A3 uses maintained distributions rather than static point estimates.

A3 requirements:

- priors are documented;
- posterior update rules are documented;
- evidence is segmented by model, tool, policy, environment, and horizon;
- red-team evidence and passive runtime observation are not pooled without a declared model;
- correlated events are handled explicitly;
- temporal decay is applied;
- sparse segments retain conservative upper bounds;
- no-incident windows reduce uncertainty only through a declared statistical model;
- runtime telemetry is auditable without exposing private source data in public artifacts.

Public ARCANA may document the A3 contract, but public examples must use synthetic or public-source-safe evidence only.

## 8. Evidence Source Classes

Public calibration profiles may declare these source classes:

| Source | Description | Minimum level |
| --- | --- | --- |
| `synthetic_demo` | Synthetic values for examples or tutorials. | A0 |
| `static_conservative_prior` | Conservative static assumptions. | A1 |
| `controlled_redteam` | Controlled adversarial tests. | A2 |
| `adversarial_replay` | Replay of known scenario classes. | A2 |
| `public_benchmark` | Public ARCANA-Bench or public-source-safe benchmark evidence. | A2 |
| `runtime_observation` | Runtime observations handled through documented priors and segmentation. | A3 |

Evidence source labels must not expose private customer, enterprise, adapter, or lab mechanics.

## 9. Evidence Quality

ARCANA evaluates evidence quality along these dimensions:

| Dimension | Required question |
| --- | --- |
| relevance | Does the evidence match the requested graph scope and action class? |
| coverage | Which edge types, tools, memories, gates, and operations were tested? |
| sample size | How many independent trials or observations support the estimate? |
| severity coverage | Were high-impact and tail-risk cases included when loss is in scope? |
| adversarial strength | Were adaptive or adversarial attempts represented? |
| segmentation | Are model, tool, policy, environment, and horizon versions separated? |
| freshness | Is the evidence inside the permitted update window? |
| independence | Are repeated events independent enough for the claimed confidence? |
| observability | Could unsafe transitions have been detected by the evidence process? |
| reproducibility | Can a reviewer reproduce or audit the evidence class? |

Evidence quality is insufficient when the requested action depends on untested or stale factors whose conservative bounds exceed the allowed envelope.

## 10. Edge Factor Calibration

The formal model defines:

```text
w_e(H) =
  activation_e(H)
  * p_unsafe_e(H)
  * exposure_e(H)
  * capability_e(H)
  * scope_e(H)
  * (1 - detectability_e(H))
  * (1 - gate_effectiveness_e(H))
  * (1 - reversibility_e(H))
```

Calibration assigns lower, mean, and upper bounds to each factor.

Risk-amplifying factors:

```text
activation
p_unsafe
exposure
capability
scope
```

Control-like factors:

```text
detectability
gate_effectiveness
reversibility
```

Unknown risk-amplifying factors must use conservative upper bounds.

Unknown control-like factors must use conservative lower bounds.

The calibrated edge interval is:

```text
w_lower_e(H), w_mean_e(H), w_upper_e(H)
```

with:

```text
0 <= w_lower_e(H) <= w_mean_e(H) <= w_upper_e(H)
```

Invalid intervals return:

```text
ARCANA_DENY_MODEL_INPUT_INVALID
```

Insufficient evidence quality returns:

```text
ARCANA_DENY_CALIBRATION_INSUFFICIENT
```

## 11. Uncertainty Policy

ARCANA stores uncertainty as intervals.

For propagation:

```text
K_lower(H), K_mean(H), K_upper(H)
```

For scalar metrics:

```text
rho_lower <= rho_mean <= rho_upper
```

For loss when in scope:

```text
AaR_upper
AES_upper
```

Rules:

- admission-like decisions use upper bounds;
- `rho_mean` can support analysis but not admission;
- sparse evidence widens intervals;
- weak control evidence lowers control estimates;
- stale evidence widens intervals or invalidates the profile;
- conflicting evidence widens intervals unless resolved by segmentation;
- unknown means risky.

## 12. Sparse-Evidence Fallback

If evidence is sparse but a profile is still evaluable, ARCANA must widen the interval instead of using a confident point estimate.

Minimum fallback behavior:

```text
risk_upper   -> increase toward conservative bound
risk_lower   -> stay low unless directly supported
control_upper -> do not increase without evidence
control_lower -> decrease toward conservative bound
confidence   -> decrease
caveats      -> include sparse-evidence note
```

If widened upper bounds breach the allowed threshold, the decision must deny or reduce scope.

If the profile cannot support the requested action class, ARCANA returns:

```text
ARCANA_DENY_CALIBRATION_INSUFFICIENT
```

## 13. Temporal Decay

Evidence weakens with time unless the profile declares that the underlying system has not materially changed and the evidence window remains valid.

Let:

```text
age_seconds = decision_time - evidence_observed_at
```

A public reference method may apply exponential decay:

```text
effective_weight = raw_weight * exp(-lambda * age_seconds)
```

where `lambda` is declared by the profile or benchmark method.

Decay effects:

- stale positive control evidence becomes less trusted;
- stale risk evidence remains relevant unless superseded;
- stale no-incident evidence loses force quickly;
- stale adversarial success remains a risk signal until remediated and retested.

If the profile or context is outside its freshness window, ARCANA returns:

```text
ARCANA_DENY_CONTEXT_STALE
```

## 14. Segmentation Rules

Evidence must be segmented when any of these change materially:

- risk model version;
- decision horizon;
- model family or version;
- tool or API class;
- memory class;
- gate class;
- policy regime;
- environment class;
- graph scope;
- action class;
- benchmark scenario class.

Pooling across segments requires a declared method and a caveat. Otherwise, ARCANA must select the most conservative applicable segment or return insufficient calibration.

## 15. Loss Calibration

Loss calibration is separate from propagation calibration.

Loss calibration may estimate:

```text
AaR_99_upper
AES_99_upper
```

Loss evidence must identify:

- impact category;
- unit or scoring basis;
- horizon;
- upper-bound method;
- exclusions;
- caveats.

If loss is in scope but the loss model is missing, malformed, unsupported, or horizon-incompatible, ARCANA returns:

```text
ARCANA_DENY_LOSS_MODEL_INVALID
```

Loss values must not be embedded into `K`.

## 16. Certification Status

Allowed public certification statuses:

```text
non_certifiable
certifiable_under_profile
```

`non_certifiable` is required when:

- calibration level is A0;
- calibration level is A1 in the public v0.2 contract;
- evidence is synthetic-only;
- requested output is observe-only;
- required evidence source is missing;
- profile is stale;
- evidence cannot support the requested impact class;
- caveats invalidate admission use.

`certifiable_under_profile` may be used only when:

- calibration level is A2 or A3;
- calibration level is sufficient for the requested action;
- evidence is not synthetic-only;
- risk model version is supported;
- decision horizon is compatible;
- evidence quality passes;
- graph and evidence bindings pass;
- upper-bound propagation and loss constraints pass;
- required controls are satisfiable;
- caveats do not block admission use.

This status remains model-bounded. It does not assert absolute safety,
commercial certificate issuance, production enforcement, customer approval, or
operational authorization.

## 17. Minimum Required Level by Use

Default public minimums:

| Use | Minimum level | Default result below minimum |
| --- | --- | --- |
| schema example | A0 | `ARCANA_INFO_A0_NON_CERTIFIABLE` |
| tutorial demo | A0 | `observe_only` |
| low-impact offline reference risk context | A1 | `ARCANA_REQUIRE_OBSERVE_ONLY`; no certificate-like artifact |
| bounded autonomy certificate example beyond demo | A2 | `ARCANA_DENY_CALIBRATION_INSUFFICIENT` |
| high-impact operation admission | A2 | `ARCANA_DENY_CALIBRATION_INSUFFICIENT` |
| runtime adaptive autonomy budget update | A3 | `ARCANA_DENY_CALIBRATION_INSUFFICIENT` |
| distillation eligibility | A2 | `ARCANA_DENY_DISTILLATION_RISK` or `ARCANA_DENY_CALIBRATION_INSUFFICIENT` |

Public v0.1 examples should remain A0 unless an A2 public benchmark fixture is deliberately added later.

## 18. Validation Order

Calibration validation happens before propagation and loss threshold evaluation.

Required order:

1. Validate risk model version.
2. Validate calibration profile schema.
3. Validate profile level.
4. Validate decision horizon compatibility.
5. Validate source classes.
6. Validate evidence freshness.
7. Validate segmentation compatibility.
8. Validate evidence quality for requested use.
9. Derive or validate edge-factor intervals.
10. Derive or validate `K_lower`, `K_mean`, and `K_upper`.
11. Derive or validate loss model if loss is in scope.
12. Apply certification-status rules.

Distinct failures must produce distinct reason codes. Calibration insufficiency must not hide malformed model input, stale context, graph mismatch, or unsupported model version.

## 19. Public Profile Caveats

Every public profile must include caveats.

Required caveat classes:

- evidence limitations;
- horizon limitations;
- graph-scope limitations;
- source-class limitations;
- segmentation limitations;
- certification-status limitations;
- known unsupported uses.

A caveat is binding. If a requested action violates a caveat, the profile is insufficient for that action.

## 20. Reference Implementation Entry Contract

The future reference implementation should implement calibration in this order:

1. typed calibration profile object;
2. schema-level validation;
3. level and certification-status validation;
4. horizon compatibility check;
5. source-class validation;
6. evidence freshness check;
7. segmentation compatibility check;
8. evidence-quality assessment;
9. interval derivation and invariant checks;
10. explicit reason-code branches;
11. tests for A0 non-certifiable behavior;
12. tests for calibration insufficiency.

No implementation should issue a certifiable non-demo artifact before this
methodology, the schemas, and the formal model are reviewed together. Public
v0.2 non-demo certificate-like artifacts require A2 or A3 calibration and
non-synthetic evidence.

## 21. Open Questions

- What public benchmark evidence should define the first A2 profile?
- What default temporal decay parameter should be used for public reference fixtures?
- Should calibration profiles include explicit per-factor intervals in v0.3 schemas?
- Should evidence quality become a separate public schema object?

## 22. Next Artifact

This artifact is followed by FastGate design before reference implementation work.

The next implementation-planning artifact should be:

```text
Public Demo and Reference Implementation Plan v0.1
```
