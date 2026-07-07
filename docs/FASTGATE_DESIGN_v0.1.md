# ARCANA-FastGate Design v0.1

> Status: public FastGate design v0.1 draft
> Scope: low-latency admission design for public ARCANA reference work
> Implementation status: no FastGate prototype is approved by this document

This document defines the public ARCANA-FastGate design for conservative admission of sparse graph changes without a full spectral recompute on every action.

FastGate is an optimization path. It must preserve the same upper-bound decision semantics as the exact ARCANA evaluator.

## 1. Design Requirements

FastGate must satisfy these requirements:

- use `K_upper`, not `K_mean`, for admission-like decisions;
- accept only nonnegative propagation matrices;
- bind every result to risk model version, calibration profile, decision horizon, graph hash, and evidence;
- validate sparse graph deltas before acting;
- declare the selected FastGate mode;
- declare the positive-vector method when a Collatz bound is used;
- handle reducible graphs explicitly;
- fail closed on invalid vectors, stale context, malformed deltas, or insufficient numerical margin;
- expose exact recompute as the conservative fallback;
- never allow solely because the fast path is unavailable.

## 2. Decision Semantics

The exact ARCANA admission condition remains:

```text
0 <= theta_rho <= 1
rho(K_after_upper) < theta_rho
```

FastGate may allow only when it proves a conservative upper bound:

```text
fastgate_upper_bound >= rho(K_after_upper)
fastgate_upper_bound < theta_rho
```

If FastGate cannot prove both inequalities, it must not return `allow_bounded_autonomy`.

If exact recompute is available, FastGate may delegate to exact recompute. If exact recompute is unavailable and the fast path is inconclusive, ARCANA returns:

```text
ARCANA_DENY_FASTGATE_UNCERTAIN
```

## 3. Public Modes

FastGate has three public modes.

| Mode | Purpose | Allow-like result permitted |
| --- | --- | --- |
| `exact_recompute` | Full recompute of `rho(K_after_upper)`. | Yes, if all exact decision constraints pass. |
| `perron_collatz_bound` | Conservative sparse update bound. | Yes, if the bound proves admission with margin. |
| `observe_only` | Evaluate or explain without admission authority. | No. |

`observe_only` is used for A0/demo outputs, unsupported fast-path assumptions, or non-admission analysis.

## 4. Path Classes

FastGate implementations may expose cold, warm, and hot paths.

### Cold Path

Cold path performs exact recompute:

```text
K_after_upper = K_before_upper + DeltaK_upper
rho_after_upper = rho(K_after_upper)
```

Cold path is required when:

- no valid cache exists;
- sparse delta is too large;
- graph hash binding fails;
- positive-vector method is unavailable;
- reducible graph handling is not declared;
- numerical margin is insufficient;
- warm or hot path assumptions fail.

### Warm Path

Warm path uses a declared positive-vector method and a conservative bound:

```text
fastgate_upper_bound >= rho(K_after_upper)
```

Warm path is allowed only when:

- `K_before_upper` is valid and graph-bound;
- `DeltaK_upper` is sparse, nonnegative, and horizon-compatible;
- the positive vector is strictly positive for every covered component;
- reducible graph handling is valid;
- the bound has enough margin below `theta_rho`;
- the autonomy budget remains available.

### Hot Path

Hot path may reuse a previously validated bound only when all cache keys still match.

Required cache keys:

- risk model version;
- calibration profile ID;
- decision horizon ID and duration;
- graph hash before delta;
- delta hash or canonical delta fingerprint;
- positive-vector method;
- threshold;
- numerical tolerance profile;
- evidence hash or evidence source ID;
- context expiry.

If any cache key mismatches, hot path must fall back to warm or cold path.

Hot path must not issue a new certifiable result from stale context.

## 5. Sparse Perturbation Model

A proposed action induces a graph delta:

```text
DeltaG = (DeltaV, DeltaE, removed_edges, modified_edges)
```

The calibrated upper-bound matrix delta is:

```text
DeltaK_upper(H)
```

The after-state matrix is:

```text
K_after_upper(H) = K_before_upper(H) + DeltaK_upper(H)
```

For public v0.1, FastGate warm path supports additive nonnegative sparse deltas. Removals or risk-reducing changes must be handled by exact recompute unless the reference implementation later defines a reviewed monotone-removal proof.

Sparse delta requirements:

- row and column order match the graph hash;
- every added or modified entry is numeric and nonnegative;
- all entries use the same compatible decision horizon;
- every changed entry is derived from the calibration profile;
- loss values are not embedded in the delta;
- delta hash or canonical fingerprint is available for cache binding.

Malformed deltas return:

```text
ARCANA_DENY_MODEL_INPUT_INVALID
```

## 6. Collatz-Wielandt Bound

For a nonnegative matrix `A` and vector `x` with `x_i > 0`:

```text
rho(A) <= max_i ((A x)_i / x_i)
```

FastGate uses:

```text
A = K_after_upper
fastgate_upper_bound = max_i ((A x)_i / x_i)
```

