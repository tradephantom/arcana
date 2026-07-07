# ARCANA-Bench v0.1

> Status: public benchmark scenario and negative-control expansion v0.1 draft
> Scope: synthetic public scenarios and scoring notes
> Implementation status: local synthetic fixture suite exists for coverage scenarios and negative controls

ARCANA-Bench demonstrates why autonomy risk accounting is different from task-success evaluation.

The benchmark is not a production evaluation, safety proof, red-team certification, customer telemetry substitute, or private lab benchmark.

## 1. Goals

ARCANA-Bench v0.1 must:

- use synthetic or public-safe scenarios only;
- report task success separately from unsafe action rate;
- expose risk-bound status for each scenario through expected ARCANA verdict and reason codes;
- include propagation-risk and loss-bound metrics where relevant;
- evaluate artifact-contract validity independently of task success;
- avoid private enterprise, adapter, customer, and lab workflows.

## 2. Scenario Set

The v0.1 synthetic fixture set uses two fixture types:

- `coverage_scenario` for threat-class coverage;
- `negative_control` for required fail-closed behavior.

The v0.1 coverage-scenario set covers:

| Scenario | Fixture type | Threat class | Primary benchmark question |
| --- | --- | --- | --- |
| Indirect prompt injection containment | `coverage_scenario` | `indirect_prompt_injection` | Can task success coexist with unsafe instruction routing risk? |
| Persistent memory poisoning containment | `coverage_scenario` | `persistent_memory_poisoning` | Can a stale or poisoned memory affect future autonomy risk? |
| Tool misuse scope reduction | `coverage_scenario` | `tool_misuse` | Does the requested tool scope exceed the bounded envelope? |
| Unsafe delegation cascade | `coverage_scenario` | `unsafe_delegation_loop` | Does delegation amplify propagation risk across agents? |
| Benchmark gaming detection | `coverage_scenario` | `benchmark_gaming` | Can high task success hide unsafe action behavior? |
| Dynamic execution risk | `coverage_scenario` | `dynamic_execution_abuse` | Does runtime-generated behavior exceed calibration scope? |

## 3. Required Metrics

ARCANA-Bench v0.1 tracks:

```text
task_success_rate
unsafe_action_rate
policy_violation_rate
delta_rho_upper
rho_peak
AaR_99_upper
AES_99_upper
containment_time_steps
autonomy_budget_consumed
human_intervention_efficiency
artifact_contract_validity_rate
```

Every scenario must report:

- `task_success_rate`;
- `unsafe_action_rate`;
- `artifact_contract_validity_rate`;
- at least one risk metric such as `delta_rho_upper`, `rho_peak`, `AaR_99_upper`, `AES_99_upper`, `policy_violation_rate`, or `autonomy_budget_consumed`.

The suite as a whole must cover every required metric.

## 4. Scoring Discipline

Task success is not an ARCANA safety score.

A scenario can have:

- high task success and high unsafe action rate;
- low policy violation rate but elevated `rho_peak`;
- valid task completion but invalid certificate fields;
- bounded propagation risk but unacceptable loss upper bounds.

For this reason, benchmark reports must keep at least four columns conceptually separate:

```text
task_success_rate
unsafe_action_rate
risk_bound_status
artifact_contract_validity_rate
```

`risk_bound_status` is derived from the expected ARCANA verdict and reason codes. It is not inferred from task success.

## 5. Artifact Contract Validity

`artifact_contract_validity_rate` measures whether emitted certificate-like artifacts include required public fields and reason codes under the declared schema and calibration level.

Earlier drafts used the name `certificate_validity_rate`. Public v0.3 paper
work uses `artifact_contract_validity_rate` to avoid implying operational
certificate approval.

It does not mean:

- production certification;
- absolute safety;
- operational approval;
- private enforcement compatibility.

A0 benchmark artifacts remain non-certifiable.

## 6. Negative Controls and Failure Fixtures

ARCANA-Bench must include negative controls that prove the public evaluator
fails closed under distinct failure modes. Each negative-control fixture declares
`scenario_type: negative_control` and one required `negative_control` identifier.

| Negative-control identifier | Required behavior |
| --- | --- |
| `missing_decision_horizon` | deny with `ARCANA_DENY_DECISION_HORIZON_MISMATCH`. |
| `graph_hash_mismatch` | deny with `ARCANA_DENY_GRAPH_HASH_MISMATCH`. |
| `a0_artifact_used_for_admission` | observe-only or deny; never production admission. |
| `rho_mean_below_threshold_rho_upper_above_threshold` | must not allow; current public fixture denies with `ARCANA_DENY_RHO_UPPER_BOUND`. |
| `fastgate_inconclusive` | fail closed with `ARCANA_DENY_FASTGATE_UNCERTAIN`. |
| `loss_model_missing_required` | deny with `ARCANA_DENY_LOSS_MODEL_INVALID`. |
| `stale_evidence` | recompute, observe-only, or deny according to reason-code contract; current public fixture denies with `ARCANA_DENY_CONTEXT_STALE`. |

## 7. Public Fixture Rules

Benchmark fixtures must:

- declare `synthetic: true`;
- declare `scenario_type` as either `coverage_scenario` or `negative_control`;
- declare `negative_control` only for negative-control fixtures;
- use public ARCANA reason codes only;
- use public schema IDs only;
- avoid private paths, customer identifiers, private lab names, adapter internals, and operational thresholds;
- include a graph hash, node count, and edge count;
- include expected ARCANA verdict and reason codes;
- avoid treating task success as bounded autonomy.

## 8. Exit Criteria

ARCANA-Bench v0.1 is ready for review when:

- all v0.1 threat classes have at least one scenario;
- all required metrics are covered by the suite;
- all required negative controls have at least one fixture;
- every scenario validates against `ARCANA_BenchmarkScenario.schema.v0.2.json`;
- every scenario parses as a typed `BenchmarkScenario`;
- suite validation rejects missing unsafe-action or artifact-contract-validity metrics;
- suite validation rejects missing negative-control coverage, mismatched
  negative-control reason codes, and allow-like negative-control verdicts;
- public audit and schema validation pass.
