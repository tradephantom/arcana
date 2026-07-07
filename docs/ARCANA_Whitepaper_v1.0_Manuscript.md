# ARCANA: Model-Bounded Autonomy Accounting for Agentic Systems

> Status: final manuscript candidate; FWP-REVIEW-008 claim-language review pending
> Scope: final manuscript artifact for the public ARCANA research/reference track
> Classification: public-safe manuscript candidate; not final publication until FWP-REVIEW-008 passes
> Implementation status: reference implementation and synthetic benchmark evidence only

## Abstract

Agentic systems can act through tools, memory, delegation, capability envelopes, repeated operations, and external services. Task success alone does not show whether a proposed operation remains inside an acceptable autonomy-risk envelope. ARCANA introduces a public research/reference framework for autonomy accounting: it estimates whether a proposed operation remains bounded under an explicit risk model version, calibration profile, decision horizon, uncertainty bounds, evidence assumptions, graph state, and reason-code contract.

ARCANA models unsafe propagation pressure separately from loss or impact. It represents an agentic system as a capability graph, assigns horizon-bound propagation weights, computes upper-bound spectral propagation risk, evaluates loss-side quantities separately, and emits schema-shaped risk contexts or certificate-like artifacts with explicit caveats. The public reference implementation uses deterministic synthetic fixtures, public schemas, public reason codes, and local reproducibility gates.

This manuscript does not claim production readiness, production enforcement, universal safety, or production certificate issuance. A0 outputs remain non-certifiable. Benchmark scenarios are synthetic and are intended to show why task success, unsafe action rate, risk-bound status, and artifact-contract validity must be reported separately. ARCANA is only as complete as the graph and evidence it is given.

## 1. Paper Rule

ARCANA may be described as:

```text
model-bounded autonomy accounting for agentic systems
```

The strongest allowed public claim in this manuscript is:

```text
ARCANA estimates bounded autonomy under explicit risk model versions, calibration profiles, decision horizons, uncertainty bounds, and evidence assumptions.
```

The manuscript must not present any agent, workflow, deployment, model, policy, or organization as safe by proof. Every result is scoped by declared assumptions, public schemas, reason codes, evidence, and limitations.

## Contributions

ARCANA contributes:

1. A graph-based model for autonomy-risk propagation in agentic systems.
2. A strict separation between propagation risk `K` and loss or impact `L`.
3. A decision-horizon contract that prevents dimensionally ambiguous risk claims.
4. A calibration-level model that exposes uncertainty and evidence quality.
5. A conservative upper-bound spectral decision rule.
6. FastGate, a fail-closed sparse-update path for low-latency admission.
7. Certificate-like bounded artifacts with reason-code semantics.
8. ARCANA-Bench, a synthetic benchmark separating task success from autonomy risk.

## 2. Problem

Agentic systems can complete tasks while increasing autonomy risk. Examples include:

- routing unsafe instructions through an otherwise useful tool path;
- retaining poisoned memory that affects future operations;
- requesting a tool scope broader than the task requires;
- delegating across agents until risk compounds;
- optimizing for benchmark success while hiding unsafe actions;
- generating dynamic behavior outside the calibrated envelope.

These behaviors are not captured by a task-success metric alone. ARCANA asks a narrower question:

```text
Given a proposed operation, graph state, calibration profile, decision horizon, uncertainty interval, and evidence bundle, does the operation remain inside the declared bounded-risk envelope?
```

This is not the same question as whether a local policy should allow the operation. ARCANA can inform surrounding systems, but the surrounding system remains responsible for local policy, enforcement, and operational approval.

## 3. Scope and Non-Scope

Public ARCANA includes:

- formal model documentation;
- calibration methodology;
- reason-code registry;
- public schemas;
- reference implementation;
- synthetic demos;
- ARCANA-Bench synthetic scenarios;
- public integration contract;
- limitations and release-readiness documents.

Public ARCANA does not include:

