# ARCANA Whitepaper / Paper v0.2 Outline

> Status: public whitepaper/paper outline v0.2 draft
> Scope: staged expert-review outline for the public ARCANA research/reference track
> Classification: public-safe draft; not a final manuscript
> Implementation status: outline only; no production claim

This document defines the structure and claim discipline for a future ARCANA whitepaper or paper.

The paper must describe ARCANA as model-bounded autonomy accounting for agentic systems. It must not present ARCANA as a proof of absolute safety, a production enforcement system, a sandbox, a policy engine, or a production certificate issuer.

## 1. Paper Rule

The paper may claim:

```text
ARCANA estimates bounded autonomy under explicit risk model versions, calibration profiles, decision horizons, uncertainty bounds, and evidence assumptions.
```

The paper must preserve these boundaries:

- propagation risk is separate from loss and impact;
- every decision is horizon-bound;
- every certificate-like artifact is model-bounded;
- A0 outputs are non-certifiable;
- weak, stale, missing, or incompatible evidence widens uncertainty or blocks admission-like claims;
- FastGate is an optimization path, not a weaker decision rule;
- benchmark task success is separate from unsafe action rate and certificate validity;
- public examples use synthetic or public-source-safe evidence only;
- integration guidance remains enforcement-neutral.

## 2. Working Title and Thesis

Working title:

```text
ARCANA: Model-Bounded Autonomy Accounting for Agentic Systems
```

Working thesis:

```text
Agentic systems need explicit accounting for autonomy risk across operations, delegation, tools, memory, grants, and distillation. ARCANA provides a public model for bounding propagation risk under declared calibration, horizon, uncertainty, and evidence assumptions.
```

The thesis is intentionally limited. It does not claim universal safety, operational approval, or production certification.

## 3. Target Reader and Review Purpose

Primary readers:

- AI safety researchers evaluating formal assumptions;
- autonomous-agent engineers evaluating reproducibility;
- security engineers evaluating failure modes and evidence binding;
- governance reviewers evaluating certificate-like language;
- benchmark designers separating task success from autonomy risk.

Review purpose:

- check the mathematical contract for dimensional correctness;
- check calibration uncertainty and evidence-quality limits;
- check reason-code granularity and fail-closed behavior;
- check whether benchmark claims are measured separately from task success;
- check that public integration language does not disclose private operational mechanics.

## 4. Claimed Contributions

The paper should frame contributions as public research/reference artifacts:

| Contribution | Source artifact | Claim boundary |
| --- | --- | --- |
| Autonomy capability graph | `docs/FORMAL_MODEL_v0.2.md` | Model object, not full system truth. |
| Propagation matrix `K` | `docs/FORMAL_MODEL_v0.2.md` | Propagation risk only; no embedded loss. |
| Loss model `L` | `docs/FORMAL_MODEL_v0.2.md` | Impact model kept separate from propagation. |
| Upper-bound decision rule | `docs/FORMAL_MODEL_v0.2.md` and `docs/REASON_CODES.md` | Admission-like decisions use upper bounds. |
| Calibration levels A0-A3 | `docs/CALIBRATION_METHODOLOGY_v0.1.md` | Calibration strength is explicit and limited. |
| FastGate | `docs/FASTGATE_DESIGN_v0.1.md` | Conservative optimization with exact fallback. |
| ARCANA-Bench | `docs/ARCANA_BENCH_v0.1.md` | Synthetic scenario suite, not production evaluation. |
| Public reference implementation | `src/arcana/` and `tests/` | Reproducible local reference, not production runtime. |
| Public integration contract | `docs/PUBLIC_INTEGRATION_CONTRACT_v0.1.md` | Enforcement-neutral import/export guidance. |

## 5. Proposed Paper Structure

### 5.1 Abstract

The abstract should state:

- the problem is autonomy accounting for agentic systems;
- ARCANA estimates whether a proposed operation remains within a bounded risk envelope;
- the envelope is defined by model version, calibration profile, decision horizon, uncertainty bounds, and evidence assumptions;
- the public reference implementation and benchmarks use synthetic fixtures;
- limitations and non-goals are central to the result.

The abstract must not use certificate language unless it is explicitly model-bounded and calibration-scoped.

### 5.2 Introduction

