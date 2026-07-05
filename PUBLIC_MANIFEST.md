# ARCANA Public Manifest

> Status: public repository manifest v0.1
> Scope: files included in the public ARCANA repository

Only files listed here are part of this public repository tree.

## Included Files

| Path | Status | Notes |
| --- | --- | --- |
| `README.md` | public-staging | Public release workspace instructions. |
| `PUBLIC_MANIFEST.md` | public-staging | Manifest of public repository files. |
| `LICENSE.md` | public-staging | Final file-scope license profile. |
| `CONTRIBUTING.md` | public-staging | Public contribution policy. |
| `SECURITY.md` | public-staging | Public security reporting policy and GitHub Private Vulnerability Reporting decision. |
| `.gitignore` | public-staging | Local development exclusions. |
| `Makefile` | public-staging | Local check, test, and demo entrypoint. |
| `pyproject.toml` | public-staging | Python package and dependency declaration. |
| `examples/README.md` | public-staging | Synthetic example index. |
| `examples/calibration_profile_a0.synthetic.json` | public-safe draft | Synthetic A0 calibration profile example. |
| `examples/risk_context_allow_with_controls.synthetic.json` | public-safe draft | Synthetic risk context example. |
| `examples/certificate_a0_non_certifiable.synthetic.json` | public-safe draft | Synthetic non-certifiable A0 certificate example. |
| `examples/benchmark_prompt_injection.synthetic.json` | public-safe draft | Synthetic benchmark scenario example. |
| `examples/benchmark_memory_poisoning.synthetic.json` | public-safe draft | Synthetic benchmark scenario example. |
| `examples/benchmark_tool_misuse.synthetic.json` | public-safe draft | Synthetic benchmark scenario example. |
| `examples/benchmark_delegation_cascade.synthetic.json` | public-safe draft | Synthetic benchmark scenario example. |
| `examples/benchmark_gaming.synthetic.json` | public-safe draft | Synthetic benchmark scenario example. |
| `examples/benchmark_dynamic_execution.synthetic.json` | public-safe draft | Synthetic benchmark scenario example. |
| `docs/README.md` | public-staging | Public documentation index. |
| `docs/ARCANA_PRD_v0.2_Public.md` | public-safe draft | Public PRD draft. |
| `docs/ARCANA_Roadmap_v0.1_Public.md` | public-safe draft | Public roadmap draft. |
| `docs/GLOSSARY.md` | public-safe draft | Public ARCANA vocabulary. |
| `docs/REASON_CODES.md` | public-safe draft | Public ARCANA reason-code registry. |
| `docs/FORMAL_MODEL_v0.2.md` | public-safe draft | Public ARCANA formal model contract. |
| `docs/CALIBRATION_METHODOLOGY_v0.1.md` | public-safe draft | Public ARCANA calibration methodology contract. |
| `docs/FASTGATE_DESIGN_v0.1.md` | public-safe draft | Public ARCANA FastGate admission design. |
| `docs/PUBLIC_DEMO_REFERENCE_IMPLEMENTATION_PLAN_v0.1.md` | public-safe draft | Public demo and reference implementation plan. |
| `docs/ARCANA_BENCH_v0.1.md` | public-safe draft | Public ARCANA-Bench scenario expansion and scoring notes. |
| `docs/PUBLIC_INTEGRATION_CONTRACT_v0.1.md` | public-safe draft | Public enforcement-neutral integration contract and reason-code bridge. |
| `docs/ARCANA_Whitepaper_v0.2_Outline.md` | public-safe draft | Public whitepaper/paper v0.2 outline and claim discipline. |
| `docs/ARCANA_Whitepaper_v0.2_Draft.md` | public-safe draft | Public whitepaper/paper v0.2 full draft for staged expert review. |
| `docs/LIMITATIONS_v0.1.md` | public-safe draft | Public limitations and non-goals document. |
| `docs/PUBLIC_RELEASE_NOTES_v0.1.md` | public-staging | Initial public release note and public claim boundary. |
| `docs/RELEASE_POLICY.md` | public-staging | Local-first release and remote policy. |
| `docs/PUBLIC_REMOTE_PREFLIGHT_v0.1.md` | public-staging | Public remote publication preflight checklist. |
| `schemas/ARCANA_BenchmarkScenario.schema.v0.2.json` | public-safe draft | Public benchmark scenario schema. |
| `schemas/ARCANA_CalibrationProfile.schema.v0.2.json` | public-safe draft | Public calibration profile schema. |
| `schemas/ARCANA_Certificate.schema.v0.2.json` | public-safe draft | Public certificate schema. |
| `schemas/ARCANA_Context.schema.v0.2.json` | public-safe draft | Public risk context schema. |
| `src/arcana/__init__.py` | public-staging | ARCANA package entrypoint. |
| `src/arcana/_validation.py` | public-staging | Internal validation helpers for typed public contracts. |
| `src/arcana/bench.py` | public-staging | ARCANA-Bench suite loader and coverage validator. |
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
| `tests/test_benchmark_suite.py` | public-staging | ARCANA-Bench scenario coverage and scoring discipline tests. |
| `tests/test_certificate_emission.py` | public-staging | Slice 4 certificate and context emission tests. |
| `tests/test_cli_demo.py` | public-staging | Slice 4 deterministic demo CLI tests. |
| `tests/test_decision_reason_codes.py` | public-staging | Slice 3 decision evaluator and reason-code tests. |
| `tests/test_fastgate.py` | public-staging | Slice 5 FastGate prototype tests. |
| `tests/test_matrix_validation.py` | public-staging | Slice 2 matrix and spectral calculator tests. |
| `tests/test_project_scaffold.py` | public-staging | Slice 0 scaffold verification tests. |
| `tests/test_public_integration_contract.py` | public-staging | Public integration contract boundary and example tests. |
| `tests/test_public_remote_preflight.py` | public-staging | Public remote preflight checklist tests. |
| `tests/test_release_readiness_docs.py` | public-staging | Release-readiness document boundary and gate tests. |
| `tests/test_schema_validation.py` | public-staging | Slice 1 schema validation tests. |
| `tests/test_typed_contracts.py` | public-staging | Slice 1 typed contract tests. |
| `tests/test_whitepaper_draft.py` | public-staging | Whitepaper/paper full draft claim discipline and source coverage tests. |
| `tests/test_whitepaper_outline.py` | public-staging | Whitepaper/paper outline claim discipline and source coverage tests. |
| `tools/audit_public.py` | public-staging | Public release-boundary audit script. |
| `tools/validate_schemas.py` | public-staging | Public schema and synthetic example validator. |

## Release Checklist Status

- [x] All public files are listed in this manifest.
- [x] No file contains local filesystem paths.
- [x] No file contains private implementation details.
- [x] No file contains private lab or customer operational details.
- [x] No file uses private or adapter-specific reason codes as the public default.
- [x] No file claims absolute safety, risk elimination, or production certification from demo calibration.
- [x] Schema IDs, if present, use public namespaces.
- [x] Examples and fixtures, if present, are synthetic or public-source safe.
