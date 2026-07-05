# ARCANA Public Release Notes v0.1

> Status: initial public reference release
> Scope: ARCANA open research/reference repository
> Repository: https://github.com/tradephantom/arcana

ARCANA is now available as a public open research/reference repository for
model-bounded autonomy accounting in agentic systems.

This release includes:

- public PRD and roadmap;
- formal model and calibration methodology drafts;
- public schema contracts;
- reason-code registry;
- synthetic benchmark scenarios;
- FastGate reference prototype;
- deterministic synthetic demo;
- whitepaper/paper v0.2 outline and draft;
- limitations, contribution, security, and release-readiness documents.

Local validation:

```sh
make check
make test
make demo
```

The initial public remote was validated from a fresh clone. The validation
covered public-boundary audit, schema validation, unit tests, and deterministic
demo execution.

## Claim Boundary

Allowed public claim:

```text
ARCANA is an open research/reference framework for model-bounded autonomy
accounting under explicit model, calibration, horizon, uncertainty, and evidence
assumptions.
```

Not authorized:

- absolute-safety claims;
- risk-elimination claims;
- public production enforcement claims;
- production certificate issuance claims;
- final paper publication claims;
- claims that synthetic benchmark results prove deployment safety.

## Security Channel

Security reports should use GitHub Private Vulnerability Reporting. Sensitive
reports should not be opened as public issues.

## Current Non-Goals

This public repository does not include production enforcement, private
deployment integrations, private telemetry pipelines, production calibration
profiles, or commercial certificate issuance.
