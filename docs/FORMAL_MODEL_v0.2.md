# ARCANA Formal Model v0.2

> Status: public formal model v0.2 implemented reference contract
> Scope: mathematical contract for public ARCANA reference work
> Implementation status: implemented by the public reference evaluator, matrix, artifact, and FastGate modules; not a production approval

This document defines the public ARCANA model contract for graph state, propagation risk, loss, uncertainty, decision horizons, admission rules, and FastGate assumptions.

ARCANA is model-bounded autonomy accounting. This document does not assert universal safety, production readiness, or enforcement authority.

## 1. Design Requirements

The formal model must satisfy these requirements:

- propagation risk and loss are separate;
- every risk value has an explicit decision horizon;
- every decision has a risk model version;
- every decision has a calibration profile;
- admission-like decisions use upper bounds;
- missing, stale, malformed, or incompatible input fails through specific reason codes;
- weak calibration cannot produce certifiable output;
- FastGate cannot allow silently when its assumptions fail.

## 2. Primitive Sets

An agentic system at time `t` is represented as:

```text
G_t = (V_t, E_t)
```

where:

```text
V_t = A_t union T_t union M_t union H_t union Gt_t union O_t union D_t union X_t
```

Public node classes:

```text
A  = agents
T  = tools or APIs
M  = memory or knowledge stores
H  = human or policy gates
Gt = grants or capability envelopes
O  = operations or plans
D  = distilled or repeated operations
X  = external systems
```

`Gt` is used for grant-like model objects to avoid collision with graph `G_t`.

An edge is:

```text
e = (source, target, edge_type, factors, evidence)
```

Each edge describes a possible unsafe propagation path from `source` to `target` over a declared decision horizon.

## 3. Decision Horizon

A decision horizon is:

```text
H = (horizon_id, duration_seconds, context)
```

`H` defines the time or context window over which edge weights are normalized.

All of the following must use compatible horizons:

- graph edge weights;
- calibration profile;
- risk context;
- certificate-like artifact;
- proposed graph delta.

If horizons are missing or incompatible, ARCANA returns:

```text
ARCANA_DENY_DECISION_HORIZON_MISMATCH
```

Without `H`, `K` is dimensionally ambiguous and cannot be interpreted.

## 4. Edge Weight Model

For an edge `e` over horizon `H`, ARCANA models unsafe propagation weight as:

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

All factors must be declared or derived by a calibration profile.

Expected factor domains:

```text
activation_e(H)          >= 0
p_unsafe_e(H)            in [0, 1]
exposure_e(H)            in [0, 1]
capability_e(H)          in [0, 1]
scope_e(H)               in [0, 1]
detectability_e(H)       in [0, 1]
gate_effectiveness_e(H)  in [0, 1]
reversibility_e(H)       in [0, 1]
```

`activation_e(H)` is normalized to horizon `H`. It can exceed `1` only when the model intentionally represents expected repeated unsafe transition pressure over the horizon. The resulting `w_e(H)` is dimensionless and horizon-bound.

`w_e(H)` must not contain monetary loss, business impact, impact severity, or tail-loss values.

Unknown factors use conservative defaults:

```text
unknown risk factor     -> conservative upper bound
unknown control factor  -> conservative lower bound
```

## 5. Propagation Matrix `K`

Let `n = |V_t|`. The propagation matrix is:

```text
K(H) in R_nonnegative^(n x n)
```

For nodes `i` and `j`:

```text
K_ij(H) = sum w_e(H) for all edges e where source(e) = i and target(e) = j
```

Matrix requirements:

- `K` is square;
- `K` is nonnegative;
- row and column order are explicit and consistent across the matrix interval;
- the matrix graph hash matches the request graph hash;
- all weights are normalized to the same compatible horizon;
- `K` contains propagation risk only.

If the model input is malformed, not square, negative, unbound to graph state, or missing required values, ARCANA returns:

```text
ARCANA_DENY_MODEL_INPUT_INVALID
```

The public evaluator validates declared node ordering and graph-hash equality.
The producer remains responsible for computing the graph hash from a declared
canonical graph representation; a well-formed hash string alone does not prove
that omitted topology is absent.

## 6. Uncertainty Bounds

ARCANA tracks uncertainty as interval matrices:

```text
K_lower(H), K_mean(H), K_upper(H)
```

Required invariants:

```text
0 <= K_lower_ij <= K_mean_ij <= K_upper_ij
```

for every `i, j`.

Admission-like decisions use `K_upper`, not `K_mean`.

Sparse evidence should widen intervals. Weak controls should lower assumed control effectiveness. A lack of observed incidents cannot collapse uncertainty by itself.

## 7. Spectral Propagation Risk

For a nonnegative matrix `K`, define:

```text
rho(K) = spectral_radius(K)
```

ARCANA decision metrics are:

```text
rho_lower = rho(K_lower)
rho_mean  = rho(K_mean)
rho_upper = rho(K_upper)
```

