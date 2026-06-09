# ARCANA Public Reason-Code Registry

> Status: public reason-code registry v0.1 draft
> Scope: public ARCANA research/reference outcomes
> Contract: every code has one meaning and one primary handling path

ARCANA reason codes explain why a decision was allowed, denied, constrained, escalated, or marked observe-only.

Reason codes are part of the public contract surface. Do not reuse a code for a distinct failure mode. Do not collapse missing input, unsupported model, stale context, graph mismatch, calibration gap, threshold breach, and fast-path uncertainty into a generic denial.

## Naming Rules

Public ARCANA reason codes use:

```text
ARCANA_<CLASS>_<SPECIFIC_OUTCOME>
```

Allowed classes:

```text
ALLOW
DENY
REQUIRE
INFO
```

Rules:

- use uppercase ASCII identifiers;
- keep codes stable after public release;
- add a new code for a new distinct outcome;
- never use adapter-specific prefixes as public defaults;
- every deny code must have actionable guidance.

## Verdict Mapping

| Verdict | Required reason-code class |
| --- | --- |
| `allow_bounded_autonomy` | `ARCANA_ALLOW_*` or `ARCANA_INFO_*` |
| `allow_with_controls` | `ARCANA_REQUIRE_*` or `ARCANA_INFO_*` |
| `require_scope_reduction` | `ARCANA_REQUIRE_SCOPE_REDUCTION` |
| `require_human_gate` | `ARCANA_REQUIRE_HUMAN_GATE` |
| `observe_only` | `ARCANA_REQUIRE_OBSERVE_ONLY` |
| `deny` | `ARCANA_DENY_*` |

## Allowance Codes

### `ARCANA_ALLOW_BOUNDED_AUTONOMY`

Meaning: the proposed action remains within declared model, calibration, horizon, uncertainty, evidence, threshold, and control constraints.

Use when:

- the risk model version is supported;
- the calibration level is sufficient;
- the decision horizon is compatible;
- graph and evidence hashes match;
- `rho_upper_after` is within threshold;
- loss bounds are within limits when loss is in scope;
- required controls are satisfiable.

Do not use when:

- any required field is missing;
- the result depends on A0/demo calibration for a certifiable claim;
- FastGate is uncertain;
- evidence is stale or mismatched.

Guidance: emit a bounded autonomy certificate only if all certificate fields are present and the calibration level permits certification.

### `ARCANA_ALLOW_WITH_CONTROLS`

Meaning: the proposed action is admissible only with explicit controls.

Use when:

- risk remains within upper-bound limits after controls;
- controls are required for the decision to stay bounded;
- controls are concrete and enforceable by the surrounding system.

Do not use when:

- controls are vague or unavailable;
- scope reduction or human approval is required instead;
- a deny threshold has already been breached.

Guidance: list required controls in the risk context and certificate-like artifact.

## Denial Codes

### `ARCANA_DENY_CALIBRATION_INSUFFICIENT`

Meaning: the requested action requires a stronger calibration level than the provided calibration profile.

Use when:

- A0/demo calibration is used for a non-demo or certifiable claim;
- high-impact action policy requires A2 or stronger calibration;
- evidence quality is below the declared requirement.

Actionable guidance: lower impact, reduce scope, switch to observe-only, add a human gate, or provide stronger calibration evidence.

### `ARCANA_DENY_RISK_MODEL_UNSUPPORTED`

Meaning: the risk model version is missing, unknown, disabled, malformed, or incompatible with the evaluator.

Use when:

- `risk_model_version` is absent;
- the version is syntactically invalid;
- the version is not supported by the current evaluator;
- a schema references a model family the evaluator cannot interpret.

Actionable guidance: provide a supported risk model version and rerun the evaluation.

### `ARCANA_DENY_CONTEXT_STALE`

Meaning: the risk context is expired or older than the allowed freshness window.

Use when:

- `issued_at`, `last_updated_at`, or context expiry is outside the accepted window;
- policy requires fresh context for the action class;
- context age cannot be determined.

Actionable guidance: recompute risk context against current graph, evidence, policy, and calibration profile.

### `ARCANA_DENY_GRAPH_HASH_MISMATCH`