Admission requires:

```text
fastgate_upper_bound + numeric_margin < theta_rho
```

where `numeric_margin` is declared by the implementation or tolerance profile.

If any `x_i <= 0`, `x_i` is missing, or `x` is not bound to the graph state, ARCANA returns:

```text
ARCANA_DENY_FASTGATE_VECTOR_INVALID
```

## 7. Positive-Vector Methods

Public v0.1 recognizes these positive-vector methods:

| Method | Use | Required validation |
| --- | --- | --- |
| `irreducible_perron_vector` | Matrix is irreducible and a positive Perron vector is available. | Prove or declare irreducibility and validate all vector entries are positive. |
| `scc_decomposition` | Reducible graph is decomposed into strongly connected components. | Validate component ordering and bound each relevant component. |
| `epsilon_floor` | A nonnegative vector is made strictly positive by an epsilon floor. | Validate epsilon is positive, declared, and included in the margin policy. |
| `component_local_gate` | Only affected components and downstream components are gated. | Validate affected component closure and no unbounded cross-component path is ignored. |
| `fallback_exact` | Fast path delegates to exact recompute. | Exact recompute result must be used for the admission decision. |

No wildcard positive-vector method is allowed.

Unknown or incompatible methods return:

```text
ARCANA_DENY_FASTGATE_VECTOR_INVALID
```

The public reference implementation validates `irreducible_perron_vector`
against the after-state nonnegative graph. A caller declaration is not enough:
if the after-state matrix is reducible, this method fails closed and the caller
must use SCC decomposition, epsilon floor, component-local gating, or exact
recompute.

## 8. Reducible Graph Handling

Agentic graphs can be reducible. A reducible graph can contain disconnected regions, one-way dependency chains, or isolated components.

FastGate must use one of these strategies:

1. SCC decomposition.
2. Epsilon floor.
3. Component-local gate.
4. Exact recompute.

### SCC Decomposition

For SCC decomposition, the implementation must:

- compute components from the after-state graph;
- identify components affected by `DeltaK_upper`;
- include downstream components when cross-component propagation can affect the bound;
- compute or bound each relevant component;
- compare every relevant component bound against `theta_rho` or component-local thresholds;
- declare the component method in the risk context or certificate-like artifact.

If component ordering or affected-component closure cannot be validated, return:

```text
ARCANA_DENY_FASTGATE_VECTOR_INVALID
```

### Epsilon Floor

For epsilon floor, the implementation converts a nonnegative vector into a strictly positive vector:

```text
x_i_floor = max(x_i, epsilon)
```

Requirements:

- `epsilon > 0`;
- epsilon is declared;
- the resulting vector is graph-bound;
- numerical margin accounts for the perturbation;
- the method is not used to hide a weak or invalid bound.

If the epsilon floor produces an insufficient margin, return:

```text
ARCANA_DENY_FASTGATE_UNCERTAIN
```

### Component-Local Gate

Component-local gate is allowed only when the implementation can prove that the changed entries affect a closed component set for the decision horizon.

Requirements:

- affected components are identified;
- outgoing propagation from affected components is included or bounded;
- incoming-only components are handled conservatively;
- removed or risk-reducing edges do not justify fast allow;
- component thresholds are declared if they differ from global `theta_rho`.

If closure cannot be proven, fall back to exact recompute or return:

```text
ARCANA_DENY_FASTGATE_UNCERTAIN
```

## 9. Numerical Margin

FastGate decisions require explicit numerical tolerance.

The reference implementation should define:

```text
numeric_margin = max(abs_tolerance, rel_tolerance * theta_rho)
```

Admission through warm path requires:

```text
fastgate_upper_bound + numeric_margin < theta_rho
```

If:

```text
fastgate_upper_bound + numeric_margin >= theta_rho
```

FastGate must use exact recompute if available. If exact recompute is unavailable, return:

```text
ARCANA_DENY_FASTGATE_UNCERTAIN
```

## 10. Budget Handling

FastGate must validate autonomy budget before returning an allow-like result.

Budget checks can include:

- `max_delta_rho_upper`;
- external request count;
- memory write count;
- output byte count;
- budget expiry.

If the action would exceed budget, ARCANA returns:

```text
ARCANA_DENY_BUDGET_EXHAUSTED
```

Budget failure must not be reported as FastGate uncertainty.

## 11. Loss Handling

FastGate gates propagation risk only.

Loss bounds remain separate:

```text
AaR_99_upper
AES_99_upper
```

If loss is in scope, a FastGate allow-like propagation result is insufficient by itself. ARCANA must also validate loss upper bounds.

Loss model failures return:

```text
ARCANA_DENY_LOSS_MODEL_INVALID
```

Loss bound breaches return:

```text
ARCANA_DENY_AAR_UPPER_BOUND
ARCANA_DENY_AES_UPPER_BOUND
```

FastGate must not place loss, impact severity, or monetary values inside `K`.

## 12. Validation Order

