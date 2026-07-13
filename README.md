# ARCANA

[![ARCANA Public CI](https://github.com/tradephantom/arcana/actions/workflows/ci.yml/badge.svg)](https://github.com/tradephantom/arcana/actions/workflows/ci.yml)

ARCANA, the **Autonomy Risk Calculus for Agentic Network Assurance**, is an open research and reference framework for autonomy accounting in agentic systems.

ARCANA estimates whether a proposed operation, delegation, tool call, memory action, capability grant, or distillation event remains within a bounded risk envelope under explicit model, calibration, horizon, uncertainty, and evidence assumptions.

ARCANA does not prove that an agent or system is safe. It provides model-bounded autonomy accounting.

## Current Status

This public repository is live as an open research/reference release for local evaluation.

The standalone reference implementation through Slice 5, ARCANA-Bench v0.1
synthetic evaluator execution, Public Integration Contract v0.1, Whitepaper /
Paper v1.0 public research manuscript, and release-readiness contracts are
present. The Zenodo DOI assigned to the preprint is
`10.5281/zenodo.21333463`. No production implementation is present in this
public release tree.

Public artifact handling separates structural validation from semantic
admission validation. ARCANA-Bench v0.1 executes complete synthetic inputs
through the public reference evaluator and compares observed decisions with
fixture contracts. It is not an empirical system benchmark, production
evaluation, or calibration evidence source. These boundaries are enforced by
tests and explicit metric availability states.

The `public_benchmark` calibration source class names this synthetic benchmark
and cannot qualify A2. `empirical_public_benchmark` is a distinct non-synthetic
source class whose provenance and evidence must be reviewed separately.

Public remote:

```text
https://github.com/tradephantom/arcana
```

Security reports should use GitHub Private Vulnerability Reporting, as described in `SECURITY.md`.

## Documents

- `CITATION.cff`
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
- `docs/PUBLIC_RELEASE_NOTES_v0.1.1.md`
- `docs/PUBLIC_REMOTE_PREFLIGHT_v0.1.md`
- `paper/README.md`
- `paper/PUBLICATION.json`
- `paper/ARCANA_Whitepaper_v1.0.tex`
- `PUBLIC_MANIFEST.md`

## License

- Code, tests, tools, schemas, examples, and build files: `Apache-2.0`
- Public documentation: `CC-BY-4.0`

See `LICENSE.md` for the file-scope license profile.

## Citation

Preferred paper citation:

```text
Elizondo Rodriguez, Julio. ARCANA: Autonomy Risk Calculus for Agentic Network
Assurance. Version 1.0. Zenodo, 2026.
https://doi.org/10.5281/zenodo.21333463
```

`CITATION.cff` provides machine-readable software and preferred-paper citation
metadata. The paper is licensed under `CC-BY-4.0`; the public reference
software remains under `Apache-2.0`.

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
make paper-check
```

`make check` runs the public-boundary audit, schema/example validation, and the
deterministic synthetic evaluator benchmark. Unit tests and the standalone demo
remain explicit `make test` and `make demo` gates.

`make paper` compiles the venue-neutral LaTeX package locally with Pandoc and
Tectonic. Generated PDF and auxiliary files remain under ignored `build/`.

## Public CI

GitHub Actions independently repeats the public-boundary audit, schema checks,
the reference test suite, deterministic benchmark and demo replay, and pinned
Pandoc/Tectonic paper reproduction on standard Ubuntu runners. The workflow is
read-only, uses no repository secrets, persists no build artifacts or caches,
and pins every external Action to a full commit SHA.

CI validates the checked-out public research/reference revision. A green run is
not empirical A2/A3 evidence, peer review, production approval, or proof of
absolute safety.

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
- external academic peer review or venue acceptance;
- public production claim;
- gateway enforcement mode.