- production enforcement implementation;
- private policy engine;
- customer telemetry pipeline;
- production dashboard;
- private deployment profile;
- commercial certificate issuance;
- private evidence payload;
- production operational approval.

The public repository is a research/reference track. It is not a production control plane.

## 4. Model Overview

ARCANA represents an agentic system at time `t` as a graph:

```text
G_t = (V_t, E_t)
```

where `V_t` contains public node classes:

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

An edge is:

```text
e = (source, target, edge_type, factors, evidence)
```

Each edge describes a possible unsafe propagation path over a declared decision horizon. The graph hash binds matrix ordering and artifact scope to the graph state used for evaluation.

## 5. Decision Horizon

A decision horizon is:

```text
H = (horizon_id, duration_seconds, context)
```

Every model input must be horizon-compatible:

- graph edge weights;
- calibration profile;
- risk context;
- certificate-like artifact;
- proposed graph delta;
- loss bounds where loss is in scope.

Without `H`, propagation weights are dimensionally ambiguous. Missing or incompatible horizons return:

```text
ARCANA_DENY_DECISION_HORIZON_MISMATCH
```

The horizon is not a formatting detail. It is part of the mathematical contract.

## 6. Edge Weights and Propagation Matrix

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

Risk-amplifying factors use conservative upper bounds when unknown. Control factors use conservative lower bounds when unknown.

Expected factor domains:

| Factor | Domain | Meaning |
| --- | --- | --- |
| `activation_e(H)` | `>= 0` | Expected unsafe transition pressure over horizon `H`; may exceed `1` only when repeated transition pressure is intentionally modeled. |
| `p_unsafe_e(H)` | `[0, 1]` | Conditional unsafe-transition likelihood under the declared model. |
| `exposure_e(H)` | `[0, 1]` | Degree to which the target can be reached by the source under the current operational context. |
| `capability_e(H)` | `[0, 1]` | Privilege amplification or capability strength if the target is reached. |
| `scope_e(H)` | `[0, 1]` | Breadth of resources or actions available through the edge. |
| `detectability_e(H)` | `[0, 1]` | Strength of detection over the horizon. |
| `gate_effectiveness_e(H)` | `[0, 1]` | Strength of human, policy, or technical gate controls. |
| `reversibility_e(H)` | `[0, 1]` | Degree to which the transition can be undone or contained. |

Calibration profiles must prevent double-counting between `exposure_e`,
`capability_e`, and `scope_e`. Each factor should have a definition, domain,
source, uncertainty rule, conservative default direction, and caveat when
evidence is sparse or stale.

For `n = |V_t|`, the propagation matrix is:

```text
K(H) in R_nonnegative^(n x n)
```

with:

```text
K_ij(H) = sum w_e(H) for all edges e where source(e) = i and target(e) = j
```

`K` must be square, nonnegative, horizon-bound, and graph-bound. It contains unsafe propagation pressure only. If graph, matrix, interval, threshold, node ordering, or required model input is malformed, ARCANA returns:

```text
ARCANA_DENY_MODEL_INPUT_INVALID
```

## 7. Uncertainty and Spectral Risk

ARCANA tracks matrix uncertainty as:

```text
K_lower(H), K_mean(H), K_upper(H)
```

with the invariant:

```text
0 <= K_lower_ij <= K_mean_ij <= K_upper_ij
```

ARCANA computes:

```text
rho_lower = rho(K_lower)
rho_mean  = rho(K_mean)
rho_upper = rho(K_upper)
```

Admission-like decisions use `rho_upper`, not `rho_mean`.

The public subcritical-under-model condition is:

```text
0 <= theta_rho <= 1
rho(K_upper) < theta_rho
```

where `theta_rho` is the declared public threshold for the decision context. A
stricter policy threshold may be used only inside the same subcritical range:

```text
rho(K_upper) < theta_rho <= 1
```

