# PRD: ARCANA v0.2 Public

> Product: ARCANA - Autonomy Risk Calculus for Agentic Network Assurance
> Status: public-safe draft for review
> Date: 2026-06-05
> Source: derived from the ARCANA internal baseline and publication boundary review
> Classification: open-candidate, redaction review required before public release
> Implementation status: documentation only; no reference implementation is approved by this document

## 1. Executive Summary

ARCANA is an open research and reference framework for autonomy accounting in agentic systems.

ARCANA estimates whether a proposed operation, delegation, tool call, memory action, capability grant, or distillation event remains within a bounded risk envelope under:

- an explicit risk model version;
- an explicit calibration profile;
- an explicit decision horizon;
- declared uncertainty bounds;
- evidence-backed reason codes.

ARCANA does not prove that an agent or system is safe. It provides model-bounded autonomy accounting and may issue bounded autonomy certificates when the required evidence and calibration conditions are present.

Preferred public claim:

```text
ARCANA estimates and certifies bounded autonomy under explicit risk model versions, calibration profiles, decision horizons, and uncertainty bounds.
```

## 2. Product Boundary

ARCANA public scope:

- formal model;
- calibration methodology;
- benchmark scenarios;
- public-safe schemas;
- synthetic demos;
- reference implementation;
- public PRD, roadmap, glossary, and whitepaper.

Out of scope for the public ARCANA repository:

- production policy engines;
- customer telemetry and dashboards;
- private enterprise adapters;
- commercial certificate issuance workflows;
- private capability-bound execution implementation details;
- private lab architecture or operational profiles.

ARCANA can integrate with enforcement systems, but ARCANA is not the enforcement boundary. ARCANA answers how much autonomy risk a proposed action consumes. The surrounding system still decides whether to admit, deny, scope, observe, or escalate the action.

## 3. Problem Statement

Modern agent systems are gaining:

- persistent memory;
- tool and API access;
- code execution paths;
- delegation to other agents;
- data access and transformation authority;
- operational permissions;
- financial, infrastructure, privacy, or compliance impact.

Traditional controls ask:

```text
Is this action permitted?
```

ARCANA asks:

```text
How much systemic autonomy risk does this action add under the declared model and calibration profile?
```

Permission is necessary but insufficient. Autonomy must be measured, budgeted, calibrated, bounded, and audited.

## 4. Goals

- Define a graph-based model of agentic propagation risk.
- Separate propagation risk from loss and impact.
- Require explicit model versioning, calibration profiles, decision horizons, and uncertainty bounds.
- Support conservative defaults where unknown inputs increase risk or reduce assumed control effectiveness.
- Provide a low-latency FastGate method for incremental admission decisions.
- Produce bounded autonomy certificates only when evidence and calibration requirements are met.
- Provide public-safe schemas for risk context and certificate artifacts.
- Provide synthetic benchmark scenarios for autonomy risk evaluation.
- Provide an offline reproducible reference demo before any production integration.

## 5. Non-Goals

ARCANA does not aim to:

- prove absolute safety;
- replace identity, policy, sandboxing, or enforcement;
- make arbitrary code safe;
- become an AXCP Core feature;
- depend on any private enterprise implementation;
- depend on any private lab or organism;
- treat telemetry without calibration as scientific proof;
- produce production-grade certificates from A0/demo calibration;
- publish private operational thresholds, telemetry, customer profiles, or adapter mechanics.

## 6. Principal Objects

### 6.1 Agentic Capability Graph

```text
G_t = (V_t, E_t)
```

`G_t` represents the agentic system at time `t`.

Public node classes:

```text
A = agents
T = tools/APIs
M = memory/knowledge stores
H = human/policy gates
G = grants or capability envelopes
O = operations/plans
D = distilled or repeated operations
X = external systems
```

Node classes are semantic model objects, not required implementation types.

### 6.2 Propagation Matrix `K`

`K` is a nonnegative matrix representing unsafe propagation across the graph.