FastGate validation happens after model, horizon, graph, calibration, loss-model, and budget preconditions are known enough to evaluate the requested path.

Required order:

1. Validate risk model version.
2. Validate calibration profile and required level.
3. Validate decision horizon compatibility.
4. Validate current context freshness.
5. Validate graph hash binding.
6. Validate `K_before_upper` shape and nonnegativity.
7. Validate `DeltaK_upper` shape, sparsity, nonnegativity, and horizon.
8. Validate budget.
9. Validate loss model if loss is in scope.
10. Select FastGate mode.
11. Validate positive-vector method if warm path is used.
12. Validate reducible graph handling if needed.
13. Compute conservative bound or exact recompute.
14. Apply numerical margin.
15. Return verdict and reason codes.

Each failure must map to its specific reason code. FastGate must not absorb unrelated failures into `ARCANA_DENY_FASTGATE_UNCERTAIN`.

## 13. Reason-Code Mapping

| Condition | Reason code |
| --- | --- |
| unsupported risk model | `ARCANA_DENY_RISK_MODEL_UNSUPPORTED` |
| malformed matrix, delta, threshold, interval, or graph-bound input | `ARCANA_DENY_MODEL_INPUT_INVALID` |
| stale context or expired cache | `ARCANA_DENY_CONTEXT_STALE` |
| graph hash mismatch | `ARCANA_DENY_GRAPH_HASH_MISMATCH` |
| horizon mismatch | `ARCANA_DENY_DECISION_HORIZON_MISMATCH` |
| insufficient calibration for requested path | `ARCANA_DENY_CALIBRATION_INSUFFICIENT` |
| budget exceeded | `ARCANA_DENY_BUDGET_EXHAUSTED` |
| invalid positive vector, method, SCC decomposition, epsilon floor, or component-local proof | `ARCANA_DENY_FASTGATE_VECTOR_INVALID` |
| valid fast path but insufficient margin or inconclusive bound | `ARCANA_DENY_FASTGATE_UNCERTAIN` |
| exact or fast upper bound exceeds threshold | `ARCANA_DENY_RHO_UPPER_BOUND` |

## 14. Certificate and Context Fields

When FastGate is used or evaluated, risk contexts and certificate-like artifacts should include:

```text
fastgate.mode
fastgate.positive_vector_method
fastgate.upper_bound
```

`positive_vector_method` and `upper_bound` are required when:

```text
fastgate.mode = perron_collatz_bound
```

`fastgate.mode = exact_recompute` means the exact after-state spectral result was used.

`fastgate.mode = observe_only` means no admission claim is made from FastGate.

## 15. Public Schema Alignment

Public schema v0.2 recognizes:

```text
perron_collatz_bound
exact_recompute
observe_only
```

and these positive-vector methods:

```text
irreducible_perron_vector
scc_decomposition
epsilon_floor
component_local_gate
fallback_exact
```

The schema must reject `perron_collatz_bound` artifacts that omit `positive_vector_method` or `upper_bound`.

## 16. Non-Goals

FastGate v0.1 does not:

- replace exact spectral evaluation;
- prove absolute safety;
- weaken upper-bound admission semantics;
- use mean risk for admission;
- optimize loss modeling;
- publish private runtime or adapter mechanics;
- infer control effectiveness without calibration;
- make risk-reducing deltas fast-allowable without reviewed proof.

## 17. Reference Implementation Entry Contract

The future reference implementation should implement FastGate in this order:

1. exact recompute path for `K_after_upper`;
2. sparse delta validation;
3. graph and delta hash binding;
4. positive-vector validation;
5. Collatz bound calculation;
6. numerical margin policy;
7. SCC decomposition fallback;
8. epsilon-floor fallback;
9. component-local gate fallback;
10. exact recompute fallback;
11. explicit reason-code tests for every failure path;
12. certificate/context FastGate field emission.

FastGate prototype work should start only after exact spectral calculation and upper-bound decision evaluator tests pass.

## 18. Minimal Test Matrix

The first implementation must include tests for:

- exact recompute allow;
- exact recompute rho breach;
- warm path allow with valid positive vector;
- warm path denied by insufficient margin;
- missing positive-vector method;
- nonpositive vector entry;
- reducible graph without declared handling;
- SCC handling with affected component closure;
- epsilon floor with insufficient margin;
- component-local gate with invalid closure;
- stale hot-path cache;
- graph hash mismatch;
- horizon mismatch;
- malformed sparse delta;
- budget exhaustion;
- A0 observe-only FastGate artifact.

## 19. Open Questions

- Should public v0.1 default to `scc_decomposition` or `exact_recompute` for reducible graphs?
- Should risk-reducing deltas be exact-only for all v0.1 examples?
- Should `numeric_margin` be schema-visible in v0.3?
- Should FastGate expose component-local bounds in a separate public schema object?
- Should `exact_recompute` certificates include `positive_vector_method: fallback_exact` or omit the method?

## 20. Next Artifact

The next public planning artifact is:

```text
Public Demo and Reference Implementation Plan v0.1
```
