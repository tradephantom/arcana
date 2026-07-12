# ARCANA

ARCANA is an open research and reference framework for autonomy accounting in agentic systems.

ARCANA estimates whether a proposed operation, delegation, tool call, memory action, capability grant, or distillation event remains within a bounded risk envelope under explicit model, calibration, horizon, uncertainty, and evidence assumptions.

ARCANA does not prove that an agent or system is safe. It provides model-bounded autonomy accounting.

## Current Status

This public repository is live as an open research/reference release for local evaluation.

Reference implementation through Slice 5 FastGate prototype, ARCANA-Bench v0.1 synthetic evaluator execution, Public Integration Contract v0.1, Whitepaper / Paper v0.2 outline and draft, Whitepaper / Paper v0.3 draft, Whitepaper / Paper v1.0 final public manuscript, release-readiness documents, and the initial public release note are present. No production implementation is present in this public release tree.

Public artifact handling separates structural validation from semantic
admission validation. ARCANA-Bench v0.1 executes complete synthetic inputs
through the public reference evaluator and compares observed decisions with
fixture contracts. It is not an empirical system benchmark, production
evaluation, or calibration evidence source. These boundaries are enforced by
tests and explicit metric availability states.

Public remote:

```text
https://github.com/tradephantom/arcana
```

Security reports should use GitHub Private Vulnerability Reporting, as described in `SECURITY.md`.

## Documents

- `LICENSE.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
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
- `docs/ARCANA_Whitepaper_v0.2_Draft.md`
- `docs/ARCANA_Whitepaper_v0.3_Draft.md`
- `docs/ARCANA_Whitepaper_v1.0_Manuscript.md`
- `docs/LIMITATIONS_v0.1.md`
- `docs/PUBLIC_RELEASE_NOTES_v0.1.md`
- `docs/PUBLIC_REMOTE_PREFLIGHT_v0.1.md`
- `PUBLIC_MANIFEST.md`

## License

- Code, tests, tools, schemas, examples, and build files: `Apache-2.0`
- Public documentation: `CC-BY-4.0`

See `LICENSE.md` for the file-scope license profile.

## Schemas

- `schemas/ARCANA_CalibrationProfile.schema.v0.2.json`
- `schemas/ARCANA_Context.schema.v0.2.json`
- `schemas/ARCANA_Certificate.schema.v0.2.json`
- `schemas/ARCANA_BenchmarkScenario.schema.v0.2.json`
- `schemas/ARCANA_BenchmarkExecutionSuite.schema.v0.1.json`
- `schemas/ARCANA_BenchmarkRunReport.schema.v0.1.json`

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
make bench
```

`make check` runs the public-boundary audit, schema/example validation, and the
deterministic synthetic evaluator benchmark. Unit tests and the standalone demo
remain explicit `make test` and `make demo` gates.

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
- venue-specific paper submission or external archive publication;
- public production claim;
- gateway enforcement mode.