Meaning: the graph used for evaluation does not match the graph referenced by the decision or certificate.

Use when:

- `graph_hash` differs from the current graph;
- graph state changed after context generation;
- the graph hash is missing where graph binding is required.

Actionable guidance: recompute from the current graph and issue a new context.

### `ARCANA_DENY_DECISION_HORIZON_MISMATCH`

Meaning: the requested action, calibration profile, graph weights, or certificate use incompatible decision horizons.

Use when:

- decision horizon is absent;
- horizon identifiers differ where compatibility is required;
- edge weights were normalized over a different horizon;
- horizon duration is invalid.

Actionable guidance: normalize inputs to a compatible horizon and rerun evaluation.

### `ARCANA_DENY_RHO_UPPER_BOUND`

Meaning: upper-bound propagation risk exceeds the declared threshold.

Use when:

- `rho_upper_after > rho_threshold`;
- `delta_rho_upper` exceeds available budget;
- uncertainty widens enough that the upper bound breaches threshold.

Actionable guidance: reduce scope, remove risky edges, add controls with measurable effect, or require human approval if policy permits.

### `ARCANA_DENY_AAR_UPPER_BOUND`

Meaning: upper-bound Autonomy-at-Risk exceeds the declared limit.

Use when:

- loss model is in scope;
- `AaR_upper` or equivalent configured quantile exceeds the allowed bound.

Actionable guidance: reduce loss exposure, restrict affected resources, narrow output authority, or strengthen controls.

### `ARCANA_DENY_AES_UPPER_BOUND`

Meaning: upper-bound Agentic Expected Shortfall exceeds the declared limit.

Use when:

- tail loss is in scope;
- expected tail exposure exceeds the allowed bound.

Actionable guidance: reduce tail exposure, require manual approval, add containment, or deny the action.

### `ARCANA_DENY_BUDGET_EXHAUSTED`

Meaning: the autonomy budget available for the action or context is exhausted.

Use when:

- `max_delta_rho_upper` would be exceeded;
- request, write, output, or other public budget counters would be exceeded;
- the budget has expired.

Actionable guidance: wait for a new budget window, request a smaller action, or recompute with a new approved budget.

### `ARCANA_DENY_FASTGATE_UNCERTAIN`

Meaning: FastGate could not prove admission conservatively.

Use when:

- sparse bound is inconclusive;
- required FastGate inputs are incomplete;
- numerical margin is insufficient;
- fallback exact recompute is required but unavailable.

Actionable guidance: run exact recompute, reduce scope, or return observe-only if policy allows.

### `ARCANA_DENY_FASTGATE_VECTOR_INVALID`

Meaning: FastGate positive-vector requirements are not satisfied.

Use when:

- no positive vector method is declared;
- the declared method is invalid for the graph;
- reducible graph handling is missing;
- epsilon floor, component-local gate, or exact fallback is required but absent.

Actionable guidance: provide a valid positive-vector method or use exact recompute.

### `ARCANA_DENY_DISTILLATION_RISK`

Meaning: the operation is not eligible for distillation under the declared risk, evidence, stability, scope, or invalidation rules.

Use when:

- evidence is insufficient;
- the operation is unstable;
- scope is too broad;
- invalidation rules are absent;
- calibration level is insufficient for distillation.

Actionable guidance: keep the operation non-distilled, gather stronger evidence, narrow scope, or define invalidation rules.

## Requirement Codes

### `ARCANA_REQUIRE_HUMAN_GATE`

Meaning: the action requires human or policy approval before admission.

Use when:

- risk is not low enough for autonomous admission;
- impact class requires approval;
- calibration is not strong enough for autonomous execution but does not require direct denial.

Actionable guidance: route the action to an approval gate with the ARCANA context attached.

### `ARCANA_REQUIRE_SCOPE_REDUCTION`

Meaning: the action may become admissible if scope is reduced.

Use when:

- requested authority is too broad;
- budget breach can be resolved by reducing operation size;
- specific graph edges or resources cause threshold breach.

Actionable guidance: reduce capability envelope, data scope, resource count, delegation depth, output authority, or time horizon.

