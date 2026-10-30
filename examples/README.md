# ARCANA Public Examples

Examples in this folder are synthetic. They are not production evidence and do not establish operational certification.

Current examples:

- `coverage_union_bound.synthetic.json`
- `temporal_common_envelope.synthetic.json`

- `increment_calibration_envelope.synthetic.json`

- `calibration_profile_a0.synthetic.json`
- `risk_context_allow_with_controls.synthetic.json`
- `certificate_a0_non_certifiable.synthetic.json`
- `benchmark_prompt_injection.synthetic.json`
- `benchmark_memory_poisoning.synthetic.json`
- `benchmark_tool_misuse.synthetic.json`
- `benchmark_delegation_cascade.synthetic.json`
- `benchmark_gaming.synthetic.json`
- `benchmark_dynamic_execution.synthetic.json`
- `benchmark_negative_a0_artifact_admission.synthetic.json`
- `benchmark_negative_fastgate_inconclusive.synthetic.json`
- `benchmark_negative_graph_hash_mismatch.synthetic.json`
- `benchmark_negative_loss_model_missing.synthetic.json`
- `benchmark_negative_missing_decision_horizon.synthetic.json`
- `benchmark_negative_rho_upper_above_threshold.synthetic.json`
- `benchmark_negative_stale_evidence.synthetic.json`
- `arcana_bench_execution_suite.synthetic.json`

The execution suite supplies one complete non-certifiable A0/A1 evaluator
input per benchmark scenario. `make bench` executes those inputs through the
public reference evaluator. The resulting report is synthetic evaluator
evidence only, not empirical system or production evidence.

The increment example reproduces the R3-C02 budget-scope counterexample. Its
standalone calculation uses `evaluate_increment` at the fixed synthetic time
`2026-09-10T10:00:00Z`. It is not live evidence or a certificate.

The coverage example declares four synthetic direct-operator failure bounds.
At `2026-09-28T10:00:00Z`, `evaluate_coverage` with a 0.125 failure policy
composes them to a conditional coverage lower bound of 31/32. This does not
establish empirical coverage; requesting empirical qualification is denied.
See [the coverage contract](../docs/COVERAGE_CONTRACT_v1.md) for the full example.

The temporal example declares two generation operators under one common
envelope. At `2026-09-11T10:00:00Z`, a `TemporalPolicy` requiring three
generations with peak/cumulative limits of 10/20 passes `evaluate_temporal`.
Its expected activation totals are `[1, 0.5, 0.125, 0.0625]`, cumulative 1.6875.
The fixed date and declared evidence are synthetic, not runtime telemetry.
