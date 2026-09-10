# ARCANA Roadmap v0.1 Public

> Product: ARCANA - Autonomy Risk Calculus for Agentic Network Assurance
> Status: active public roadmap v0.1, post-hardening repository edition
> Date: 2026-06-05
> Source: derived from the ARCANA internal roadmap, public PRD v0.2, and publication boundary review
> Classification: public-safe
> Implementation status: public model, schemas, standalone reference implementation, synthetic ARCANA-Bench, integration contract, and manuscript v1.0 are implemented and locally gated; empirical calibration evidence, production enforcement, and production certificate issuance are not present

## 1. Roadmap Rule

### Corrective Gate, 2026-09-10

R1 numerical/input correction described in
[Numerical Contract v1](NUMERICAL_CONTRACT_v1.md) is merged through PR #3.
R2 adds [installed-package portability](PACKAGE_PORTABILITY.md), complete
runtime provenance, [current-state navigation](PROJECT_STATUS.md) and the
[corrective reviewer packet](CORRECTIVE_REVIEW_PACKET.md). These are unreleased
corrections. Next: clean source freeze, exact-revision CI and independent R3
review before a separately authorized corrective release and manuscript update.
Do not reinterpret historical local gates as approval of these new changes.
Archival publication and production/empirical qualification remain separate.

ARCANA must progress in sequence:

```text
boundary -> PRD -> roadmap -> glossary/reason codes -> schemas -> formal model -> calibration -> FastGate -> reference implementation -> benchmark -> paper
```

No implementation work under `src/` should start until the publication boundary, public PRD, and public roadmap have been reviewed. The reference implementation must remain standalone, synthetic-fixture based, and free of private enterprise or lab dependencies.

## 2. Public Scope

This roadmap covers the public ARCANA research/reference track:

- public model documentation;
- public calibration methodology;
- public reason-code registry;
- public schema drafts;
- synthetic demos;
- standalone reference implementation;
- ARCANA-Bench public scenarios;
- whitepaper/paper artifacts.

This roadmap does not cover:

- production policy engines;
- customer telemetry or dashboards;
- commercial certificate issuance;
- private enterprise adapters;
- private capability-bound execution implementation details;
- private lab architecture or operational profiles.

## 3. Current Baseline

The repository baseline now contains:

- an active public PRD, roadmap, glossary, reason-code registry, and publication boundary;
- versioned public schemas with structural and semantic admission validation;
- a standalone typed reference implementation for graph, calibration, spectral,
  loss, decision, artifact, and FastGate contracts;
- deterministic synthetic examples, negative controls, and ARCANA-Bench v0.1;
- a public enforcement-neutral integration contract;
- a post-hardening public research manuscript v1.0;
- a hash-bound, venue-neutral LaTeX package with a pinned local toolchain;
- final license, contribution, security, limitations, release, and remote
  preflight documents;
- a live public remote with GitHub Private Vulnerability Reporting configured.

The current public release boundary is:

- final public claim-language review is closed for the v1.0 manuscript;
- venue-specific submission packaging remains separate from technical claim
  approval;
- the repository can support reproducible public research and reference-code
  review after its local release gate passes;
- the synthetic `public_benchmark` source class does not qualify an A2 profile;
- only reviewed, non-synthetic `empirical_public_benchmark`, controlled red-team,
  or adversarial replay evidence can satisfy the public A2 source-class rule;
- no public artifact demonstrates deployment-specific A2/A3 calibration;
- no public artifact authorizes production enforcement or certificate issuance;
- the venue-neutral LaTeX source is reproducible from the reviewed manuscript;
- generated PDF distribution, archive submission, and external peer review
  remain separate publication steps.

## 4. Milestone 0 - Boundary Freeze

Goal: make the public/private split explicit enough to prevent accidental disclosure or overclaiming.

Deliverables:

- publication boundary document;
- artifact classification table;
- public extraction checklist;
- claim discipline rules;
- schema, reason-code, certificate, CBE/AXCP, and lab-language boundaries.

Exit criteria:

- every existing artifact has a release class;
- no public artifact requires private implementation details;
- prohibited claims are documented;
- A0/demo output cannot be mistaken for production-grade certification.

Status: complete and maintained as the public release boundary.

## 5. Milestone 1 - Public PRD v0.2

Goal: define ARCANA as a public research/reference framework without relying on private enforcement systems.

Deliverables:

- public PRD v0.2;
- product boundary;
- problem statement;
- goals and non-goals;
- principal model objects;
- calibration levels;
- decision rule;
- FastGate requirements;
- public reason-code set;
- public demo and schema requirements.

Exit criteria:

- PRD is shareable with technical reviewers;
- PRD does not imply absolute safety;
- PRD does not imply production readiness;
- PRD does not disclose private enterprise or lab details;
- PRD blocks implementation until roadmap review.

Status: complete and active for the public research/reference track.

## 6. Milestone 2 - Public Roadmap v0.1

Goal: define the public execution order and review gates.

Deliverables:

- public roadmap v0.1;
- milestone sequencing;
- release gates;
- dependency rules;
- public/private integration boundary;
- risk register;
- first implementation entry criteria.

Exit criteria:

- reviewers can see what happens before code;
- public work is separable from private operationalization;
- reference implementation entry criteria are explicit;
- next artifacts are unambiguous.

Status: complete and active; subsequent work is governed by this sequence.

## 7. Milestone 3 - Public Glossary and Reason-Code Registry

Goal: stabilize public vocabulary before schemas and code.

Deliverables:

- public glossary;
- public reason-code registry;
- reason-code semantics;
- verdict vocabulary;
- calibration-level vocabulary;
- certificate vocabulary;
- reserved/private vocabulary list.

Required public reason-code families:

- calibration failures;
- unsupported model failures;
- malformed model input failures;
- stale or mismatched context failures;
- graph/evidence mismatch failures;
- decision-horizon mismatch failures;
- propagation-risk upper-bound failures;
- loss upper-bound failures;
- invalid loss model failures;
- budget exhaustion;
- FastGate uncertainty;
- FastGate vector invalidity;
- distillation risk;
- human-gate requirement;
- scope-reduction requirement;
- observe-only requirement.

Exit criteria:

- every reason code has one meaning;
- no generic catch-all denial is used for distinct failure modes;
- public reason codes are ARCANA-owned;
- private adapter reason-code mappings are excluded.

Implementation gate: schemas may not finalize before this registry exists.

Status: implemented and covered by public contract tests.

## 8. Milestone 4 - Public Schema Draft v0.2

Goal: define public machine-readable contracts without private implementation coupling.

Deliverables:

- `ARCANA_Context.schema.v0.2.json`;
- `ARCANA_Certificate.schema.v0.2.json`;
- `ARCANA_CalibrationProfile.schema.v0.2.json`;
- `ARCANA_BenchmarkScenario.schema.v0.2.json`;
- schema examples using synthetic fixtures;
- validation tests for required fields and rejection paths.

Required schema properties:

- public `$id` namespace;
- model version;
- calibration profile;
- decision horizon;
- uncertainty interval;
- evidence source or hash;
- verdict;
- reason codes;
- A0 non-certifiable marker where applicable.

Exit criteria:

- no internal URLs;
- no private policy profile names;
- no customer identifiers;
- no private adapter fields;
- no private lab fields;
- schema validation rejects missing mandatory certificate fields;
- schema validation rejects malformed reason codes.

Implementation gate: reference code may not emit certificates before schemas are reviewed.

Status: implemented with public IDs, examples, and validation tests.

## 9. Milestone 5 - Formal Model v0.2

Goal: make the mathematical contract precise enough for implementation and external review.

Deliverables:

- agentic capability graph definition;
- node and edge semantics;
- propagation matrix `K`;
- loss model `L`;
- decision horizon `H`;
- `K_lower`, `K_mean`, `K_upper`;
- subcritical-under-model decision rule;
- upper-bound enforcement rule;
- K/L separation examples;
- dimensional analysis notes.

Exit criteria:

- no dimensional ambiguity in `K`;
- loss is not embedded in `K`;
- decision horizons are mandatory;
- all certificate claims include model and calibration scope;
- all uncertainty-handling rules are explicit.

Implementation gate: spectral risk calculator should not be implemented before this model is reviewed.

Status: implemented as the public mathematical contract and reference behavior.

## 10. Milestone 6 - ARCANA-Cal v0.1

Goal: define calibration levels and evidence handling before any authoritative-looking output exists.

Deliverables:

- A0 heuristic/demo mode;
- A1 conservative static prior;
- A2 empirical/red-team calibration;
- A3 runtime Bayesian calibration;
- evidence quality rules;
- evidence segmentation rules;
- temporal decay rule;
- sparse-evidence fallback;
- non-certifiable output rules.