For admission-like decisions:

```text
rho_decision = rho_upper
```

The public subcritical-under-model condition is:

```text
0 <= theta_rho <= 1
rho_upper < theta_rho
```

where `theta_rho` is the declared public threshold for the decision context.

`theta_rho` must not be reused across incompatible horizons, graph scopes, model
versions, or calibration profiles. Public allow-like, subcritical-under-model,
and certificate-like bounded-autonomy artifacts must not use `theta_rho > 1`.

## 8. Subcritical Interpretation

If:

```text
rho(K_upper) < 1
```

then the nonnegative propagation model is subcritical under the declared assumptions.

If a stricter operational threshold is used:

```text
theta_rho <= 1
```

then ARCANA enforces:

```text
rho(K_upper) < theta_rho
```

The phrase subcritical under model means only that the declared ARCANA model, calibration profile, horizon, uncertainty bounds, and thresholds are satisfied.

## 9. Loss Model `L`

Loss is modeled separately from propagation.

```text
L = distribution or bounded random variable over impact
```

Public impact categories can include:

- operational impact;
- financial impact;
- privacy impact;
- compliance impact;
- safety impact;
- reputational impact.

`L` must not be embedded inside `K`.

If loss is in scope and the loss model is missing, malformed, incompatible with the horizon, or unsupported, ARCANA returns:

```text
ARCANA_DENY_LOSS_MODEL_INVALID
```

## 10. Loss Bounds

For confidence level `alpha`, ARCANA defines:

```text
AaR_alpha = quantile_alpha(L)
AES_alpha = expected tail loss beyond AaR_alpha
```

Public v0.2 examples use:

```text
AaR_99_upper
AES_99_upper
```

Admission-like decisions compare upper loss bounds against declared limits:

```text
AaR_99_upper <= max_allowed_AaR_99
AES_99_upper <= max_allowed_AES_99
```

If upper loss bounds exceed limits, ARCANA returns:

```text
ARCANA_DENY_AAR_UPPER_BOUND
ARCANA_DENY_AES_UPPER_BOUND
```

depending on which constraint is violated.

## 11. Decision Input Contract

An ARCANA decision requires:

- risk model version;
- calibration profile;
- decision horizon;
- graph hash;
- graph state or graph delta;
- `K_lower`, `K_mean`, `K_upper` or sufficient calibrated inputs to derive them;
- loss model or explicit declaration that loss is out of scope;
- calibration evidence-source declaration for evaluator use;
- evidence source and evidence hash before any exported artifact is treated as
  admission-capable;
- requested verdict mode;
- applicable thresholds and budget.

Missing or invalid inputs must not fall through to the happy path.

## 12. Ordered Decision Rule

ARCANA evaluates a proposed action in this order:

1. Validate risk model version.
2. Validate model input shape and required values.
3. Validate decision horizon compatibility.
4. Validate context freshness if a prior context is reused.
5. Validate graph hash binding.
6. Validate calibration profile and required calibration level.
7. Validate propagation matrix invariants.
8. Validate loss model if loss is in scope.
9. Validate autonomy budget.
10. Evaluate `rho_upper`.
11. Evaluate loss upper bounds if loss is in scope.
12. Evaluate FastGate if the warm path is used.
13. Return verdict and reason codes.

Failure mapping:

| Condition | Reason code |
| --- | --- |
| missing, unknown, disabled, or incompatible risk model version | `ARCANA_DENY_RISK_MODEL_UNSUPPORTED` |
| malformed graph, matrix, interval, threshold, or required model input | `ARCANA_DENY_MODEL_INPUT_INVALID` |
| missing or incompatible decision horizon | `ARCANA_DENY_DECISION_HORIZON_MISMATCH` |
| expired or stale context | `ARCANA_DENY_CONTEXT_STALE` |
| graph hash mismatch | `ARCANA_DENY_GRAPH_HASH_MISMATCH` |
| insufficient calibration level or evidence quality | `ARCANA_DENY_CALIBRATION_INSUFFICIENT` |
| invalid or unsupported loss model when loss is in scope | `ARCANA_DENY_LOSS_MODEL_INVALID` |
| exhausted autonomy budget | `ARCANA_DENY_BUDGET_EXHAUSTED` |
| `rho_upper` exceeds threshold | `ARCANA_DENY_RHO_UPPER_BOUND` |
| `AaR_upper` exceeds limit | `ARCANA_DENY_AAR_UPPER_BOUND` |
| `AES_upper` exceeds limit | `ARCANA_DENY_AES_UPPER_BOUND` |
| FastGate cannot prove admission | `ARCANA_DENY_FASTGATE_UNCERTAIN` |
| FastGate positive-vector method is invalid | `ARCANA_DENY_FASTGATE_VECTOR_INVALID` |

Success or constrained outcomes:

