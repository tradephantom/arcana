# ARCANA Public Integration Contract v0.1

> Status: public integration contract v0.1 draft
> Scope: generic import/export and reason-code bridge for public ARCANA artifacts
> Classification: public-safe draft; enforcement-neutral
> Implementation status: documentation contract only

This document defines how a surrounding system can consume ARCANA outputs without depending on private operational mechanics.

ARCANA remains an autonomy accounting layer. It exports model-bounded risk accounting artifacts. It is not the enforcement boundary, policy engine, sandbox, telemetry system, production certificate issuer, or proof of absolute safety.

## 1. Contract Rule

An integration may use ARCANA outputs only as model-bounded risk accounting artifacts.

Every integration must preserve:

- schema version;
- risk model version;
- calibration profile;
- calibration level;
- decision horizon;
- graph hash;
- uncertainty interval;
- evidence reference or evidence hash;
- verdict;
- reason codes;
- required controls when present;
- A0 non-certifiable marker when applicable.

The surrounding system decides whether to enforce, admit, deny, reduce scope, observe, or escalate. ARCANA does not publish enforcement mechanics and does not turn a local enforcement decision into an ARCANA safety claim.

No integration may convert an ARCANA result into an absolute-safety claim, a production certification claim, or a claim that risk was eliminated.

## 2. Public Roles

ARCANA defines abstract public roles. These names are contract roles, not implementation names.

| Role | Responsibility | Public contract surface |
| --- | --- | --- |
| ARCANA evaluator | Computes model-bounded autonomy risk. | Public schemas, typed reference implementation, reason codes. |
| Generic integration surface | Imports ARCANA artifacts and passes them to surrounding systems. | Public import/export shapes in this document. |
| Generic policy layer | Decides local action after ARCANA validation succeeds. | Local policy outside ARCANA. |
| Evidence store or source | Provides evidence reference or hash binding. | `EvidenceReference` fields and hash requirements. |
| Reviewer or operator | Reviews human-gate, scope-reduction, or observe-only outcomes. | Public verdict and reason-code summary. |

The policy layer may enforce decisions. ARCANA does not specify how enforcement is implemented.

## 3. Public Artifact Import

A generic integration request should provide enough public data to validate provenance, compatibility, and decision scope before any local policy action occurs.

```json
{
  "risk_model_version": "arcana.risk.v0.2",
  "calibration_profile_id": "arcana.cal.example_profile",
  "decision_horizon": {
    "id": "example_horizon",
    "duration_seconds": 300,
    "context": "synthetic integration example"
  },
  "graph_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "evidence": {
    "source_type": "synthetic_fixture",
    "source_id": "public-integration-example-001",
    "evidence_hash": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "synthetic": true
  }
}
```

The request may also include public model inputs such as matrix bundles, autonomy budgets, loss bounds, FastGate context, and synthetic scenario references.

The importer must validate:

- supported schema version where the request is schema-shaped;
- supported risk model version;
- calibration profile identifier;
- calibration level when present;
- decision horizon identifier and duration;
- graph hash format and binding;
- evidence source, source identifier, evidence hash, and synthetic marker;
- reason codes when importing an existing ARCANA artifact;
- freshness and expiry fields when present.

The request must not include credentials, private execution traces, customer identifiers, raw sensitive evidence, private policy tables, local enforcement secrets, or private deployment URLs.

## 4. Risk Context Export Shape

ARCANA exports public schema-shaped artifacts:

- `arcana.context.v0.2`;
- `arcana.certificate.v0.2`;
- `arcana.calibration_profile.v0.2`;
- `arcana.benchmark_scenario.v0.2`.

A generic risk-context export contains:

```json
{
  "schema_version": "arcana.context.v0.2",
  "risk_model_version": "arcana.risk.v0.2",
  "calibration_profile_id": "arcana.cal.example_profile",
  "calibration_level": "A0",
  "decision_horizon": {
    "id": "example_horizon",
    "duration_seconds": 300,
    "context": "synthetic integration example"
  },
  "graph_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "rho_interval": {
    "lower": 0.2,
    "mean": 0.5,
    "upper": 0.9,
    "threshold": 0.8
  },
  "loss_bounds": {
    "aar_99_upper": 0.0,
    "aes_99_upper": 0.0,
    "max_allowed_aar_99": 0.0,
    "max_allowed_aes_99": 0.0
  },
  "fastgate": {
    "mode": "observe_only"
  },
  "decision": "observe_only",
  "reason_codes": [
    "ARCANA_REQUIRE_OBSERVE_ONLY",
    "ARCANA_INFO_A0_NON_CERTIFIABLE",
    "ARCANA_INFO_SYNTHETIC_FIXTURE"
  ],
  "required_controls": [
    "human_review_before_admission"
  ],
  "evidence": {
    "source_type": "synthetic_fixture",
    "source_id": "public-integration-example-001",
    "evidence_hash": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "synthetic": true
  },
  "autonomy_budget": {
    "max_delta_rho_upper": 0.05,
    "expires_at": "2026-06-09T00:05:00Z"
  }
}
```

Consumers must validate exported artifacts against the public schema before using them. Unknown fields must not be interpreted as local policy instructions unless a separate integration-private contract authorizes them outside the ARCANA artifact.

## 5. Certificate Import and Export Shape

Certificate-like artifacts are stricter than risk contexts because they can be misread as authority claims.

