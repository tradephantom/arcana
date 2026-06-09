# ARCANA

ARCANA is an open research and reference framework for autonomy accounting in agentic systems.

ARCANA estimates whether a proposed operation, delegation, tool call, memory action, capability grant, or distillation event remains within a bounded risk envelope under explicit model, calibration, horizon, uncertainty, and evidence assumptions.

ARCANA does not prove that an agent or system is safe. It provides model-bounded autonomy accounting.

## Current Status

Public-safe draft documentation is in progress. Reference implementation through Slice 5 FastGate prototype, ARCANA-Bench v0.1 synthetic scenario expansion, Public Integration Contract v0.1, and Whitepaper / Paper v0.2 outline are present for local evaluation. No production implementation is present in this public release tree.

## Documents

- `docs/ARCANA_PRD_v0.2_Public.md`
- `docs/ARCANA_Roadmap_v0.1_Public.md`
- `docs/GLOSSARY.md`
- `docs/REASON_CODES.md`
- `docs/FORMAL_MODEL_v0.2.md`
- `docs/CALIBRATION_METHODOLOGY_v0.1.md`
- `docs/FASTGATE_DESIGN_v0.1.md`
- `docs/PUBLIC_DEMO_REFERENCE_IMPLEMENTATION_PLAN_v0.1.md`
- `docs/ARCANA_BENCH_v0.1.md`
- `docs/PUBLIC_INTEGRATION_CONTRACT_v0.1.md`
- `docs/ARCANA_Whitepaper_v0.2_Outline.md`
- `PUBLIC_MANIFEST.md`

## Schemas

- `schemas/ARCANA_CalibrationProfile.schema.v0.2.json`
- `schemas/ARCANA_Context.schema.v0.2.json`
- `schemas/ARCANA_Certificate.schema.v0.2.json`
- `schemas/ARCANA_BenchmarkScenario.schema.v0.2.json`

## Local Checks

Optional local environment setup:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run:

```sh
make check
make test
make demo
```

The local gate runs public-boundary audit, schema/example validation, unit tests, and the deterministic synthetic demo.

## Core Claim Discipline

Allowed:

```text
ARCANA estimates bounded autonomy under explicit risk model versions, calibration profiles, decision horizons, and uncertainty bounds.
```

Not allowed:

```text
absolute-safety or risk-elimination claims
```

## Not Yet Present

- production implementation;
- production certificate issuance;
- final reviewed whitepaper or paper manuscript;
- release-readiness documents: license, contribution policy, security policy, and limitations document.