### `ARCANA_REQUIRE_OBSERVE_ONLY`

Meaning: the action can be evaluated or monitored but not treated as bounded for admission or certification.

Use when:

- calibration is A0/demo only;
- evidence is too weak for enforcement-like claims;
- rollout stage is observation;
- model support is incomplete but non-executing analysis is allowed.

Actionable guidance: run in observation mode, collect evidence, and avoid certificate-like production claims.

## Informational Codes

### `ARCANA_INFO_A0_NON_CERTIFIABLE`

Meaning: output was produced with A0/demo calibration and must not be treated as a certifiable bounded autonomy result.

Use when:

- demo certificate examples are emitted;
- synthetic tutorials show the certificate shape;
- public examples illustrate the model without empirical calibration.

Actionable guidance: keep `certification_status: "non_certifiable"` visible.

### `ARCANA_INFO_SYNTHETIC_FIXTURE`

Meaning: the example, scenario, or certificate uses synthetic data.

Use when:

- fixtures are fabricated for public demos;
- benchmark scenarios are illustrative;
- examples should not be interpreted as production evidence.

Actionable guidance: label the source clearly and avoid operational claims.

## Initial Registry

| Code | Class | Primary verdict | Stable meaning |
| --- | --- | --- | --- |
| `ARCANA_ALLOW_BOUNDED_AUTONOMY` | allow | `allow_bounded_autonomy` | Decision is bounded under declared model, calibration, horizon, uncertainty, evidence, and controls. |
| `ARCANA_ALLOW_WITH_CONTROLS` | allow | `allow_with_controls` | Decision is bounded only if required controls are applied. |
| `ARCANA_DENY_CALIBRATION_INSUFFICIENT` | deny | `deny` | Calibration level or evidence quality is insufficient. |
| `ARCANA_DENY_RISK_MODEL_UNSUPPORTED` | deny | `deny` | Risk model version is missing, malformed, unknown, disabled, or incompatible. |
| `ARCANA_DENY_CONTEXT_STALE` | deny | `deny` | Risk context is expired or too old. |
| `ARCANA_DENY_GRAPH_HASH_MISMATCH` | deny | `deny` | Graph state does not match the bound decision context. |
| `ARCANA_DENY_DECISION_HORIZON_MISMATCH` | deny | `deny` | Decision horizons are missing or incompatible. |
| `ARCANA_DENY_RHO_UPPER_BOUND` | deny | `deny` | Upper-bound propagation risk exceeds threshold or budget. |
| `ARCANA_DENY_AAR_UPPER_BOUND` | deny | `deny` | Upper-bound Autonomy-at-Risk exceeds limit. |
| `ARCANA_DENY_AES_UPPER_BOUND` | deny | `deny` | Upper-bound Agentic Expected Shortfall exceeds limit. |
| `ARCANA_DENY_BUDGET_EXHAUSTED` | deny | `deny` | Autonomy budget is exhausted or expired. |
| `ARCANA_DENY_FASTGATE_UNCERTAIN` | deny | `deny` | FastGate cannot prove admission conservatively. |
| `ARCANA_DENY_FASTGATE_VECTOR_INVALID` | deny | `deny` | FastGate positive-vector requirements are invalid or missing. |
| `ARCANA_DENY_DISTILLATION_RISK` | deny | `deny` | Operation is not eligible for distillation. |
| `ARCANA_REQUIRE_HUMAN_GATE` | require | `require_human_gate` | Human or policy approval is required. |
| `ARCANA_REQUIRE_SCOPE_REDUCTION` | require | `require_scope_reduction` | Action scope must be reduced. |
| `ARCANA_REQUIRE_OBSERVE_ONLY` | require | `observe_only` | Result is observation-only and not certifiable for admission. |
| `ARCANA_INFO_A0_NON_CERTIFIABLE` | info | `observe_only` | A0/demo output is non-certifiable. |
| `ARCANA_INFO_SYNTHETIC_FIXTURE` | info | any | Artifact uses synthetic data. |

## Reserved Prefixes

Only `ARCANA_` is public in this registry.

Adapter-specific prefixes are reserved for private or separate integration layers and must not appear as public defaults.
