# ARCANA Public Demo and Reference Implementation Plan v0.1

> Status: public implementation plan v0.1 draft
> Scope: local-first public demo and standalone reference implementation plan
> Implementation status: Slice 5 FastGate prototype may exist after review; ARCANA-Bench expansion is not approved by this document

This document defines the first public ARCANA demo and reference implementation plan. It selects the implementation language, dependency policy, module boundaries, synthetic fixture strategy, CLI behavior, and test matrix required before code begins.

The implementation described here is a public reference implementation. It is not a production policy engine, commercial certificate issuer, sandbox, enforcement boundary, or private adapter.

## 1. Roadmap Position

This plan follows:

```text
boundary -> PRD -> roadmap -> glossary/reason codes -> schemas -> formal model -> calibration -> FastGate -> implementation plan
```

The next roadmap step after this plan is reviewed is:

```text
reference implementation v0.1
```

No implementation under `src/` should start until this plan is reviewed.

## 2. Goals

The first public implementation must:

- load synthetic public fixtures;
- validate schema-shaped inputs;
- construct typed graph, horizon, calibration, and loss objects;
- validate `K_lower`, `K_mean`, and `K_upper` invariants;
- compute upper-bound propagation risk;
- evaluate decision rules with explicit reason-code branches;
- support exact recompute before FastGate;
- support FastGate only after exact path tests pass;
- emit A0 demo certificates marked non-certifiable;
- run entirely locally without network access;
- avoid private enterprise, customer, adapter, or lab dependencies.

## 3. Non-Goals

The first public implementation must not:

- claim absolute safety;
- issue production-grade certificates;
- integrate with private enforcement systems;
- import private repositories;
- depend on private telemetry;
- use customer or private lab fixtures;
- create a GitHub remote or paid hosted workflow;
- hide distinct failures behind a generic denial;
- optimize runtime before admission semantics are correct.

## 4. Implementation Language

The reference implementation should use:

```text
Python 3.11+
```

Rationale:

- existing public audit and schema tooling already use Python;
- local-first execution is simple;
- deterministic CLI demos are easy to reproduce;
- test coverage can be strict without hosted infrastructure;
- typed dataclasses and explicit enums fit the reason-code contract.

Planned package layout:

```text
src/arcana/
  __init__.py
  model.py
  calibration.py
  matrices.py
  loss.py
  decision.py
  fastgate.py
  certificate.py
  schemas.py
  demo.py
  errors.py
```

Planned test layout:

```text
tests/
  test_model_validation.py
  test_calibration_validation.py
  test_matrix_validation.py
  test_loss_validation.py
  test_decision_reason_codes.py
  test_fastgate.py
  test_certificate_emission.py
  test_cli_demo.py
```

## 5. Dependency Policy

Runtime dependencies should be explicit and minimal.

Planned runtime dependencies:

| Dependency | Purpose | Policy |
| --- | --- | --- |
| `numpy` | Matrix operations and spectral radius calculation. | Required for v0.1 numeric correctness. |
| `jsonschema` | Draft 2020-12 schema validation. | Required for validating public schemas beyond the current local structural gate. |

Planned development dependencies:

| Dependency | Purpose | Policy |
| --- | --- | --- |
| `pytest` | Unit and CLI tests. | Required for local test gate. |

Dependency rules:

- dependencies must be declared in `pyproject.toml`;
- dependency versions should be pinned or bounded before public remote release;
- runtime must not require network access;
- examples and tests must use committed synthetic fixtures;
- no hosted CI is required for v0.1;
- no optional fallback may silently weaken validation or numerical behavior.

The current `make check` gate remains mandatory. A later implementation phase may add:

```text
make test
make demo
```

## 6. Public Fixture Strategy

All fixtures must be synthetic or public-source safe.

Planned fixture classes:

```text
examples/graphs/*.synthetic.json
examples/deltas/*.synthetic.json
examples/outputs/*.synthetic.json
```

Initial demo fixtures:

| Fixture | Purpose |
| --- | --- |
| synthetic graph with agent, tool, memory, gate, and external nodes | Demonstrate graph construction and `K` generation. |
| synthetic sparse delta adding a risky tool edge | Demonstrate `DeltaK_upper` and budget use. |
| A0 calibration profile | Demonstrate non-certifiable output. |
| A1 static prior profile | Demonstrate allow-with-controls context shape. |
| toy loss model | Demonstrate K/L separation. |

Fixture rules:

- every graph has a deterministic graph hash;
- every delta has a deterministic delta hash;
- every fixture declares decision horizon;
- every fixture declares synthetic evidence;
- no fixture encodes private operational workflows.

## 7. Demo Behavior

The first public demo should run locally as:

```text
python -m arcana.demo --scenario synthetic_prompt_injection
```

Expected demo flow:

1. Load public synthetic fixtures.
2. Validate risk model version.
3. Validate calibration profile.
4. Validate decision horizon compatibility.
5. Validate graph hash binding.
6. Validate `K_lower`, `K_mean`, and `K_upper`.
7. Validate loss model when loss is in scope.
8. Compute `rho_upper`.
9. Evaluate budget.
10. Evaluate decision rule.
11. Optionally evaluate FastGate in observe-only or exact mode.
12. Emit a risk context.
13. Emit an A0 non-certifiable demo certificate.

The demo must print or write clearly labeled artifacts:

```text
arcana.context.v0.2
arcana.certificate.v0.2
```

A0 certificate output must include:

```text
certification_status = non_certifiable
ARCANA_INFO_A0_NON_CERTIFIABLE
ARCANA_INFO_SYNTHETIC_FIXTURE
```

## 8. Typed Model Contracts

The first implementation should define typed structures for:

- decision horizon;
- graph node;
- graph edge;
- graph state;
- graph delta;
- calibration profile;
- evidence reference;
- uncertainty interval;
- propagation matrix bundle;
- loss bounds;
- autonomy budget;
- FastGate context;
- decision result;
- certificate artifact.

Typed structures must validate preconditions before calculations.

Invalid model inputs return:

```text
ARCANA_DENY_MODEL_INPUT_INVALID
```

unless a more specific reason code applies.

## 9. Numerical Correctness Plan

The spectral calculator must operate on nonnegative square matrices only.

Validation requirements:

- matrix is square;
- all entries are finite numbers;
- all entries are nonnegative;
- interval order satisfies `lower <= mean <= upper`;
- row and column order is bound to graph hash;
- thresholds are finite and nonnegative.

Cold path calculation:

```text
rho_upper = spectral_radius(K_upper)
```

The implementation should use `numpy.linalg.eigvals` for v0.1 cold-path spectral radius, then validate:

- result is finite;
- imaginary residual is within tolerance for real-valued nonnegative input;
- computed `rho_upper` is compared against threshold using declared tolerance;
- near-bound cases do not allow without margin.

FastGate warm path must use the Collatz-Wielandt bound defined in `FASTGATE_DESIGN_v0.1.md`.

## 10. Decision Evaluator Plan

The decision evaluator should run ordered validation:

1. Risk model version.
2. Model input shape.
3. Decision horizon.
4. Context freshness.
5. Graph hash binding.
6. Calibration profile and required level.
7. Matrix interval invariants.
8. Loss model if in scope.
9. Autonomy budget.
10. `rho_upper`.
11. Loss upper bounds.
12. FastGate if requested.
13. Verdict and reason codes.

Every branch must return a typed result:

```text
DecisionResult(
  verdict,
  reason_codes,
  metrics,
  required_controls,
  caveats
)
```

No branch may return an allow-like verdict after a failed required validation.

## 11. Certificate Emission Plan

Certificate emission starts only after:

- schema validation exists;
- A0 non-certifiable behavior is tested;
- reason-code tests pass;
- K/L separation tests pass;
- FastGate fields are schema-validated.

The first certificate generator emits only:

```text
demo_non_certifiable_certificate
```

Non-demo certificate output is deferred until calibration contracts and test coverage are reviewed with at least A2 public evidence fixtures.

