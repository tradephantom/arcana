# ARCANA

ARCANA is an open research and reference framework for autonomy accounting in agentic systems.

ARCANA estimates whether a proposed operation, delegation, tool call, memory action, capability grant, or distillation event remains within a bounded risk envelope under explicit model, calibration, horizon, uncertainty, and evidence assumptions.

ARCANA does not prove that an agent or system is safe. It provides model-bounded autonomy accounting.

## Current Status

Public-safe draft documentation is in progress. No production implementation is present in this public release tree.

## Documents

- `docs/ARCANA_PRD_v0.2_Public.md`
- `docs/ARCANA_Roadmap_v0.1_Public.md`
- `docs/GLOSSARY.md`
- `docs/REASON_CODES.md`
- `docs/FORMAL_MODEL_v0.2.md`
- `PUBLIC_MANIFEST.md`

## Schemas

- `schemas/ARCANA_CalibrationProfile.schema.v0.2.json`
- `schemas/ARCANA_Context.schema.v0.2.json`
- `schemas/ARCANA_Certificate.schema.v0.2.json`
- `schemas/ARCANA_BenchmarkScenario.schema.v0.2.json`

## Local Checks

Run:

```sh
make check
```

The local gate runs public-boundary audit and schema/example validation.

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

- calibration methodology v0.1;
- reference implementation.