The public reference implementation currently permits A0 demo output only. A0 output is non-certifiable and must preserve `ARCANA_INFO_A0_NON_CERTIFIABLE`.

Certificate importers must validate:

- `schema_version`;
- `certificate_id`;
- `certificate_type`;
- `risk_model_version`;
- `calibration_profile.profile_id`;
- `calibration_profile.level`;
- `decision_horizon`;
- `graph_hash`;
- `issued_at`;
- `expires_at` when present;
- `evidence`;
- `reason_codes`;
- caveats or limitations.

Certificate exporters must not emit a certifiable production artifact from A0 calibration. Non-demo certificate issuance is outside this public contract until stronger public calibration and evidence requirements are reviewed.

## 6. Evidence Hash Requirements

Evidence references must be explicit enough to bind the result without publishing private evidence.

Requirements:

- `source_type` must be a public schema value;
- `source_id` must be stable within the public or local evidence namespace;
- `evidence_hash`, when present, must use `sha256:<64 hex chars>`;
- the canonicalization method used before hashing must be declared by the producer;
- `synthetic` must be true for public examples and fixtures;
- stale, missing, or mismatched evidence must not be treated as bounded autonomy.

The evidence hash binds an artifact to evidence. It does not prove evidence quality by itself.

## 7. Reason-Code Bridge

Public ARCANA reason codes remain the integration contract surface.

The surrounding system may map ARCANA reason codes into local actions, but it must preserve the original ARCANA reason codes in logs, reviews, and exported artifacts.

| ARCANA result class | Generic local action |
| --- | --- |
| `ARCANA_ALLOW_BOUNDED_AUTONOMY` | Eligible for local admission review when local policy also permits. |
| `ARCANA_ALLOW_WITH_CONTROLS` | Apply listed controls before admission is considered. |
| `ARCANA_REQUIRE_SCOPE_REDUCTION` | Request a narrower action, capability envelope, horizon, or budget. |
| `ARCANA_REQUIRE_HUMAN_GATE` | Route to a review or approval flow. |
| `ARCANA_REQUIRE_OBSERVE_ONLY` | Monitor or analyze without admission or certificate claim. |
| `ARCANA_DENY_*` | Do not admit without recompute, remediation, or a narrower request. |
| `ARCANA_INFO_*` | Preserve as an artifact caveat, provenance marker, or limitation. |

Local action mappings must not collapse distinct ARCANA denial codes into a generic public result.

## 8. Public vs Integration-Private Field Boundary

Public fields are fields that may appear in ARCANA public artifacts:

| Public field class | Examples |
| --- | --- |
| Versioning | `schema_version`, `risk_model_version` |
| Calibration | `calibration_profile_id`, `calibration_level` |
| Horizon | `decision_horizon.id`, `duration_seconds`, `context` |
| Graph binding | `graph_hash` |
| Risk metrics | `rho_interval`, `loss_bounds`, `fastgate` |
| Decision | `decision`, `verdict`, `reason_codes`, `required_controls` |
| Evidence | `source_type`, `source_id`, `evidence_hash`, `synthetic` |
| Budget | `autonomy_budget` |
| Certificate metadata | `certificate_id`, `certificate_type`, `issued_at`, `expires_at`, `caveats` |

Integration-private fields must remain outside public ARCANA artifacts unless a future public schema explicitly admits them.

Examples of integration-private data:

- credentials;
- secrets;
- raw prompts or raw user data;
- private logs;
- local policy tables;
- local approval notes;
- customer identifiers;
- billing or account identifiers;
- private telemetry streams;
- commercial calibration profiles;
- private evidence payloads;
- private adapter state;
- local control-plane state;
- service endpoint URLs if they identify private deployments.

Public ARCANA artifacts may reference evidence by hash and source identifier. They must not embed integration-private evidence payloads by default.

## 9. Freshness and Recompute Rules

An integration must reject or recompute an ARCANA artifact when any of these conditions holds:

- schema version is unsupported;
- risk model version is unsupported;
- calibration profile is missing or unsupported;
- calibration level is insufficient for the requested claim;
- decision horizon is missing, expired, or incompatible;
- graph hash is missing or mismatched;
- evidence hash is missing where required;
- evidence source is stale, unavailable, or mismatched;
- reason code is not registered in the public registry;
- `rho_interval.upper` breaches the declared threshold;
- loss bounds breach declared limits;
- autonomy budget is expired or exhausted;
- FastGate returns uncertain or vector-invalid status;
- A0 output is being used for a certifiable claim.

Unknown compatibility state means risky. It must not become an allow-like ARCANA result.

## 10. Integration Non-Goals

This public contract does not define:

- production enforcement;
- private policy evaluation;
- private telemetry pipelines;
- customer-specific dashboards;
- commercial certificate issuance;
- private adapter mechanics;
- credential handling;
- hosted workflow requirements;
- absolute-safety guarantees;
- risk-elimination guarantees.

## 11. Conformance Checklist

Before using an ARCANA integration contract in a public repo:

- public schema validation passes;
- public audit passes;
- integration examples are synthetic or abstract;
- no private operational field is exported;
- public artifact fields and integration-private fields are separated;
- reason-code mappings preserve original ARCANA codes;
- A0 outputs remain visibly non-certifiable;
- stale or mismatched context triggers recompute;
- evidence hash, source, and synthetic marker are preserved;
- local policy decisions remain separate from ARCANA verdicts.
