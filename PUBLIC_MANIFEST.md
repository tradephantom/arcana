# ARCANA Public Manifest

> Status: public staging manifest v0.1
> Scope: files intended to seed a future public ARCANA repository

Only files listed here are part of this public release candidate tree.

## Included Files

| Path | Status | Notes |
| --- | --- | --- |
| `README.md` | public-staging | Public release workspace instructions. |
| `PUBLIC_MANIFEST.md` | public-staging | Manifest of public release candidates. |
| `.gitignore` | public-staging | Local development exclusions. |
| `Makefile` | public-staging | Local check entrypoint. |
| `pyproject.toml` | public-staging | Python package and dependency declaration. |
| `examples/README.md` | public-staging | Synthetic example index. |
| `examples/calibration_profile_a0.synthetic.json` | public-safe draft | Synthetic A0 calibration profile example. |
| `examples/risk_context_allow_with_controls.synthetic.json` | public-safe draft | Synthetic risk context example. |
| `examples/certificate_a0_non_certifiable.synthetic.json` | public-safe draft | Synthetic non-certifiable A0 certificate example. |
| `examples/benchmark_prompt_injection.synthetic.json` | public-safe draft | Synthetic benchmark scenario example. |
| `docs/README.md` | public-staging | Public documentation index. |
| `docs/ARCANA_PRD_v0.2_Public.md` | public-safe draft | Public PRD draft; review required before remote publication. |
| `docs/ARCANA_Roadmap_v0.1_Public.md` | public-safe draft | Public roadmap draft; review required before remote publication. |
| `docs/GLOSSARY.md` | public-safe draft | Public ARCANA vocabulary. |
| `docs/REASON_CODES.md` | public-safe draft | Public ARCANA reason-code registry. |
| `docs/FORMAL_MODEL_v0.2.md` | public-safe draft | Public ARCANA formal model contract. |
| `docs/CALIBRATION_METHODOLOGY_v0.1.md` | public-safe draft | Public ARCANA calibration methodology contract. |
| `docs/FASTGATE_DESIGN_v0.1.md` | public-safe draft | Public ARCANA FastGate admission design. |
| `docs/PUBLIC_DEMO_REFERENCE_IMPLEMENTATION_PLAN_v0.1.md` | public-safe draft | Public demo and reference implementation plan. |
| `docs/RELEASE_POLICY.md` | public-staging | Local-first release and remote policy. |
| `schemas/ARCANA_BenchmarkScenario.schema.v0.2.json` | public-safe draft | Public benchmark scenario schema. |
| `schemas/ARCANA_CalibrationProfile.schema.v0.2.json` | public-safe draft | Public calibration profile schema. |
| `schemas/ARCANA_Certificate.schema.v0.2.json` | public-safe draft | Public certificate schema. |
| `schemas/ARCANA_Context.schema.v0.2.json` | public-safe draft | Public risk context schema. |
| `src/arcana/__init__.py` | public-staging | ARCANA package entrypoint. |
| `src/arcana/_validation.py` | public-staging | Internal validation helpers for typed public contracts. |
| `src/arcana/calibration.py` | public-staging | Calibration module boundary. |
| `src/arcana/certificate.py` | public-staging | Certificate module boundary. |
| `src/arcana/decision.py` | public-staging | Decision module boundary. |
| `src/arcana/demo.py` | public-staging | Demo entrypoint boundary. |
| `src/arcana/errors.py` | public-staging | Error and reason-code module boundary. |
| `src/arcana/fastgate.py` | public-staging | FastGate module boundary. |
| `src/arcana/loss.py` | public-staging | Loss module boundary. |
| `src/arcana/matrices.py` | public-staging | Matrix module boundary. |
| `src/arcana/model.py` | public-staging | Graph and horizon model boundary. |
| `src/arcana/schemas.py` | public-staging | Public schema module boundary. |
| `tests/test_decision_reason_codes.py` | public-staging | Slice 3 decision evaluator and reason-code tests. |
| `tests/test_matrix_validation.py` | public-staging | Slice 2 matrix and spectral calculator tests. |
| `tests/test_project_scaffold.py` | public-staging | Slice 0 scaffold verification tests. |
| `tests/test_schema_validation.py` | public-staging | Slice 1 schema validation tests. |
| `tests/test_typed_contracts.py` | public-staging | Slice 1 typed contract tests. |
| `tools/audit_public.py` | public-staging | Public release-boundary audit script. |
| `tools/validate_schemas.py` | public-staging | Public schema and synthetic example validator. |

## Release Checklist

- [ ] All public files are listed in this manifest.
- [ ] No file contains local filesystem paths.
- [ ] No file contains private implementation details.
- [ ] No file contains private lab or customer operational details.
- [ ] No file uses private or adapter-specific reason codes as the public default.
- [ ] No file claims absolute safety, risk elimination, or production certification from demo calibration.
- [ ] Schema IDs, if present, use public namespaces.
- [ ] Examples and fixtures, if present, are synthetic or public-source safe.