This condition means the declared model is subcritical under the stated
assumptions. A threshold above `1` may be a diagnostic or policy quantity in
some other model, but it must not support an ARCANA public allow-like,
subcritical-under-model, or certificate-like bounded-autonomy artifact. Public
allow-like, subcritical-under-model, and certificate-like bounded-autonomy
artifacts must not use `theta_rho > 1`. It is not a statement about all
possible real-world behavior.

When the upper-bound propagation risk exceeds the threshold or budget, ARCANA returns:

```text
ARCANA_DENY_RHO_UPPER_BOUND
```

## Mathematical Propositions and Proof Sketches

The public model relies on standard facts about nonnegative matrices. These
propositions are model-bounded statements, not claims about all real-world
behavior.

### Proposition 1 - Subcritical finite propagation

For a nonnegative propagation matrix `K` with:

```text
rho(K) < 1
```

the Neumann series converges:

```text
sum_{m=0}^{infinity} K^m
```

Under the declared ARCANA model, this means modeled propagation pressure remains
finite. It does not prove that unmodeled propagation paths are absent.

### Proposition 2 - Upper-bound monotonicity

If:

```text
0 <= K <= K_upper
```

entrywise, then:

```text
rho(K) <= rho(K_upper)
```

This justifies using `rho_upper` for admission-like decisions when uncertainty
is represented through entrywise upper-bound matrices.

### Proposition 3 - FastGate conservative bound

For `A >= 0` and `x > 0`, the Collatz-Wielandt upper bound gives:

```text
rho(A) <= max_i ((A x)_i / x_i)
```

FastGate may use this only as a conservative upper bound. If the vector,
nonnegativity, graph, cache, margin, calibration, or horizon assumptions fail,
FastGate must not return an allow-like result.

## 8. Loss Is Separate From Propagation

ARCANA separates:

```text
K = unsafe propagation pressure
L = impact or loss
```

Loss can include operational, financial, privacy, compliance, safety, or reputational impact. Loss must not be embedded in `K`; propagation risk must not be treated as impact.

When loss is in scope, ARCANA can report loss-side upper bounds such as:

```text
AaR_99_upper
AES_99_upper
```

If a required loss model is missing, malformed, unsupported, or horizon-incompatible, ARCANA returns:

```text
ARCANA_DENY_LOSS_MODEL_INVALID
```

If the upper-bound Autonomy-at-Risk or Agentic Expected Shortfall exceeds declared limits, ARCANA returns:

```text
ARCANA_DENY_AAR_UPPER_BOUND
ARCANA_DENY_AES_UPPER_BOUND
```

An operation can have bounded propagation risk but unacceptable loss bounds. It can also have low expected impact but unacceptable propagation-risk upper bound.

## 9. Calibration

Calibration converts evidence and assumptions into uncertainty bounds. It is not a proof of real-world behavior.

ARCANA uses four public calibration levels:

| Level | Name | Public use | Certification status |
| --- | --- | --- | --- |
| A0 | Heuristic / Demo Only | Synthetic examples, tutorials, paper illustrations. | Always `non_certifiable`. |
| A1 | Static Conservative Prior | Conservative offline estimates from declared static factors. | Public v0.2 default is `non_certifiable`; no certificate-like artifact support. |
| A2 | Empirical / Red-Team Calibration | Controlled adversarial evidence, replay, and benchmark evidence. | Eligible for `certifiable_under_profile` only after reviewed scope, coverage, freshness, and non-synthetic evidence checks. |
| A3 | Runtime Bayesian Calibration | Maintained segmented distributions with decay and priors. | Eligible for `certifiable_under_profile` only after reviewed runtime evidence and auditability checks. |

A0 is demo-only. A0 outputs must preserve:

```text
ARCANA_INFO_A0_NON_CERTIFIABLE
```

The public claim boundary after production-readiness review is:

- A1 is a conservative prior level and is not a commercial certificate basis.
- A1 can support bounded reference risk contexts when all other constraints pass,
  but A1 remains `non_certifiable` and cannot support non-demo certificate-like
  artifacts in the public v0.2 contract.
- A2 may support reviewed empirical calibration claims only when scope,
  evidence, freshness, horizon, and non-synthetic evidence match the reviewed
  profile.
- A3 remains a runtime-calibration design target unless a separate runtime
  distribution review is completed.
- Public examples do not disclose private thresholds, formulas, runtime
  distributions, telemetry, or deployment mechanics.
- No public calibration level in this manuscript authorizes production enforcement or
  certificate issuance by itself.

The phrase `certifiable_under_profile` is a bounded public/reference semantic
state. It means that an artifact may support a bounded-under-profile claim
inside the declared ARCANA model and calibration profile. It does not imply
commercial certificate issuance, production enforcement, customer approval, or
operational authorization.

If the requested decision requires stronger calibration than the supplied profile, ARCANA returns:

```text
ARCANA_DENY_CALIBRATION_INSUFFICIENT
```

If evaluation is allowed but admission-like claims are not, ARCANA may return:

```text
ARCANA_REQUIRE_OBSERVE_ONLY
```

Calibration limitations must be visible in the result. Sparse evidence widens uncertainty. Stale evidence weakens or invalidates the profile. Passive absence of observed incidents cannot collapse uncertainty by itself.

## 10. Evidence Binding

ARCANA artifacts bind results to evidence by source identifiers and hashes. A public evidence reference may include:

```text
source_type
source_id
evidence_hash
synthetic
```

For public examples, `synthetic` must be true. An evidence hash binds the artifact to evidence; it does not prove evidence quality by itself.

Evidence mismatch, stale evidence, missing evidence, or unsupported evidence class can invalidate the result. The correct action is recompute, denial, or observe-only according to the public reason-code contract.

## 11. Decision Semantics

ARCANA emits explicit verdicts:

| Verdict | Meaning |
| --- | --- |
| `allow_bounded_autonomy` | The proposed operation is bounded under declared assumptions. |
| `allow_with_controls` | The operation is bounded only if listed controls are applied. |
| `require_scope_reduction` | The requested scope is too broad but may become bounded if narrowed. |
| `require_human_gate` | A human or policy gate is required before admission. |
| `observe_only` | The result may be analyzed but not treated as bounded for admission or certification. |
| `deny` | The operation is outside the declared bounded-risk envelope or invalid. |

Allow-like results require compatible model, calibration, horizon, graph, evidence, uncertainty, threshold, budget, and controls.

Distinct failures must not collapse into generic denial. Examples:

```text
ARCANA_DENY_RISK_MODEL_UNSUPPORTED
ARCANA_DENY_CONTEXT_STALE
ARCANA_DENY_GRAPH_HASH_MISMATCH
ARCANA_DENY_BUDGET_EXHAUSTED
ARCANA_REQUIRE_SCOPE_REDUCTION
ARCANA_REQUIRE_HUMAN_GATE
```

Reason codes are part of the public contract surface and must be preserved by integrations.

## 12. Certificate-Like Artifacts

Certificate-like artifacts are bounded records. They are not broad approvals.

Every certificate-like artifact must include:

- schema version;
- certificate identifier;
- certificate type;
- risk model version;
- calibration profile;
- calibration level;
- decision horizon;
- graph hash;
- uncertainty bounds;
- evidence source or hash;
- verdict;
- reason codes;
- caveats;
- issued time and expiry when applicable.

A0 artifacts are non-certifiable and cannot support production certificate issuance.

In this public manuscript, A1 certificate-like artifacts are not supported beyond
non-certifiable reference contexts. A2 and A3 references are conditional claim
boundaries: they describe what a reviewed profile would need to bind, not an
authorization to issue a production certificate from this repository.
Certificate issuance, if ever implemented by a deployment-specific system,
requires a separate issuance process, expiry, revocation path, support
evidence, and review record.

