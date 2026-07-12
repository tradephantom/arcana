# ARCANA Public Manifest

> Status: public repository manifest v0.1
> Scope: files included in the public ARCANA repository

Only files listed here are part of this public repository tree.

## Included Files

| Path | Status | Notes |
| --- | --- | --- |
| `README.md` | public release | Public research/reference repository entrypoint. |
| `PUBLIC_MANIFEST.md` | public release | Manifest of public repository files. |
| `LICENSE.md` | public release | Final file-scope license profile. |
| `CONTRIBUTING.md` | public release | Public contribution policy. |
| `SECURITY.md` | public release | Public security reporting policy and GitHub Private Vulnerability Reporting decision. |
| `.gitignore` | public release | Local development exclusions. |
| `Makefile` | public release | Local check, test, and demo entrypoint. |
| `pyproject.toml` | public release | Python package and dependency declaration. |
| `examples/README.md` | public release | Synthetic example index. |
| `examples/calibration_profile_a0.synthetic.json` | public-safe release artifact | Synthetic A0 calibration profile example. |
| `examples/risk_context_allow_with_controls.synthetic.json` | public-safe release artifact | Synthetic risk context example. |
| `examples/certificate_a0_non_certifiable.synthetic.json` | public-safe release artifact | Synthetic non-certifiable A0 certificate example. |
| `examples/benchmark_prompt_injection.synthetic.json` | public-safe release artifact | Synthetic benchmark scenario example. |
| `examples/benchmark_memory_poisoning.synthetic.json` | public-safe release artifact | Synthetic benchmark scenario example. |
| `examples/benchmark_tool_misuse.synthetic.json` | public-safe release artifact | Synthetic benchmark scenario example. |
| `examples/benchmark_delegation_cascade.synthetic.json` | public-safe release artifact | Synthetic benchmark scenario example. |
| `examples/benchmark_gaming.synthetic.json` | public-safe release artifact | Synthetic benchmark scenario example. |
| `examples/benchmark_dynamic_execution.synthetic.json` | public-safe release artifact | Synthetic benchmark scenario example. |
| `examples/benchmark_negative_a0_artifact_admission.synthetic.json` | public-safe release artifact | Synthetic benchmark negative-control fixture. |
| `examples/benchmark_negative_fastgate_inconclusive.synthetic.json` | public-safe release artifact | Synthetic benchmark negative-control fixture. |
| `examples/benchmark_negative_graph_hash_mismatch.synthetic.json` | public-safe release artifact | Synthetic benchmark negative-control fixture. |
| `examples/benchmark_negative_loss_model_missing.synthetic.json` | public-safe release artifact | Synthetic benchmark negative-control fixture. |
| `examples/benchmark_negative_missing_decision_horizon.synthetic.json` | public-safe release artifact | Synthetic benchmark negative-control fixture. |
| `examples/benchmark_negative_rho_upper_above_threshold.synthetic.json` | public-safe release artifact | Synthetic benchmark negative-control fixture. |
| `examples/benchmark_negative_stale_evidence.synthetic.json` | public-safe release artifact | Synthetic benchmark negative-control fixture. |
| `examples/arcana_bench_execution_suite.synthetic.json` | public-safe executable fixture | Complete synthetic evaluator inputs for all ARCANA-Bench scenarios. |
| `docs/README.md` | public release | Public documentation index. |
| `docs/ARCANA_PRD_v0.2_Public.md` | public-safe release artifact | Active public research/reference product contract. |
| `docs/ARCANA_Roadmap_v0.1_Public.md` | public-safe release artifact | Active post-hardening public roadmap. |
| `docs/GLOSSARY.md` | public-safe release artifact | Public ARCANA vocabulary. |
| `docs/REASON_CODES.md` | public-safe release artifact | Public ARCANA reason-code registry. |
| `docs/FORMAL_MODEL_v0.2.md` | public-safe release artifact | Implemented public ARCANA formal model contract. |
| `docs/CALIBRATION_METHODOLOGY_v0.1.md` | public-safe release artifact | Implemented public ARCANA calibration methodology contract. |
| `docs/FASTGATE_DESIGN_v0.1.md` | public-safe release artifact | Implemented public ARCANA FastGate reference design. |
| `docs/PUBLIC_DEMO_REFERENCE_IMPLEMENTATION_PLAN_v0.1.md` | public-safe release artifact | Public demo and reference implementation plan. |
| `docs/ARCANA_BENCH_v0.1.md` | public-safe release artifact | Public ARCANA-Bench scenario expansion and scoring notes. |
| `docs/PUBLIC_INTEGRATION_CONTRACT_v0.1.md` | public-safe release artifact | Public enforcement-neutral integration contract and reason-code bridge. |
| `docs/ARCANA_Whitepaper_v0.2_Outline.md` | public-safe release artifact | Public whitepaper/paper v0.2 outline and claim discipline. |
| `docs/ARCANA_Whitepaper_v0.2_Draft.md` | public-safe release artifact | Public whitepaper/paper v0.2 full draft for staged expert review. |
| `docs/ARCANA_Whitepaper_v0.3_Draft.md` | public-safe historical draft | Public whitepaper/paper v0.3 draft superseded by the v1.0 final public manuscript. |
| `docs/ARCANA_Whitepaper_v1.0_Manuscript.md` | public-safe research manuscript | Public whitepaper/paper v1.0 post-hardening repository edition with executable-reference claim boundaries. |
| `docs/LIMITATIONS_v0.1.md` | public-safe release artifact | Active public limitations and non-goals contract. |
| `docs/PUBLIC_RELEASE_NOTES_v0.1.md` | public release | Initial public release note and public claim boundary. |
| `docs/RELEASE_POLICY.md` | public release | Local-first release and remote policy. |
| `docs/PUBLIC_REMOTE_PREFLIGHT_v0.1.md` | public release | Public remote publication preflight checklist. |
| `schemas/ARCANA_BenchmarkScenario.schema.v0.2.json` | public-safe release artifact | Public benchmark scenario schema. |
| `schemas/ARCANA_BenchmarkExecutionSuite.schema.v0.1.json` | public-safe executable contract | Public typed evaluator-input suite schema. |
| `schemas/ARCANA_BenchmarkRunReport.schema.v0.1.json` | public-safe executable contract | Public deterministic benchmark report schema. |
| `schemas/ARCANA_CalibrationProfile.schema.v0.2.json` | public-safe release artifact | Public calibration profile schema. |
| `schemas/ARCANA_Certificate.schema.v0.2.json` | public-safe release artifact | Public certificate schema. |
| `schemas/ARCANA_Context.schema.v0.2.json` | public-safe release artifact | Public risk context schema. |
| `src/arcana/__init__.py` | public release | ARCANA package entrypoint. |
| `src/arcana/_validation.py` | public release | Internal validation helpers for typed public contracts. |
| `src/arcana/artifacts.py` | public release | Semantic admission validation for typed public artifacts. |
| `src/arcana/bench.py` | public release | ARCANA-Bench suite loader and coverage validator. |
| `src/arcana/benchmark_input.py` | public release | Typed benchmark evaluator inputs and deterministic matrix construction. |
| `src/arcana/bench_runner.py` | public release | Actual evaluator runner, report generator, and report verifier. |
| `src/arcana/calibration.py` | public release | Calibration module boundary. |
| `src/arcana/certificate.py` | public release | Certificate module boundary. |
| `src/arcana/decision.py` | public release | Decision module boundary. |
| `src/arcana/demo.py` | public release | Demo entrypoint boundary. |
| `src/arcana/errors.py` | public release | Error and reason-code module boundary. |
| `src/arcana/fastgate.py` | public release | FastGate module boundary. |
| `src/arcana/loss.py` | public release | Loss module boundary. |
| `src/arcana/matrices.py` | public release | Matrix module boundary. |
| `src/arcana/model.py` | public release | Graph and horizon model boundary. |
| `src/arcana/schemas.py` | public release | Public schema module boundary. |
| `tests/test_benchmark_suite.py` | public release | ARCANA-Bench scenario coverage and scoring discipline tests. |
| `tests/test_benchmark_runner.py` | public release | Executable benchmark, provenance, regression, and tamper tests. |
| `tests/test_artifact_semantics.py` | public release | Semantic artifact contradiction, freshness, and binding tests. |
| `tests/test_certificate_emission.py` | public release | Slice 4 certificate and context emission tests. |
| `tests/test_cli_demo.py` | public release | Slice 4 deterministic demo CLI tests. |
| `tests/test_decision_reason_codes.py` | public release | Slice 3 decision evaluator and reason-code tests. |
| `tests/test_fastgate.py` | public release | Slice 5 FastGate reference-contract tests. |
| `tests/test_matrix_validation.py` | public release | Slice 2 matrix and spectral calculator tests. |
| `tests/test_project_scaffold.py` | public release | Slice 0 scaffold verification tests. |
| `tests/test_public_audit_security.py` | public release | Public audit secret-material regression tests. |
| `tests/test_public_integration_contract.py` | public release | Public integration contract boundary and example tests. |
| `tests/test_public_remote_preflight.py` | public release | Public remote preflight checklist tests. |
| `tests/test_release_readiness_docs.py` | public release | Release-readiness document boundary and gate tests. |
| `tests/test_schema_validation.py` | public release | Slice 1 schema validation tests. |
| `tests/test_typed_contracts.py` | public release | Slice 1 typed contract tests. |
| `tests/test_whitepaper_draft.py` | public release | Whitepaper/paper full draft claim discipline and source coverage tests. |
| `tests/test_whitepaper_outline.py` | public release | Whitepaper/paper outline claim discipline and source coverage tests. |
| `tests/test_whitepaper_v03_draft.py` | public release | Whitepaper/paper v0.3 draft hardening and related-work tests. |
| `tests/test_whitepaper_v10_manuscript.py` | public release | Whitepaper/paper v1.0 final manuscript claim discipline and publication-gate tests. |
| `tests/test_final_claim_language.py` | public release | Final public claim-language guardrails for manuscript and public-facing docs. |
| `tools/audit_public.py` | public release | Public release-boundary audit script. |
| `tools/validate_schemas.py` | public release | Public schema and synthetic example validator. |

## Release Checklist Status

- [x] All public files are listed in this manifest.
- [x] No file contains local filesystem paths.
- [x] No file contains private implementation details.
- [x] No file contains private lab or customer operational details.
- [x] No file uses private or adapter-specific reason codes as the public default.
- [x] No file claims absolute safety, risk elimination, or production certification from demo calibration.
- [x] Schema IDs, if present, use public namespaces.
- [x] Examples and fixtures, if present, are synthetic or public-source safe.