The introduction should motivate why task success is insufficient for agentic systems.

Required points:

- agentic systems can route unsafe instructions, delegate, misuse tools, poison memory, game benchmarks, or create dynamic execution risk;
- these failures can occur even when the requested task appears successful;
- an autonomy accounting layer should expose risk envelope, uncertainty, evidence, and reason codes;
- public ARCANA is a research/reference framework.

### 5.3 Problem Statement

Define the input question:

```text
Given a proposed operation, graph state, calibration profile, decision horizon, and evidence bundle, does the proposed action remain within the declared bounded-risk envelope?
```

Required distinctions:

- proposed operation vs local policy decision;
- propagation risk vs loss;
- model-bounded estimate vs operational truth;
- certificate-like artifact vs production authorization.

### 5.4 Formal Model

This section should summarize:

- agentic capability graph `G_t = (V_t, E_t)`;
- public node classes;
- decision horizon `H`;
- edge factor model;
- propagation matrix `K`;
- uncertainty matrices `K_lower`, `K_mean`, `K_upper`;
- spectral radius `rho(K)`;
- upper-bound decision metric `rho_upper`;
- subcritical-under-model interpretation;
- separate loss model `L`;
- Autonomy-at-Risk and Agentic Expected Shortfall as loss-side measures.

Non-negotiable rule:

```text
K describes unsafe propagation pressure; L describes impact. The paper must not merge them.
```

### 5.5 Calibration Methodology and Limitations

This section should summarize:

- calibration profile contract;
- A0, A1, A2, and A3 levels;
- evidence source classes;
- evidence quality dimensions;
- sparse-evidence behavior;
- temporal decay and staleness;
- conservative defaults for unknown risk factors and controls;
- calibration insufficiency reason codes.

Required limitation:

```text
Calibration uncertainty is a first-class limitation, not an appendix caveat.
```

A0 must be described as demo-only and non-certifiable.

The paper should also state that A1 is not a commercial certificate basis in
the public track, A2 is conditional on separate empirical review, and A3 is a
runtime-calibration design target unless separately reviewed with segmented
runtime evidence.

### 5.6 Decision Semantics and Reason Codes

This section should show how model outputs become explicit verdicts:

- `allow_bounded_autonomy`;
- `allow_with_controls`;
- `require_scope_reduction`;
- `require_human_gate`;
- `observe_only`;
- `deny`.

Reason-code requirements:

- every distinct failure mode has a distinct reason code;
- missing input, stale context, graph mismatch, calibration gap, threshold breach, loss-model invalidity, budget exhaustion, FastGate uncertainty, and invalid vectors are not collapsed;
- allow-like results require compatible model, calibration, horizon, graph, uncertainty, evidence, threshold, budget, and controls.

### 5.7 Certificate-Like Artifacts

This section should describe certificate-like artifacts as bounded, schema-shaped outputs.

Required fields:

- model version;
- calibration profile;
- calibration level;
- decision horizon;
- uncertainty bounds;
- evidence source or hash;
- verdict;
- reason codes;
- caveats;
- expiry when applicable.

Required boundary:

```text
A0 artifacts are non-certifiable and cannot support production certificate issuance.
```

Additional boundary:

```text
Public certificate-like examples demonstrate schema and reasoning contracts;
they do not authorize production certificate issuance.
```

### 5.8 FastGate

This section should explain FastGate as a conservative optimization.

Required points:

- exact decision condition remains `rho(K_after_upper) < theta_rho`;
- FastGate may allow only when its conservative bound proves the same condition;
- Collatz-Wielandt or exact recompute assumptions must be declared;
- reducible graphs require explicit handling;
- invalid positive-vector state returns a vector-specific denial;
- inconclusive fast path returns uncertainty or exact recompute, not silent admission.

### 5.9 ARCANA-Bench

This section should explain why the benchmark separates task success from risk accounting.

Required scenario classes:

- indirect prompt injection containment;
- persistent memory poisoning containment;
- tool misuse scope reduction;
- unsafe delegation cascade;
- benchmark gaming detection;
- dynamic execution risk.

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
certificate_validity_rate
```

The paper must state that benchmark task success is not an ARCANA safety score.

### 5.10 Reference Implementation Reproduction

This section should give local reproduction commands:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
make check
make test
make demo
```