If a certificate-like artifact is stale, graph-mismatched, horizon-mismatched, evidence-mismatched, or missing required fields, it must be rejected or recomputed.

## 13. FastGate

FastGate is a conservative optimization path for sparse graph changes. It must preserve the exact upper-bound decision rule:

```text
0 <= theta_rho <= 1
rho(K_after_upper) < theta_rho
```

FastGate may return an allow-like result only when it proves a conservative bound:

```text
fastgate_upper_bound >= rho(K_after_upper)
fastgate_upper_bound < theta_rho
```

If FastGate cannot prove both inequalities, it must not return `allow_bounded_autonomy`.

Recognized public modes:

| Mode | Purpose | Allow-like result permitted |
| --- | --- | --- |
| `exact_recompute` | Full recompute of `rho(K_after_upper)`. | Yes, if exact constraints pass. |
| `perron_collatz_bound` | Conservative sparse update bound. | Yes, if bound proves admission with margin. |
| `observe_only` | Evaluate or explain without admission authority. | No. |

FastGate must validate positive-vector assumptions, reducible graph handling, cache keys, numerical margin, and evidence binding.

If the fast path is inconclusive:

```text
ARCANA_DENY_FASTGATE_UNCERTAIN
```

If positive-vector requirements are invalid:

```text
ARCANA_DENY_FASTGATE_VECTOR_INVALID
```

FastGate is not a weaker model. It is a faster path that must fail closed when assumptions fail.

## 14. Distillation Risk

Distillation means treating an operation, plan, or behavior as repeatable. This can compress repeated autonomy into a persistent pattern.

Distillation is not eligible unless evidence, stability, scope, calibration, and invalidation rules are sufficient. If they are not sufficient, ARCANA returns:

```text
ARCANA_DENY_DISTILLATION_RISK
```

Public examples must not imply that a demo behavior can become a production reusable pattern without reviewed calibration evidence.

## 15. ARCANA-Bench

ARCANA-Bench v0.1 demonstrates why autonomy risk accounting differs from task-success evaluation. The public benchmark suite uses synthetic scenarios only.

Scenario classes:

| Scenario class | Benchmark question |
| --- | --- |
| Indirect prompt injection containment | Can task success coexist with unsafe instruction-routing risk? |
| Persistent memory poisoning containment | Can stale or poisoned memory affect future autonomy risk? |
| Tool misuse scope reduction | Does requested tool scope exceed the bounded envelope? |
| Unsafe delegation cascade | Does delegation amplify propagation risk across agents? |
| Benchmark gaming detection | Can high task success hide unsafe action behavior? |
| Dynamic execution risk | Does runtime-generated behavior exceed calibration scope? |

Required metrics:

```text
task_success_rate
unsafe_action_rate
policy_violation_rate
delta_rho_upper
rho_peak
AaR_99_upper
AES_99_upper
containment_time_steps
autonomy_budget_consumed
human_intervention_efficiency
artifact_contract_validity_rate
```

Task success is not an ARCANA safety score. Benchmark reports must separate at least:

```text
task_success_rate
unsafe_action_rate
risk_bound_status
artifact_contract_validity_rate
```

`artifact_contract_validity_rate` measures whether artifacts include required public fields and reason codes. It does not mean production certification or operational approval.

Earlier drafts used the name `certificate_validity_rate`; this manuscript uses
`artifact_contract_validity_rate` to avoid implying that the metric validates a
production certificate.

### Negative Controls and Failure Fixtures

ARCANA-Bench includes public synthetic negative-control fixtures that prove the
evaluator fails closed under distinct failure modes. Each negative-control
fixture declares `scenario_type: negative_control` and a required
`negative_control` identifier.