## 12. FastGate Implementation Plan

FastGate implementation should be staged after exact recompute.

Required stages:

1. `exact_recompute` mode.
2. Sparse delta validation.
3. Positive-vector validation.
4. `perron_collatz_bound` calculation.
5. Numerical margin enforcement.
6. SCC decomposition support.
7. Epsilon-floor support.
8. Component-local gate support.
9. Exact fallback.
10. Certificate/context FastGate field emission.

FastGate cannot produce `allow_bounded_autonomy` when:

- positive vector is invalid;
- graph is reducible without declared handling;
- upper bound margin is insufficient;
- context is stale;
- exact fallback is required but unavailable.

## 13. Reason-Code Test Matrix

Every public reason code requires at least one local test.

| Reason code | Required test case |
| --- | --- |
| `ARCANA_ALLOW_BOUNDED_AUTONOMY` | Exact path passes all constraints without extra controls. |
| `ARCANA_ALLOW_WITH_CONTROLS` | Upper bounds pass only when required controls are present. |
| `ARCANA_DENY_CALIBRATION_INSUFFICIENT` | Requested action requires stronger calibration than provided. |
| `ARCANA_DENY_RISK_MODEL_UNSUPPORTED` | Missing, malformed, or unsupported risk model version. |
| `ARCANA_DENY_MODEL_INPUT_INVALID` | Non-square matrix, negative entry, invalid interval, or malformed delta. |
| `ARCANA_DENY_CONTEXT_STALE` | Context or calibration evidence is outside freshness window. |
| `ARCANA_DENY_GRAPH_HASH_MISMATCH` | Bound graph hash differs from current graph hash. |
| `ARCANA_DENY_DECISION_HORIZON_MISMATCH` | Graph, calibration, context, and request horizons differ. |
| `ARCANA_DENY_RHO_UPPER_BOUND` | `rho_upper` exceeds threshold. |
| `ARCANA_DENY_AAR_UPPER_BOUND` | `AaR_99_upper` exceeds configured limit. |
| `ARCANA_DENY_LOSS_MODEL_INVALID` | Loss in scope but bounds are missing, malformed, or horizon-incompatible. |
| `ARCANA_DENY_AES_UPPER_BOUND` | `AES_99_upper` exceeds configured limit. |
| `ARCANA_DENY_BUDGET_EXHAUSTED` | `delta_rho_upper` or resource counter exceeds budget. |
| `ARCANA_DENY_FASTGATE_UNCERTAIN` | Valid fast path cannot prove sufficient margin. |
| `ARCANA_DENY_FASTGATE_VECTOR_INVALID` | Missing method, nonpositive vector entry, invalid SCC handling, or invalid epsilon floor. |
| `ARCANA_DENY_DISTILLATION_RISK` | Distillation requested with insufficient evidence, unstable operation, missing invalidation, or weak calibration. |
| `ARCANA_REQUIRE_HUMAN_GATE` | Impact or policy class requires approval despite bounded computed risk. |
| `ARCANA_REQUIRE_SCOPE_REDUCTION` | Reducing capability envelope or edge set can bring upper bound under threshold. |
| `ARCANA_REQUIRE_OBSERVE_ONLY` | A0 or weak evidence supports evaluation but not admission. |
| `ARCANA_INFO_A0_NON_CERTIFIABLE` | A0 certificate always includes non-certifiable info code. |
| `ARCANA_INFO_SYNTHETIC_FIXTURE` | Synthetic examples and outputs always include synthetic-fixture info code. |

Tests must assert both verdict and reason codes.

## 14. CLI Test Matrix

The CLI tests should cover:

- default synthetic demo succeeds;
- JSON output is parseable;
- emitted context validates against schema;
- emitted certificate validates against schema;
- A0 certificate is non-certifiable;
- malformed fixture path fails with a specific reason code;
- unsupported model fixture fails with `ARCANA_DENY_RISK_MODEL_UNSUPPORTED`;
- stale context fixture fails with `ARCANA_DENY_CONTEXT_STALE`;
- FastGate invalid-vector fixture fails with `ARCANA_DENY_FASTGATE_VECTOR_INVALID`;
- no command requires network access.