| Condition | Verdict | Reason code |
| --- | --- | --- |
| all constraints satisfied without extra controls | `allow_bounded_autonomy` | `ARCANA_ALLOW_BOUNDED_AUTONOMY` |
| constraints satisfied only with explicit controls | `allow_with_controls` | `ARCANA_ALLOW_WITH_CONTROLS` |
| human or policy approval is required | `require_human_gate` | `ARCANA_REQUIRE_HUMAN_GATE` |
| narrower scope is required | `require_scope_reduction` | `ARCANA_REQUIRE_SCOPE_REDUCTION` |
| result is evaluative but not certifiable for admission | `observe_only` | `ARCANA_REQUIRE_OBSERVE_ONLY` |

## 13. FastGate Contract

FastGate evaluates sparse graph changes without full recompute on every action.

Let:

```text
K_after_upper = K_before_upper + DeltaK_upper
```

where `DeltaK_upper` is the upper-bound sparse change induced by the proposed action.

FastGate may use the Collatz-Wielandt upper bound for a nonnegative matrix `A` and positive vector `x`:

```text
rho(A) <= max_i ((A x)_i / x_i)
```

Requirements:

- `A` must be nonnegative;
- `x_i > 0` for every component used in the bound;
- reducible graphs must use SCC decomposition, epsilon floor, component-local gate, or exact recompute;
- the positive-vector method must be declared;
- the sparse delta hash must match domain-separated canonical delta content;
- admission-capable FastGate paths require a current evidence hash;
- the computed bound must be compared against `theta_rho`;
- uncertainty in the fast path must not allow.

If the positive-vector method is invalid:

```text
ARCANA_DENY_FASTGATE_VECTOR_INVALID
```

If FastGate cannot prove the upper bound conservatively:

```text
ARCANA_DENY_FASTGATE_UNCERTAIN
```

FastGate is an optimization path, not a weaker decision rule.

## 14. Certificate Conditions

A bounded autonomy certificate-like artifact can be emitted only if it includes:

- risk model version;
- calibration profile;
- decision horizon;
- graph hash or evidence hash;
- `rho_lower`, `rho_mean`, `rho_upper`, and threshold;
- loss bounds when loss is in scope;
- verdict;
- reason codes;
- caveats.

A0/demo output must include:

```text
certification_status = non_certifiable
ARCANA_INFO_A0_NON_CERTIFIABLE
```

## 15. K/L Separation Examples

Allowed in `K`:

```text
unsafe transition probability
activation pressure over H
control effectiveness as a propagation dampener
scope as propagation multiplier
detectability as propagation dampener
reversibility as propagation dampener
```

Not allowed in `K`:

```text
money at risk
business criticality
legal severity
reputation impact
tail-loss estimates
customer-specific impact values
```

Those values belong in `L` and loss-bound metrics.

## 16. Dimensional Checks

Before computing `rho(K)`, ARCANA must validate:

- matrix is square;
- all entries are numeric and nonnegative;
- all edge weights use compatible `H`;
- node ordering is bound to graph hash;
- intervals satisfy `lower <= mean <= upper`;
- public `rho` thresholds are in the subcritical interval `[0, 1]`;
- loss is not embedded in propagation weights.

Violations return:

```text
ARCANA_DENY_MODEL_INPUT_INVALID
```

unless the violation is specifically a horizon mismatch, graph mismatch, stale context, or unsupported model version.

## 17. Implementation Conformance

The public reference implementation applies this model in the following order:

1. typed graph and horizon structures;
2. matrix validation;
3. interval validation;
4. risk model version validation;
5. calibration profile validation;
6. exact spectral calculation for cold path;
7. upper-bound decision evaluator;
8. loss-bound validation;
9. FastGate after exact path tests pass;
10. certificate generation after schema tests pass.

No wildcard branch may silently convert unknown failures into allow-like outcomes.

## 18. v0.2 Decisions and Residual Questions

- `theta_rho` is required in public v0.2 risk contexts and certificate-like
  artifacts.
- `activation_e(H)` may exceed `1` only when repeated transition pressure is
  intentional, horizon-bound, and disclosed; the reference matrix API therefore
  accepts nonnegative values above `1`.
- Public v0.2 accepts reviewed `AaR_99_upper` and `AES_99_upper` bounds; it does
  not estimate a loss distribution and therefore does not choose a strict or
  inclusive empirical tail convention.
- FastGate has no implicit positive-vector default. The method is explicit and
  exact recompute is the conservative fallback.
- Canonical graph-payload hashing remains a producer/integration contract;
  future public versions may add a standalone canonical graph schema.

## 19. Current Artifact Relationship

This model is implemented jointly by:

```text
src/arcana/matrices.py
src/arcana/decision.py
src/arcana/fastgate.py
src/arcana/artifacts.py
tests/test_matrix_validation.py
tests/test_decision_reason_codes.py
tests/test_fastgate.py
```