| Negative-control identifier | Required behavior |
| --- | --- |
| `missing_decision_horizon` | deny with `ARCANA_DENY_DECISION_HORIZON_MISMATCH`. |
| `graph_hash_mismatch` | deny with `ARCANA_DENY_GRAPH_HASH_MISMATCH`. |
| `a0_artifact_used_for_admission` | observe-only or deny; never production admission. |
| `rho_mean_below_threshold_rho_upper_above_threshold` | must not allow; current public fixture denies with `ARCANA_DENY_RHO_UPPER_BOUND`. |
| `fastgate_inconclusive` | fail closed with `ARCANA_DENY_FASTGATE_UNCERTAIN`. |
| `loss_model_missing_required` | deny with `ARCANA_DENY_LOSS_MODEL_INVALID`. |
| `stale_evidence` | recompute, observe-only, or deny according to reason-code contract; current public fixture denies with `ARCANA_DENY_CONTEXT_STALE`. |

## 16. Reference Implementation

The public reference implementation is a local, deterministic implementation of the public contracts. It is intended for review, reproduction, and tests, not production deployment.

Public implementation components include:

- typed graph and calibration objects;
- schema validation;
- spectral risk calculator;
- decision evaluator with explicit reason-code branches;
- A0 certificate-like demo output marked non-certifiable;
- FastGate prototype;
- ARCANA-Bench synthetic fixture loader;
- ARCANA-Bench negative-control coverage validator;
- public audit and validation tools.

