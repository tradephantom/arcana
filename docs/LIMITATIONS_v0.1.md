# ARCANA Limitations v0.1

> Status: active public limitations contract v0.1
> Scope: public ARCANA research/reference track
> Classification: public-safe

This document states the limits of ARCANA public artifacts. It should be read before any whitepaper, demo, benchmark, certificate-like artifact, or integration guidance is treated as release-ready.

## 1. Core Limitation

ARCANA estimates bounded autonomy under declared assumptions. It does not prove that an agent, workflow, model, tool, policy, deployment, or organization is safe.

Every ARCANA result is scoped by:

- risk model version;
- calibration profile;
- calibration level;
- decision horizon;
- graph hash;
- uncertainty bounds;
- evidence source or evidence hash;
- threshold and budget assumptions;
- reason codes;
- caveats.

If any scope element is missing, stale, unsupported, or mismatched, the artifact must not be treated as bounded autonomy.

## 2. Model-Bounded Scope

ARCANA models a declared capability graph. The graph is not the full real world.

Limitations:

- unmodeled edges can change risk;
- missing nodes can hide propagation paths;
- horizon mismatch can make weights dimensionally invalid;
- graph hash mismatch invalidates a context;
- model updates can change results;
- local policy decisions can require stricter rules than ARCANA outputs.

Unknown compatibility state means risky.

A horizon identifier does not define a propagation generation or validate a
linear recurrence. Fixed-matrix subcriticality does not establish switching
stability, and even a zero-radius DAG can have very large transient propagation.
Initial conditions, finite-horizon amplification and separate impact constraints
remain necessary. See the [R3 technical review](R3_TECHNICAL_CLAIM_REVIEW.md).

## 3. Propagation Risk vs Loss

ARCANA separates:

```text
K = unsafe propagation pressure
L = impact or loss
```

`K` must not contain impact values. `L` must not be used as a propagation edge weight.

An action can have bounded propagation risk but unacceptable loss bounds. An action can also have low expected loss but unacceptable propagation-risk upper bound.

The reference validates supplied scalar loss metrics and limits; it does not
estimate a distribution or verify loss units, confidence coverage, evidence or
horizon metadata absent from `LossBounds`. These are upstream obligations.

## 4. Calibration Limits

Calibration is an evidence-to-uncertainty contract, not proof of real-world behavior.

Multiplying marginal factor probabilities is not generally a conservative joint
probability model. Per-entry marginal coverage does not imply the same coverage
for a whole graph or repeated decisions. Dependence, joint coverage and adaptive
reuse require explicit evidence; numerical enclosure cannot establish them.

Limitations:

- sparse evidence widens uncertainty;
- stale evidence weakens or invalidates a profile;
- passive absence of incidents is not enough by itself;
- unknown risk factors use conservative upper bounds;
- unknown controls use conservative lower bounds;
- calibration profiles must not be reused across incompatible horizons, graph scopes, model versions, or evidence classes.

A0 is demo-only and always non-certifiable.

A1, A2, and A3 require review before any certifiable-under-profile language is used.

The synthetic `public_benchmark` source class never qualifies a profile for A2.
The separate `empirical_public_benchmark` class may qualify only when its
non-synthetic execution provenance, scope, coverage, freshness, and
reproducibility have been reviewed. Declaring that source class is not itself
proof that those conditions hold.

Public documentation may describe A1-A3 semantics, but it must not imply that a
public example, local demo, or synthetic benchmark is production calibration.
Any deployment-specific calibration review remains outside the public reference
repository and must be represented publicly only through redacted limitations.

Current public claim boundary:

- A1 is a conservative prior level, not a commercial certificate basis.
- A2 may be described as empirically reviewable, but public text must not claim
  certificate issuance from A2 without a separate issuance process.
- A3 may be described as a runtime-calibration design target, not as active
  public production evidence.
- Private review outcomes do not disclose private thresholds, formulas,
  runtime distributions, telemetry, or deployment mechanics.

## 5. Decision Limits

ARCANA admission-like decisions use upper bounds.

Limitations:

- `rho_mean` is not an admission metric;
- `rho_upper < theta_rho` is model-bounded, not universal;
- threshold values are context-specific;
- local policy may deny an action that ARCANA marks bounded;
- ARCANA does not provide production enforcement.

Distinct failures must remain distinct. Missing input, unsupported model, stale context, graph mismatch, horizon mismatch, calibration gap, threshold breach, invalid loss model, budget exhaustion, FastGate uncertainty, and invalid vectors require specific reason-code paths.

## 6. Certificate-Like Artifact Limits

Certificate-like artifacts are bounded records, not broad safety approvals.

Every certificate-like artifact must include:

- model version;
- calibration profile;
- calibration level;
- decision horizon;
- graph hash;
- uncertainty bounds;
- evidence source or hash;
- verdict;
- reason codes;
- caveats;
- expiry when applicable.

A0 artifacts are non-certifiable and cannot support production certificate issuance.

A1 artifacts are also not commercial-certificate artifacts in this public
track. A2 or A3 language must remain conditional unless a separate, reviewed
certificate issuance process is explicitly documented. Certificate-like examples
in this repository are schema and reasoning demonstrations, not production
certificates.

## 7. FastGate Limits

FastGate is a conservative declared-model decision path and optimization design.
The reference has no demonstrated latency or sparse-update speedup advantage.
Its incremental budget concerns the supplied upper-model matrices, not every
unknown calibrated matrix below them. A separate lower baseline would be needed
for that stronger increment claim; the current request type does not supply it.

Limitations:

- FastGate must preserve the exact upper-bound decision rule;
- Collatz or positive-vector assumptions must be valid and declared;
- reducible graphs need explicit handling;
- cache keys must match model, calibration, horizon, graph, threshold, evidence, and tolerance profile;
- sparse-delta hashes must be recomputed from the canonical graph binding,
  decision horizon, additive mode, and ordered sparse entries;
- admission-capable paths require an evidence hash even when no cache is used;
- invalid vector state must fail through vector-specific denial;
- uncertainty must not become allow-like output.

When FastGate cannot prove admission conservatively, use exact recompute or deny/observe according to public reason-code semantics.

## 8. Benchmark Limits

ARCANA-Bench v0.1 uses synthetic scenarios.

Limitations:

- synthetic scenarios do not prove production behavior;
- task success is not an ARCANA safety score;
- unsafe action rate must be reported separately from task success;
- artifact-contract validity rate measures public artifact contract validity, not operational approval;
- benchmark coverage is limited to declared scenario classes;
- v0.1 executes complete synthetic inputs through the public reference evaluator and compares observed outcomes with fixture contracts;
- evaluator execution does not run an agent, tool, policy workload, human process, or deployment;
- task, unsafe-action, policy, containment, and human-efficiency metrics remain explicitly `not_measured` where no corresponding workload exists;
- synthetic reference-evaluator behavior is not empirical fail-closed evidence;
- benchmark results must not be treated as customer, enterprise, or private lab evidence.

## 9. Integration Limits

Public integration guidance is enforcement-neutral.

ARCANA can export model-bounded risk artifacts. Surrounding systems decide local policy actions.

Limitations:

- ARCANA does not define production enforcement;
- ARCANA does not publish private policy engines;
- ARCANA does not publish private telemetry pipelines;
- ARCANA does not publish commercial certificate issuance;
- public artifacts must keep integration-private fields separate;
- original ARCANA reason codes must be preserved.

## 10. Public Release Limits

For public remote release and follow-up public updates:

- final license profile must be present;
- contribution policy must be reviewed;
- GitHub Private Vulnerability Reporting must be enabled;
- this limitations document must be reviewed;
- all files must be listed in `PUBLIC_MANIFEST.md`;
- `make check`, `make test`, and `make demo` must pass;
- public-boundary audit must pass.

No release artifact or announcement should be published when its claim boundary is unclear.

This limitations document includes a redacted post-review update for public
claim discipline: private production-readiness review may inform what public
limitations must say, but it does not make the public repository a production
enforcement system, a commercial certificate issuer, or evidence that any
deployment is safe.
