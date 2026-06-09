# ARCANA Public Glossary

> Status: public glossary v0.1 draft
> Scope: public ARCANA research/reference vocabulary
> Contract: terms here are public-safe and implementation-neutral

This glossary defines public ARCANA terms before schemas and code are finalized. Terms are intentionally model-bounded and do not imply production safety certification.

## Core Terms

### ARCANA

Autonomy Risk Calculus for Agentic Network Assurance.

ARCANA is a public research and reference framework for autonomy accounting in agentic systems. ARCANA estimates whether proposed actions remain within a bounded risk envelope under explicit model, calibration, horizon, uncertainty, and evidence assumptions.

### Agentic System

A system containing one or more agents that can act, delegate, use tools, access memory, call services, transform data, or trigger operations.

### Autonomy Accounting

The practice of measuring, budgeting, bounding, and auditing the autonomy risk consumed by agentic actions.

Autonomy accounting is not identity, policy, sandboxing, permissioning, or absolute safety proof.

### Autonomy Budget

A bounded allowance for risk-increasing activity over a declared context and decision horizon.

An autonomy budget can limit changes such as `delta_rho_upper`, external requests, writes, output bytes, or other public-safe resource counters. A budget is meaningful only with explicit model and calibration scope.

### Bounded Autonomy

Autonomy that remains within declared model, calibration, horizon, uncertainty, evidence, and threshold constraints.

Bounded autonomy does not mean an agent is safe by definition. It means a decision satisfies the stated ARCANA assumptions and constraints.

### Bounded Autonomy Certificate

A certificate-like artifact asserting that a decision is bounded under a specific ARCANA model, calibration profile, decision horizon, uncertainty interval, evidence set, and reason-code outcome.

Required fields include:

- risk model version;
- calibration profile;
- decision horizon;
- uncertainty bounds;
- evidence source or hash;
- verdict;
- reason codes;
- caveats.

### Calibration Profile

A versioned declaration of how ARCANA risk estimates and uncertainty bounds were derived.

A calibration profile must state its evidence sources, calibration level, decision horizon, confidence, update time, uncertainty policy, and caveats.

### Capability Envelope

A public model object describing the proposed scope of an action or set of actions.

A capability envelope can include operation type, allowed resources, scope, budget, horizon, controls, and evidence references. It is not tied to any private enforcement implementation.

### Decision Horizon

The time or context window over which risk values are normalized and interpreted.

Without a decision horizon, `K` and related estimates are dimensionally ambiguous.

### Evidence Source

A declared source supporting the risk, calibration, or decision context.

Public examples include synthetic benchmark evidence, controlled scenario replay, public red-team fixtures, validation logs, or hash-bound context. Evidence must be explicit; missing evidence cannot silently become confidence.

### Evidence Hash

A cryptographic digest that identifies an evidence artifact without embedding the artifact itself.

Public examples should use synthetic evidence hashes or public-source safe artifacts.

### FastGate

ARCANA's low-latency admission method for sparse graph changes.

FastGate is an optimization path. It must preserve conservative admission semantics and return a specific uncertain or deny outcome when its assumptions fail.

### Graph Hash

A digest identifying the graph state used to compute an ARCANA decision.

Graph hashes prevent decisions from being reused against incompatible graph states.

### Loss Model `L`

The model of impact or loss associated with unsafe outcomes.

`L` is separate from the propagation matrix `K`. Loss can represent operational, financial, privacy, compliance, safety, or reputational impact when those categories are in scope.

### Propagation Matrix `K`

A nonnegative matrix representing unsafe propagation pressure across an agentic capability graph over a declared decision horizon.

`K` must not contain loss, impact, business severity, or monetary values.

### Reason Code

A stable machine-readable outcome identifier explaining why ARCANA allowed, denied, constrained, escalated, or marked a decision as observe-only.

Reason codes must be granular. Distinct failure modes require distinct codes.

### Risk Context

A signed, hash-bound, or evidence-bound summary of ARCANA decision state.

Public risk context may include model version, calibration profile, decision horizon, graph hash, upper-bound estimates, verdict, controls, and autonomy budget.

### Risk Model Version

The identifier for the ARCANA model contract used to compute a decision.

Every decision, context, and certificate-like artifact must include a risk model version.

### Subcritical Under Model

A decision state where the upper-bound propagation risk satisfies the declared threshold under the specified ARCANA model, calibration profile, and decision horizon.

Subcritical under model is not a universal safety claim.

### Uncertainty Bounds

The lower, mean, and upper estimates attached to ARCANA risk values.

Admission-like decisions use upper bounds for risk. Control effectiveness should use conservative lower bounds when uncertain.

### Verdict

The decision category returned by ARCANA.

Public verdicts are:

```text
allow_bounded_autonomy
allow_with_controls
require_scope_reduction
require_human_gate
observe_only
deny
```

## Calibration Terms

### A0 - Heuristic / Demo Only

Calibration level for synthetic examples, tutorials, and demos.

A0 output must be marked non-certifiable.

### A1 - Static Conservative Prior

Calibration level based on static assumptions and conservative priors.

A1 must document assumptions and use conservative bounds.

### A2 - Empirical Calibration

Calibration level based on controlled experiments, red-team scenarios, adversarial replay, and test coverage.

A2 requires evidence IDs, coverage notes, sample sizes, segmentation, and known gaps.

### A3 - Runtime Bayesian Calibration

Calibration level using runtime-updated distributions with evidence segmentation, temporal decay, and conservative priors.

A3 must not treat lack of observed incidents as proof of low risk.

## Metric Terms

### `rho`

The spectral-radius style propagation-risk metric derived from `K`.

Public docs should distinguish `rho_lower`, `rho_mean`, `rho_upper`, and `rho_threshold`.

### `rho_upper`

The conservative upper estimate used for admission-like decisions.

### `delta_rho_upper`

The increase in upper-bound propagation risk caused by a proposed change.

### AaR

Autonomy-at-Risk. A loss-bound metric over the loss model `L`.

### AES

Agentic Expected Shortfall. A tail-loss metric over the loss model `L`.

## Reserved Or Private Vocabulary

The following categories are not part of the public ARCANA vocabulary unless separately released:

- private implementation internals;
- customer policy identifiers;
- customer telemetry names;
- commercial dashboard fields;
- support bundle mechanics;
- private lab workflow names;
- adapter-specific reason-code prefixes;
- local filesystem or provenance paths.

Use generic public terms such as enforcement system, adapter, evidence source, operation plan, capability envelope, and risk context.
