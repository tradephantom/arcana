# ARCANA Security Policy

> Status: security policy v0.1 draft
> Scope: local public release candidate
> Publication status: private reporting channel must be configured before public remote release

ARCANA is a public research/reference project for model-bounded autonomy accounting. Security reporting must preserve user safety, private material boundaries, and calibration integrity.

## 1. Supported Scope

Security reports are in scope when they affect:

- public reference implementation correctness;
- schema validation;
- reason-code integrity;
- certificate-like artifact validation;
- public-boundary leakage controls;
- benchmark fixture integrity;
- FastGate fail-closed behavior;
- evidence hash or provenance binding;
- dependency or packaging safety for the local demo.

Reports about private deployments, private integrations, customer systems, or non-public telemetry are outside this public repository's scope and must not be disclosed here.

## 2. Reporting Rule

Before any public remote release, the maintainer must configure a private security reporting channel.

Until that channel exists:

- do not publish sensitive vulnerability details in public issues;
- do not include exploit payloads in public comments;
- do not attach credentials, tokens, customer data, private logs, or raw sensitive evidence;
- preserve enough detail for maintainers to reproduce the issue using synthetic or minimized inputs;
- mark the report as security-sensitive.

When a public remote exists, use the repository's private security advisory workflow or another maintainer-approved private channel.

## 3. Report Template

A useful report should include:

- affected file, module, schema, or document;
- exact ARCANA version or commit;
- public-safe reproduction steps;
- expected behavior;
- observed behavior;
- impact on model-bounded decision semantics;
- whether a reason code is missing, wrong, or collapsed;
- whether a public/private boundary could be crossed;
- synthetic proof input when possible.

Do not include private operational material.

## 4. Security-Relevant Failure Classes

ARCANA maintainers should treat these as high-priority:

| Class | Example impact |
| --- | --- |
| Boundary leakage | Public artifact exposes private operational material. |
| Schema bypass | Invalid certificate-like artifact validates. |
| Reason-code collapse | Distinct deny path becomes a generic or allow-like result. |
| FastGate false admission | Uncertain or invalid fast path can return allow-like output. |
| Calibration overclaim | A0 or insufficient calibration appears certifiable. |
| Evidence mismatch | Artifact can be accepted with stale, missing, or mismatched evidence hash. |
| Benchmark mislabeling | Synthetic scenario appears to represent a real deployment. |

## 5. Handling Guidance

Maintainers should:

- reproduce with synthetic or minimized public-safe input;
- preserve the failing artifact for review;
- add or update a regression test before closing;
- update reason codes if the failure mode is distinct;
- update schemas when validation is underspecified;
- update documentation when claim language enabled misuse;
- run `make check`, `make test`, and `make demo` before resolution.

Security fixes must not weaken public-boundary audit or replace specific reason codes with generic fallbacks.

## 6. Disclosure Readiness

Before public disclosure of a fixed issue:

- sensitive details are removed or minimized;
- no private material is included;
- reproduction uses synthetic fixtures;
- affected reason codes and schemas are named;
- limitations are updated if the issue changes ARCANA's claim boundary.
