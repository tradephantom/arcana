# Contributing to ARCANA

> Status: contribution policy v0.2
> Scope: public ARCANA repository
> Publication status: public remote setup is complete; contribution intake remains maintainer-reviewed

ARCANA is an open research/reference project for model-bounded autonomy accounting. Public remote setup and GitHub Private Vulnerability Reporting are complete. Contribution intake remains maintainer-reviewed and must preserve the public/private boundary.

## 1. Contribution Rule

Contributions may be accepted only when they preserve ARCANA's public boundary:

- public research/reference scope only;
- no private operational implementation details;
- no customer data;
- no private telemetry;
- no private policy tables;
- no private calibration profiles;
- no private evidence payloads;
- no production enforcement mechanics;
- no claims that ARCANA proves safety or makes risk-free systems.

Unknown provenance means risky. It must be rejected or held for maintainer review.

## 2. License Compatibility

Contributions must follow `LICENSE.md`:

- code, tests, tools, schemas, examples, build files, and validation fixtures must be compatible with Apache-2.0;
- documentation must be compatible with CC-BY-4.0;
- contributors must have the right to submit the material under the applicable license;
- private, restricted, customer, or non-public material must not be submitted.

## 3. Before Submitting

Run the local gate:

```sh
make check
make test
make demo
make bench
```

For code changes, also run:

```sh
python -m compileall -q src
git diff --check
```

Do not submit changes that fail local validation or rely on network-only behavior.

## 4. Public Boundary Checklist

Every contribution must answer:

- Does the change stay within public ARCANA research/reference scope?
- Are all examples synthetic or public-source safe?
- Are all new files listed in `PUBLIC_MANIFEST.md`?
- Are schema IDs public?
- Are reason codes ARCANA-owned and registered in `docs/REASON_CODES.md`?
- Are A0 outputs still non-certifiable?
- Are model version, calibration profile, decision horizon, uncertainty bounds, and evidence assumptions explicit where certificate-like artifacts appear?
- Are propagation risk `K` and loss `L` kept separate?
- Are FastGate uncertain paths fail-closed?
- Are public artifact fields separated from integration-private fields?

## 5. Code Standards

Implementation contributions must:

- use typed data structures;
- validate before acting;
- use explicit reason-code branches;
- avoid wildcard denial or generic error collapse;
- keep deterministic synthetic fixtures;
- keep the demo network-free;
- add tests for each new failure mode;
- preserve public schema validation;
- avoid runtime optimizations that weaken admission semantics.

Distinct failure modes need distinct reason codes and tests. Do not reuse a generic denial for missing input, stale context, graph mismatch, calibration gap, threshold breach, invalid loss model, budget exhaustion, FastGate uncertainty, or invalid vector state.

## 6. Documentation Standards

Documentation contributions must:

- use model-bounded language;
- state calibration limitations directly;
- avoid production-readiness claims;
- avoid certificate-like language unless model, calibration, horizon, uncertainty, evidence, and caveats are explicit;
- keep benchmarks separate from task-success marketing;
- include limitations and non-goals when a claim could be overread.

## 7. Security and Sensitive Material

Do not submit:

- credentials;
- secrets;
- private prompts;
- raw user data;
- customer identifiers;
- private logs;
- non-public telemetry;
- private endpoint URLs;
- private policy or approval workflows.

If sensitive material is found, stop work and follow `SECURITY.md`.

## 8. Review Expectations

Maintainers should review contributions in this order:

1. public/private boundary;
2. mathematical and calibration correctness;
3. schema and reason-code contract;
4. test coverage for distinct outcomes;
5. release-readiness impact.

No change should be merged solely because the happy path passes.