## 15. Local Gate Plan

Current gate:

```text
make check
```

Planned implementation gate:

```text
make check
make test
make demo
```

`make check` remains the publication-boundary and schema gate.

`make test` should run unit tests.

`make demo` should run the deterministic synthetic demo and validate emitted artifacts.

## 16. Publication Discipline

Before any public remote push:

- all files are listed in `PUBLIC_MANIFEST.md`;
- `make check` passes;
- implementation tests pass locally;
- no private paths or private mechanics are present;
- examples are synthetic or public-source safe;
- no hosted CI or paid GitHub feature is required;
- no A0 output can be mistaken for certifiable bounded autonomy.

The remote repository remains a publication channel, not the development authority.

## 17. Implementation Slices

### Slice 0 - Project Scaffold

Deliverables:

- `pyproject.toml`;
- `src/arcana/` package skeleton;
- `tests/` package;
- dependency declaration;
- `make test` target.

Exit criteria:

- package imports locally;
- no private imports;
- `make check` still passes;
- an empty test run is not accepted as completion.

### Slice 1 - Typed Contracts and Schema Validation

Deliverables:

- typed model objects;
- reason-code enum;
- verdict enum;
- schema validation wrapper;
- fixture loader.

Exit criteria:

- required fields are validated;
- schema examples pass;
- malformed fixture tests fail with specific reason codes.

Status: implemented, review pending.

### Slice 2 - Matrix and Spectral Calculator

Deliverables:

- matrix validation;
- interval validation;
- spectral radius calculator;
- tolerance policy.

Exit criteria:

- nonnegative matrix tests pass;
- malformed matrix tests return `ARCANA_DENY_MODEL_INPUT_INVALID`;
- near-threshold tests do not allow without margin.

Status: implemented, review pending.

### Slice 3 - Decision Evaluator

Deliverables:

- ordered decision evaluator;
- budget validation;
- loss-bound validation;
- required-control handling.

Exit criteria:

- every deny reason code has a test;
- allow, allow-with-controls, observe-only, human-gate, and scope-reduction verdicts are tested.

Status: implemented, review pending.

### Slice 4 - Certificate and Demo Output

Deliverables:

- risk context emitter;
- A0 certificate emitter;
- demo CLI;
- output validation.

Exit criteria:

- emitted context validates;
- emitted certificate validates;
- A0 output is non-certifiable.

Status: implemented, review pending.

### Slice 5 - FastGate Prototype

Deliverables:

- exact recompute mode;
- sparse delta validation;
- Collatz bound;
- positive-vector validation;
- fallback handling.

Exit criteria:

- exact path tests pass before warm path tests;
- invalid vector and uncertain fast path return distinct reason codes;
- FastGate fields validate in context and certificate outputs.

Status: implemented, review pending.

## 18. Review Gate Before Code

Before starting Slice 0, reviewers should confirm:

- Python 3.11+ is acceptable;
- `numpy`, `jsonschema`, and `pytest` are acceptable dependencies;
- public fixtures remain synthetic;
- no remote GitHub workflow is needed;
- the reason-code test matrix is complete enough for v0.1;
- A0 output remains non-certifiable;
- non-demo certificates remain deferred.

## 19. Open Questions

- Should `jsonschema` be runtime-required or dev-only after schema validation stabilizes?
- Should `numpy.linalg.eigvals` be replaced by a bounded nonnegative-matrix method in v0.2?
- Should `make demo` write outputs under `examples/outputs/` or a temporary ignored runtime folder?
- Should the first A1 demo emit `allow_with_controls` only, keeping `allow_bounded_autonomy` as a unit-test fixture?
- Should distillation tests be included in v0.1 implementation or deferred to ARCANA-Bench?

## 20. Next Phase

After Slice 5 is reviewed, the next roadmap phase is:

```text
ARCANA-Bench v0.1 scenario expansion
```