`K_ij` is interpreted as expected unsafe transition pressure from node `i` to node `j` over a declared decision horizon `H`.

`K` must not contain monetary loss, business impact, unnormalized severity, or arbitrary impact scores.

### 6.3 Loss Model `L`

`L` models impact separately from propagation. Loss can cover operational, financial, privacy, compliance, safety, or reputational impact.

ARCANA-derived loss metrics include:

```text
AaR_alpha = Autonomy-at-Risk at confidence alpha
AES_alpha = Agentic Expected Shortfall at confidence alpha
```

### 6.4 Calibration Profile

A calibration profile declares how edge weights, uncertainty intervals, thresholds, and evidence quality were derived.

Minimum public fields:

- `profile_id`;
- `risk_model_version`;
- `level`;
- `decision_horizon_id`;
- `source`;
- `evidence_window`;
- `confidence`;
- `last_updated_at`;
- uncertainty bounds;
- caveats.

### 6.5 Risk Context

A risk context is a signed, hash-bound, or otherwise evidence-bound summary of the current ARCANA decision state.

Public risk context may include:

- risk model version;
- calibration profile ID;
- decision horizon ID;
- graph hash;
- rho upper estimate;
- maximum allowed rho upper;
- loss bounds;
- FastGate mode;
- verdict;
- required controls;
- autonomy budget.

### 6.6 Bounded Autonomy Certificate

A bounded autonomy certificate asserts that a decision is subcritical under a specific model, calibration profile, decision horizon, evidence set, and uncertainty bound.

Every certificate-like artifact must include:

- risk model version;
- calibration profile;
- decision horizon;
- rho interval;
- loss bounds when impact is in scope;
- evidence source or evidence hash;
- reason codes;
- verdict;
- caveats.

## 7. Calibration Levels

### A0 - Heuristic / Demo Only

Allowed for:

- paper illustrations;
- local demos;
- synthetic examples;
- non-production tutorials.

Not allowed for:

- production enforcement;
- public claims of certifiable bounded autonomy;
- high-impact action admission;
- distillation eligibility.

Required marker:

```yaml
calibration_level: "A0"
certification_status: "non_certifiable"
```

### A1 - Static Conservative Prior

A1 uses static properties such as capability family, data class, execution mode, scope width, reversibility, detectability, and gate strength.

A1 must:

- document every assumption;
- use upper bounds for risk;
- use lower bounds for controls;
- mark sparse evidence explicitly.

### A2 - Empirical Calibration

A2 uses controlled evidence such as:

- red-team runs;
- adversarial scenario replay;
- prompt-injection tests;
- memory-poisoning tests;
- tool-misuse tests;
- delegation-cascade tests;
- fail-closed tests.

A2 requires:

- evidence IDs;
- test coverage;
- sample sizes;
- model/tool/version segmentation;
- known gaps.

### A3 - Runtime Bayesian Calibration

A3 maintains distributions rather than point estimates.

A3 must account for:

- correlated events;
- temporal decay;
- conservative priors for sparse evidence;
- model, tool, policy, and environment segmentation;
- separation of red-team evidence from passive runtime telemetry.

A lack of observed incidents is not evidence of low risk by itself.

## 8. Decision Rule

ARCANA decisions must use upper bounds for enforcement-like outcomes.

Generic rule:

```text
allow iff:
  policy_eligible == true
  calibration_level >= required_level
  decision_horizon is compatible
  graph/evidence hashes match
  rho_upper_after <= rho_threshold
  AaR_upper <= AaR_limit when loss is in scope
  AES_upper <= AES_limit when loss is in scope
  required_controls are satisfiable
```

If any required input is missing, stale, unsupported, or incompatible, the outcome must be a specific deny, scope-reduction, human-gate, or observe-only result.

## 9. FastGate

ARCANA-FastGate supports low-latency admission for sparse graph changes without a full recompute on every action.

Public FastGate requirements:

- use nonnegative-matrix assumptions explicitly;
- support Perron/Collatz upper-bound reasoning;
- require a valid positive vector method;
- handle reducible graphs through SCC decomposition, epsilon floor, component-local gate, or exact fallback;
- declare the selected method in any certificate;
- return an uncertain/deny result when the fast path cannot prove the bound conservatively.

FastGate is an optimization path. It must not weaken admission semantics.

## 10. Public Reason Codes

Public ARCANA reason codes must be explicit and stable.

Denials:

```text
ARCANA_DENY_CALIBRATION_INSUFFICIENT
ARCANA_DENY_RISK_MODEL_UNSUPPORTED
ARCANA_DENY_CONTEXT_STALE
ARCANA_DENY_GRAPH_HASH_MISMATCH
ARCANA_DENY_DECISION_HORIZON_MISMATCH
ARCANA_DENY_RHO_UPPER_BOUND
ARCANA_DENY_AAR_UPPER_BOUND
ARCANA_DENY_AES_UPPER_BOUND
ARCANA_DENY_BUDGET_EXHAUSTED
ARCANA_DENY_FASTGATE_UNCERTAIN
ARCANA_DENY_FASTGATE_VECTOR_INVALID
ARCANA_DENY_DISTILLATION_RISK
```

Requirements:

```text
ARCANA_REQUIRE_HUMAN_GATE
ARCANA_REQUIRE_SCOPE_REDUCTION
ARCANA_REQUIRE_OBSERVE_ONLY
```

Reason-code meanings must stay granular. Do not collapse unsupported models, stale contexts, calibration gaps, graph mismatches, and threshold breaches into a generic denial.

## 11. Functional Requirements

### FR1 - Versioned Risk Model

Every ARCANA decision must reference a risk model version.

Acceptance criteria:

- missing model version returns `ARCANA_DENY_RISK_MODEL_UNSUPPORTED`;
- unsupported model version returns `ARCANA_DENY_RISK_MODEL_UNSUPPORTED`;
- model version is included in certificates and risk contexts.

### FR2 - Decision Horizon

Every `K`, calibration profile, and certificate must declare a decision horizon.

Acceptance criteria:

- missing horizon returns `ARCANA_DENY_DECISION_HORIZON_MISMATCH`;
- incompatible horizon returns `ARCANA_DENY_DECISION_HORIZON_MISMATCH`;
- edge weights are interpreted only within compatible horizons.

### FR3 - K/L Separation

Propagation risk and loss/impact must be modeled separately.

Acceptance criteria:

- `K` values cannot contain loss or arbitrary impact values;
- loss bounds are represented through `L`, AaR, and AES fields;
- public docs do not describe rho as a financial loss score.

### FR4 - Calibration Enforcement

ARCANA must distinguish A0, A1, A2, and A3.

Acceptance criteria:

- A0 artifacts are marked non-certifiable;
- high-impact actions can require A2 or stronger calibration;
- insufficient calibration returns `ARCANA_DENY_CALIBRATION_INSUFFICIENT` or `ARCANA_REQUIRE_OBSERVE_ONLY`.

### FR5 - Upper-Bound Decisions

Admission decisions must use upper uncertainty bounds.

Acceptance criteria:

- `rho_upper`, not `rho_mean`, drives threshold denial;
- upper AaR/AES bounds drive impact denial when loss is in scope;
- sparse evidence widens uncertainty.

### FR6 - FastGate Fallback

FastGate must return a conservative outcome when its assumptions fail.

Acceptance criteria:

- invalid positive-vector method returns `ARCANA_DENY_FASTGATE_VECTOR_INVALID`;
- inconclusive fast path returns `ARCANA_DENY_FASTGATE_UNCERTAIN`;
- exact recompute is available as a documented fallback path in the reference implementation.

### FR7 - Certificate Generation

ARCANA may generate bounded autonomy certificates only when required fields are present.

Acceptance criteria:

- certificate schema rejects missing calibration profile;
- certificate schema rejects missing evidence;
- certificate schema requires at least one reason code;
- A0 certificate examples include `certification_status: "non_certifiable"`.

### FR8 - Public Reference Implementation

The reference implementation must be standalone and public-safe.

Acceptance criteria:

- no private enterprise imports;
- no private lab imports;
- synthetic fixtures only;
- explicit reason-code branches;
- deterministic CLI examples;
- unit tests for each denial reason code.

## 12. Security Requirements

- Fail closed when calibration is insufficient for the requested impact class.
- Fail closed on stale or mismatched risk context when context validity is required.
- Treat agent-declared risk values as untrusted input.
- Treat unknown edge factors as risky.
- Use conservative upper bounds for risk and conservative lower bounds for control effectiveness.
- Do not issue bounded autonomy certificates from missing, stale, or unverifiable evidence.
- Do not allow distillation eligibility without valid evidence, stability, scope, invalidation, and risk envelope.
- Do not expose private enterprise, customer, or lab details in public schemas, demos, fixtures, or examples.

## 13. ARCANA-Bench v0.1

ARCANA-Bench evaluates autonomy risk and containment, not only task success.

Initial public-safe scenario classes:

- indirect prompt injection;
- persistent memory poisoning;
- privilege escalation through delegation;
- unsafe delegation loop;
- tool misuse;
- evaluator or benchmark gaming;
- data exfiltration attempt;
- resource exhaustion;
- stale evidence or stale context;
- over-scoped operation plan;
- dynamic execution abuse.

Metrics:

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
distillation_eligibility_rate
certificate_validity_rate
```

Benchmark scenarios must be synthetic or public-source safe. They must not encode private customer, enterprise, or lab workflows.

## 14. Public Demo Requirements

The first public demo should be offline and reproducible.

Required demo behavior:

- load a synthetic graph;
- compute `rho(K)`;
- evaluate a proposed sparse graph change;
- produce an allow, scope-reduction, human-gate, observe-only, or deny verdict;
- emit public ARCANA reason codes;
- emit an A0 non-certifiable example certificate;
- demonstrate K/L separation through a toy loss model clearly marked as synthetic.

The demo must not imply production readiness.

## 15. Public Schema Requirements

Public schemas should be versioned under public schema IDs and must avoid private implementation coupling.

Required schemas:

- `ARCANA_Context.schema.v0.2.json`;
- `ARCANA_Certificate.schema.v0.2.json`;
- future `ARCANA_CalibrationProfile.schema.v0.2.json`;
- future `ARCANA_BenchmarkScenario.schema.v0.2.json`.

Public schema constraints:

- no internal URLs;
- no private policy profile names;
- no customer identifiers;
- no private enterprise adapter fields;
- no private lab fields;
- public ARCANA reason codes as defaults.

## 16. Release Criteria

ARCANA v0.2 public documentation is releasable when:

- publication boundary review is complete;
- PRD v0.2 is reviewed;
- public roadmap v0.1 exists;
- public-safe glossary exists;
- public reason-code registry exists;
- schemas use public IDs;
- examples are synthetic and marked non-production;
- claim discipline is verified;
- license, contribution policy, security policy, and limitations are added.

Reference implementation work under `src/` should start only after the public PRD and roadmap are reviewed.

## 17. Open Questions

- What public schema namespace should replace current internal schema IDs?
- Which calibration level is the minimum for non-demo certificate examples?
- Which ARCANA-Bench scenarios should be included in v0.1 versus deferred?
- Should public certificate vocabulary use `certifies bounded autonomy` or prefer `attests bounded autonomy` for lower claim risk?
- What minimal reference implementation language and dependency set should be selected?

## 18. Next Artifacts

1. Calibration methodology v0.1.
2. FastGate design v0.1.
3. Public demo/reference implementation plan.
4. ARCANA-Bench v0.1 scenario expansion.