Required reproduction claims:

- the demo is deterministic;
- fixtures are synthetic;
- schema validation is part of the gate;
- public-boundary audit is part of the gate;
- unit tests cover explicit reason-code and validation paths;
- no network dependency is required for the demo.

### 5.11 Public Integration Contract

This section should summarize enforcement-neutral integration:

- ARCANA exports model-bounded risk artifacts;
- surrounding systems decide local policy actions;
- original ARCANA reason codes must be preserved;
- evidence hash and source binding must be preserved;
- public fields and integration-private fields stay separated;
- stale, mismatched, unsupported, or uncertain artifacts require recompute or rejection.

The paper must not disclose private adapter mechanics.

### 5.12 Limitations and Non-Goals

Required limitations:

- ARCANA is model-bounded;
- calibration can be wrong, stale, sparse, or incomplete;
- synthetic benchmarks do not prove production behavior;
- A0 output is non-certifiable;
- FastGate relies on declared assumptions and valid fallback paths;
- a valid ARCANA artifact is not a substitute for local policy;
- public examples do not represent customer, enterprise, or private lab deployments;
- certificate-like language is scoped to model, calibration, horizon, uncertainty, and evidence.

Required non-goals:

- no production enforcement implementation;
- no private policy engine;
- no customer telemetry pipeline;
- no commercial certificate issuance;
- no production dashboard;
- no universal safety claim.

## 6. Evidence Table for v0.2

| Paper section | Evidence source | Current status | Review gap |
| --- | --- | --- | --- |
| Formal model | `docs/FORMAL_MODEL_v0.2.md` | Draft exists. | External mathematical review needed. |
| Calibration | `docs/CALIBRATION_METHODOLOGY_v0.1.md` | Draft exists. | Evidence-quality and level semantics review needed. |
| Reason codes | `docs/REASON_CODES.md` | Registry exists. | Stability review before public release. |
| Schemas | `schemas/` and `examples/` | Drafts and synthetic examples exist. | Public schema review needed. |
| FastGate | `docs/FASTGATE_DESIGN_v0.1.md` and `src/arcana/fastgate.py` | Design and prototype exist. | Numerical and graph-edge-case review needed. |
| Benchmark | `docs/ARCANA_BENCH_v0.1.md` and `examples/benchmark_*.synthetic.json` | Synthetic suite exists. | Scenario coverage and metric review needed. |
| Reference implementation | `src/arcana/` and `tests/` | Local tests pass. | Independent reproduction needed. |
| Integration | `docs/PUBLIC_INTEGRATION_CONTRACT_v0.1.md` | Draft exists. | Boundary review needed. |

## 7. Required Figures and Tables

Planned figures:

- agentic capability graph with public node classes;
- propagation matrix and uncertainty interval diagram;
- K/L separation diagram;
- decision flow from validation to verdict;
- FastGate exact/warm/hot path diagram;
- benchmark score separation diagram.

Planned tables:

- calibration levels A0-A3;
- reason-code families;
- required certificate-like fields;
- ARCANA-Bench scenario classes;
- reproduction command checklist;
- limitations and non-goals.

Figures must use synthetic or abstract examples only.

## 8. Publication Readiness Gate

The outline can become a paper draft only after:

- public-boundary audit passes;
- schema validation passes;
- tests pass locally;
- demo output remains deterministic and synthetic;
- no claim implies absolute safety, production readiness, or production certification;
- A0 remains visibly non-certifiable;
- limitations section is present before any release candidate;
- release-readiness documents exist: license, contribution policy, security policy, and limitations document.

## 9. Reviewer Checklist

Reviewers should be able to answer:

- Does every claim name its model, calibration, horizon, uncertainty, and evidence scope?
- Does the paper avoid treating `rho_mean` as an admission metric?
- Does the paper keep `K` and `L` separate?
- Does calibration uncertainty affect outcomes rather than only prose?
- Does FastGate fail closed when assumptions fail?
- Does ARCANA-Bench separate task success, unsafe actions, risk-bound status, and certificate validity?
- Are A0 artifacts marked non-certifiable?
- Are private operational mechanics absent?
- Are integration examples synthetic or abstract?
- Are limitations and non-goals stated before publication?