Local reproduction:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
make check
make test
make demo
```

The local gate includes public-boundary audit, schema/example validation, unit tests, and the deterministic synthetic demo.

The demo does not require network access.

## 17. Public Integration Contract

ARCANA exports model-bounded risk artifacts. Surrounding systems decide local actions.

Public integration rules:

- validate public schema before use;
- validate model version, calibration profile, decision horizon, graph hash, evidence, verdict, and reason codes;
- preserve original ARCANA reason codes;
- preserve evidence source and hash binding;
- keep public fields separate from integration-private fields;
- reject or recompute stale, unsupported, mismatched, or uncertain artifacts;
- keep A0 non-certifiable markers visible.

ARCANA remains enforcement-neutral. This paper does not define production enforcement, private policy evaluation, private telemetry, or commercial certificate issuance.

ARCANA can be integrated with capability-bound execution systems, policy
gateways, or runtime brokers, but the public ARCANA reference track remains
enforcement-neutral.

## 18. Limitations

ARCANA is useful only inside its declared scope.

ARCANA is only as complete as the graph and evidence it is given.

Core limitations:

- the graph can omit real propagation paths;
- calibration can be sparse, stale, wrong, or incomplete;
- synthetic benchmark results do not prove production behavior;
- A0 output is non-certifiable;
- A1 output is not a commercial certificate basis in this public track;
- A1 cannot support non-demo certificate-like artifacts in the public v0.2
  contract;
- A2/A3 language remains conditional on separate review, evidence coverage,
  freshness, horizon compatibility, non-synthetic evidence, expiry, and
  revocation handling;
- FastGate depends on valid assumptions and fallback paths;
- evidence hashes bind artifacts but do not prove evidence quality;
- local policy may be stricter than ARCANA's bounded result;
- a valid artifact is not a substitute for operational review;
- public examples do not represent private deployments.

No public release should proceed when claim boundaries are unclear.

## 19. Related Work

ARCANA is positioned as a bounded autonomy-accounting layer, not as a replacement
for tool protocols, threat taxonomies, governance frameworks, runtime
verification, proof-carrying authorization, network propagation models, or
financial tail-risk methods.

| Area | Relationship to ARCANA |
| --- | --- |
| Model Context Protocol (MCP) | MCP standardizes how AI applications connect to external systems such as data sources, tools, and workflows. ARCANA does not compete with tool connectivity; it accounts for autonomy risk in operations that such connectivity can enable. Source: https://modelcontextprotocol.io/docs/getting-started/intro |
| OWASP Agentic AI threats | OWASP's Agentic AI guidance frames emerging agentic threats and mitigations through a threat-model lens. ARCANA can complement such taxonomies with model-bounded risk artifacts, reason codes, and calibration-scoped decisions. Source: https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/ |
| NIST AI Risk Management Framework | NIST AI RMF is a voluntary framework for managing AI risks to individuals, organizations, and society. ARCANA does not replace AI RMF; it provides a narrower mechanism for bounded-under-model decisions in agentic operations. Source: https://www.nist.gov/itl/ai-risk-management-framework |
| Runtime verification and authorization | ARCANA can inform runtime checks, but the public reference track does not define private enforcement or authorization infrastructure. |
| Branching processes and network propagation | ARCANA borrows the subcritical intuition of finite propagation pressure, but every claim remains bound to the declared graph, horizon, and calibration. |
| VaR and expected shortfall | ARCANA separates propagation risk from loss-side tail quantities such as Autonomy-at-Risk and Agentic Expected Shortfall. |

## 20. Related Public Artifacts

This manuscript is grounded in the current public research/reference artifacts:

| Artifact | Role in this manuscript |
| --- | --- |
| `docs/FORMAL_MODEL_v0.2.md` | Mathematical contract for graph, `K`, `L`, horizon, uncertainty, and decision rule. |
| `docs/CALIBRATION_METHODOLOGY_v0.1.md` | Calibration levels, evidence quality, sparse evidence, and staleness. |
| `docs/REASON_CODES.md` | Public reason-code contract. |
| `schemas/` | Public machine-readable artifact contracts. |
| `examples/` | Synthetic examples and benchmark fixtures. |
| `docs/FASTGATE_DESIGN_v0.1.md` | Conservative FastGate semantics. |
| `docs/ARCANA_BENCH_v0.1.md` | Synthetic benchmark scenario suite and metrics. |
| `docs/PUBLIC_INTEGRATION_CONTRACT_v0.1.md` | Enforcement-neutral import/export guidance. |
| `docs/LIMITATIONS_v0.1.md` | Explicit public limitations and release gates. |
| `src/arcana/` | Public reference implementation. |
| `tests/` | Local reproducibility and contract tests. |

## 21. Review Checklist

Before this manuscript is treated as a final paper publication, reviewers should verify:

- every claim names or implies model, calibration, horizon, uncertainty, and evidence scope;
- `rho_upper`, not `rho_mean`, is the admission-like metric;
- `K` and `L` remain separate;
- A0 artifacts remain non-certifiable;
- reason-code branches remain distinct;
- FastGate fails closed when assumptions fail;
- benchmark task success is separate from unsafe action rate and artifact-contract validity;
- every required ARCANA-Bench negative control exists as a public synthetic fixture;
- reproduction commands are current;
- public integration language remains enforcement-neutral;
- limitations appear before any broad claim;
- final license profile and GitHub Private Vulnerability Reporting remain in place for the public remote.

## 22. Manuscript Status

This is the v1.0 public manuscript candidate transformed from the reviewed v0.3
draft. The public repository is live, the release note is public, and the final
paper publication gate is still in progress. This manuscript is ready for final
claim-language review, not final public publication.

The final paper publication gate is still in progress until FWP-REVIEW-008
passes.

This manuscript is ready for final claim-language review, not final public publication.

Open publication blocker:

- FWP-REVIEW-008 final public claim-language review after manuscript
  transformation.

Completed publication prerequisites:

- public remote preflight validation;
- GitHub Private Vulnerability Reporting configuration;
- public release-note publication;
- fresh-clone validation of `make check`, `make test`, and `make demo`;
- mathematical review of public subcritical threshold semantics;
- calibration-level review of A1/A2/A3 public semantics;
- public schema contract review;
- FastGate numerical and graph-edge-case review;
- ARCANA-Bench scenario coverage review;
- independent reproduction of local tests and deterministic demo;
- final manuscript transformation from draft to publication artifact.