Exit criteria:

- A0 output is always marked non-certifiable;
- insufficient calibration has specific reason codes;
- sparse evidence widens uncertainty;
- unknown risk factors use conservative upper bounds;
- unknown controls use conservative lower bounds.

Implementation gate: certificate generation should not support non-demo outputs before calibration contracts are reviewed.

Status: implemented as a versioned public calibration contract; no production
calibration profile or deployment evidence is included.

## 11. Milestone 7 - ARCANA-FastGate v0.1

Goal: define low-latency admission semantics without weakening the mathematical gate.

Deliverables:

- cold/warm/hot path definitions;
- sparse perturbation model;
- Perron/Collatz upper-bound path;
- positive-vector method contract;
- SCC decomposition fallback;
- epsilon-floor fallback;
- component-local gate fallback;
- exact recompute fallback;
- uncertain result semantics.

Exit criteria:

- FastGate declares how the positive-vector requirement is satisfied;
- reducible graphs are handled explicitly;
- invalid vector state returns a specific reason code;
- uncertain fast path cannot silently allow;
- exact recompute fallback is specified.

Implementation gate: FastGate prototype should not start before this design is reviewed.

Status: implemented and post-hardening reviewed as a conservative reference
path; it is not a production latency or enforcement claim.

## 12. Milestone 8 - Reference Implementation v0.1

Goal: build a minimal standalone public implementation that reproduces the core ARCANA calculations.

Deliverables:

- graph model;
- calibration profile loader;
- spectral risk calculator;
- upper-bound decision evaluator;
- FastGate prototype;
- certificate generator;
- CLI demo;
- synthetic fixtures;
- unit tests.

Required implementation constraints:

- no private enterprise imports;
- no private lab imports;
- no network dependency for the demo;
- deterministic fixtures;
- explicit reason-code branches;
- typed data structures;
- validation before acting;
- no catch-all denial for distinct failure modes.

Exit criteria:

- reviewer can reproduce core calculations locally;
- every public reason code has a test;
- every required certificate field is validated;
- A0 demo certificate is marked non-certifiable;
- unsupported model, stale context, horizon mismatch, graph mismatch, threshold breach, calibration insufficiency, budget exhaustion, FastGate uncertainty, and invalid vector all have distinct paths.

Status: slices 0-5 implemented with typed contracts, explicit reason paths,
deterministic fixtures, and local validation gates.

## 13. Milestone 9 - ARCANA-Bench v0.1

Goal: demonstrate why autonomy risk accounting is different from task-success evaluation.

Deliverables:

- benchmark scenario schema;
- public-safe synthetic scenarios;
- prompt-injection scenario;
- memory-poisoning scenario;
- tool-misuse scenario;
- delegation-cascade scenario;
- benchmark-gaming scenario;
- dynamic-execution-risk scenario;
- negative-control fixture set for required fail-closed behavior;
- complete synthetic evaluator execution suite;
- deterministic evaluator runner and machine-readable run report;
- metrics and scoring notes.

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

Exit criteria:

- scenarios are synthetic or public-source safe;
- benchmark does not encode private customer, enterprise, or lab workflows;
- success rate is reported separately from unsafe action rate;
- risk-bound status is visible for each scenario;
- artifact-contract validity can be evaluated independently of task success;
- every required negative-control fixture is present and declares a non-allow-like expected outcome;
- every scenario has exactly one schema-valid, typed evaluator input;
- the actual public evaluator produces every observed outcome;
- verdict, ordered reason codes, and required controls compare exactly;
- reports expose metric provenance plus measured, not-measured, and unavailable states;
- source and report hashes verify deterministically;
- synthetic evaluator execution is not described as empirical system performance.

Status: executable synthetic scenario and negative-control suite implemented.
Repository publication requires the local gate and independent clean-source
reproduction; empirical system-performance claims remain prohibited.

## 14. Milestone 10 - Public Integration Contract v0.1

Goal: describe how ARCANA can integrate with enforcement systems without publishing private operational mechanics.

Deliverables:

- generic adapter contract;
- generic risk-context import/export shape;
- generic evidence-hash requirements;
- generic reason-code bridge guidance;
- public/private field separation;
- non-goals for enforcement.

Exit criteria:

- ARCANA remains enforcement-system neutral;
- private enterprise implementation is not disclosed;
- integration examples use synthetic or abstract fixtures;
- public fields are clearly separated from adapter-private fields.

Status: implemented and maintained as an enforcement-neutral public contract.

## 15. Milestone 11 - Whitepaper / Paper v0.2

Goal: produce a defensible publication artifact grounded in reviewed model, calibration, implementation, and benchmark results.

Deliverables:

- whitepaper v0.2;
- formal model section;
- calibration limitations section;
- FastGate section;
- benchmark section;
- reference implementation reproduction instructions;
- limitations and non-goals.

Exit criteria:

- no absolute-safety claim;
- calibration uncertainty is explicit;
- benchmark limitations are explicit;
- all certificate language is model-bounded;
- public artifact is ready for staged expert review.

Status: whitepaper/paper v1.0 public research manuscript and reproducible
venue-neutral LaTeX package implemented; final public claim-language review is
closed for the repository manuscript. The archival preprint package is bound
to DOI `10.5281/zenodo.21333463` and release `v0.1.1`. This is not external
academic peer review or venue acceptance.

## 16. Sequencing Gates

Hard gates:

- no reference implementation before public PRD, roadmap, formal model, calibration methodology, FastGate design, and implementation plan review;
- no certificate generator before public schemas exist;
- no non-demo certificate examples before calibration contract review;
- no FastGate prototype before FastGate design review;
- no whitepaper before reference implementation and benchmark evidence exist;
- no public release before boundary, license, contribution policy, security policy, and limitations document exist.

Release-readiness status:

- final file-scope license profile exists;
- contribution policy exists;
- security policy exists;
- active limitations document exists;
- public remote preflight checklist exists;
- GitHub Private Vulnerability Reporting is enabled for the public remote.

Review checkpoints:

1. Boundary + PRD + Roadmap.
2. Glossary + reason-code registry.
3. Schemas + formal model.
4. Calibration + FastGate.
5. Reference implementation + tests.
6. Benchmark + paper.

## 17. Risk Register

| Risk | Failure mode | Mitigation |
| --- | --- | --- |
| Public overclaim | ARCANA is described as proving safety. | Use model-bounded claim discipline and forbidden-claim review. |
| Calibration overconfidence | Weak evidence produces authoritative-looking certificates. | Mark A0 non-certifiable and require explicit evidence quality. |
| K/L confusion | Propagation risk is mixed with impact/loss. | Keep `K` and `L` separate in model, schema, examples, and tests. |
| FastGate false confidence | Fast path allows when assumptions fail. | Require positive-vector method, explicit fallback, and uncertain denial. |
| Private leakage | Public docs expose enterprise or lab mechanics. | Use publication classes and extraction checklist before release. |
| Reason-code collapse | Distinct failures share a generic denial. | Maintain stable granular public reason-code registry. |
| Demo misread as production | A synthetic demo appears deployable. | Label demos A0/non-certifiable and require synthetic fixtures. |
| Benchmark gaming | Task success hides unsafe behavior. | Score unsafe actions, containment, risk delta, and artifact-contract validity separately. |

## 18. Historical Implementation Entry Criteria

These criteria governed entry into `src/` implementation and are retained as
the historical gate:

- public boundary reviewed;
- public PRD v0.2 reviewed;
- public roadmap v0.1 reviewed;
- public glossary drafted;
- public reason-code registry drafted;
- public schemas have draft IDs and required fields;
- formal model draft exists for `K`, `L`, `H`, and upper-bound decisions;
- calibration methodology draft exists;
- FastGate design draft exists;
- implementation language and dependency policy are selected;
- tests are planned for every public reason code.

The first implementation slice should be:

1. typed graph and calibration data structures;
2. schema validation;
3. spectral risk calculator;
4. decision evaluator with explicit reason-code branches;
5. A0 demo certificate generator marked non-certifiable;
6. deterministic CLI demo with synthetic fixtures.

## 19. Next Artifacts

1. Reproduce the venue-neutral LaTeX/PDF package from an immutable local commit.
2. Publish only that reviewed public commit, then repeat the full gate from a
   fresh clone of the public remote before tagging the research release.
3. Obtain external technical review and record unresolved limitations.
4. Prepare venue/archive metadata without changing the approved claim boundary.
5. Keep deployment calibration, enforcement activation, and certificate
   issuance outside this public roadmap and subject to separate production
   governance.
