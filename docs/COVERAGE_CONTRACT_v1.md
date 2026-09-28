# Joint Coverage Contract v1

Status: R3.3 local unreleased reference candidate, 2026-09-28.
Wire version: `arcana.coverage.v1`.

This contract implements **conditional coverage accounting**, not empirical
qualification, a safety probability, a loss probability, or production approval.
It addresses R3-C04 without changing the archived v1.0 paper or release.

## Mathematical Scope

Let E be a finite, prespecified family of required operator-envelope events.
For each event E_i, an external argument supplies a failure upper bound d_i.
Under those premises, irrespective of dependence:

    P(all E_i hold) >= max(0, 1 - sum(d_i)).

`union_bound` implements this inequality. `joint_bound` instead accepts one
externally justified failure upper bound for the **entire** generated family.
It does not infer a joint bound from a marginal confidence or sample size.
Two marginal 99% claims do not, in general, provide 99% joint coverage.

The probability space, sampling design and interpretation of the declared
events must be supplied by evidence for the policy's population and design.
For frequentist bounds this is a repeated-design coverage statement, not a
posterior probability that a realized matrix is safe. The code checks the
declared composition, identities and admissibility, not the external proof.

The supported declaration is deliberately narrow:

- `selection_protocol = fixed_prespecified_family`;
- `factor_semantics = direct_operator_bounds`;
- `dependence = arbitrary`;
- methods `union_bound` and `joint_bound` only.

No independence product, multiplication of marginal factor probabilities,
adaptive graph selection, optional stopping, anytime claim or automatic
Beta update is supported. A chain-rule factorization would need its own
explicit conditioning and estimation contract; relabelling factors is invalid.
An operator entry can exceed one: operator bounds and failure probabilities
are different quantities with different domains.

## Complete Claim Family

The family is generated, not chosen by a caller-supplied claim count:

| Claim | Required event |
| --- | --- |
| `current_upper:i:j` | The true operator entry at these ordered coordinates is bounded above by the supplied current upper entry, under the declared design/scope. |
| `before_lower:i:j` | The calibrated before-state entry is bounded below by the increment contract's lower entry; required exactly when that lower baseline is used. |
| `temporal_joint_premises` | All stochastic premises of the bound temporal contract hold jointly across its whole horizon and declared operator family. |

Every ordered pair is covered, **including zeros and absent edges**. A zero
entry needs a justified structural zero or a failure bound; omitting it is not
evidence that propagation is impossible. A zero failure probability is an
external premise, not inferred certainty.

The lower-baseline claims apply to `calibration_envelope` increment scope with
an explicit before-lower matrix. The deterministic zero fallback needs no
additional statistical claim. `upper_model` increment accounting remains an
algorithmic comparison, not a calibrated real-system increment guarantee.

The temporal joint premise includes domination for every permitted generation
and history, the initial-state bound, family closure and the declared absence
of later exogenous input. Snapshot marginal intervals alone cannot supply it.
Duplicate/dependent events remain conservative under the union bound.

For `joint_bound`, the only accepted term identifier is `complete_family`,
covering exactly all events above, including their referenced contracts.
Neither method covers loss/impact premises, enforcement availability, identity,
network containment, policy truth or general agent behavior.

## Binding and Admissibility

`CoveragePolicy` is an independently authorized requirement inside
`AutonomyBudget`. It pins the population, preregistration/design hash, evidence
hash/source, maximum failure probability in [0,1), and an explicit
`require_empirical_qualification` boolean. It is not an autonomy counter.
Operators must protect the policy separately from untrusted proposed actions.

The contract binds model/profile versions, the complete decision horizon,
current matrix values, ordered node identities and graph identity, as well as
complete increment/temporal contract hashes where present. Referenced contracts
must match the evaluated inputs. Validity must cover the whole half-open
decision horizon; expiration at the horizon endpoint is allowed, evaluation at
expiration is not. Runtime freshness monitoring is outside this contract.

Both main admission and FastGate validate coverage before admission or any
exact/Collatz fallback. Cache entries bind **both** contract and policy hashes.
Removing a contract while retaining its requirement, dropping a policy while
retaining its contract, or reusing a scoped cache after removing both is denied.
Removing both without a scoped cache invokes legacy semantics and reports
`coverage_scope = not_evaluated`; the library cannot enforce a policy that its
trusted caller does not supply. Existing context/certificate v0.2 serialization
rejects scoped coverage policy instead of silently dropping it.

Hashes establish content identity only. They do not prove provenance, temporal
preregistration, nonadaptive selection, source authenticity, completeness of
observations or calibration validity. There is no cryptographic attestation,
external evidence ingestion or mutable population registry in this stage.

## Arithmetic and Resources

All finite binary64 failure bounds are interpreted as their exact represented
values. Composition and policy comparison use rational arithmetic. The emitted
failure bound rounds upward; the complementary coverage bound rounds downward.
For example, the exact represented sum of 0.1 and 0.2 exceeds represented 0.3;
a 0.3 policy therefore rejects it. Numerical enclosure does not establish
statistical validity.

The reference limits the matrix to 64 nodes and the explicit family to 8193
terms (two 64-by-64 matrices plus one temporal event). Duplicate, missing,
unknown or malformed claims are rejected. This is a bounded reference scope,
not a measured latency/SLA claim or a general ingress denial-of-service defense.

## Separate Empirical Gate

Accepted sources are `synthetic_fixture` and `external_unverified` only.
Both can demonstrate conditional software behavior when policy explicitly
does not require empirical qualification. Successful metrics always include:

    coverage_scope = conditional_fixed_family
    coverage_empirical_qualification = not_established
    coverage_evidence_assurance = declared_premises_not_empirically_verified

If policy requires empirical qualification, synthetic input is denied with
`coverage_synthetic_not_empirical`; external unverified input is denied with
`coverage_empirical_review_required`. No self-declared reviewed flag can unlock
this gate. Profile confidence, source labels, successful tests and fixture
hashes do not promote this contract to A2/A3 or establish a real-system bound.

Real qualification still requires a governed external review of the sampling
unit, population, held-out/calibration split, selection design, simultaneous
coverage construction, drift and validity, evidence integrity and approval.
The reference has no empirical approval path yet. Repeated decisions do not
consume a global error budget here; cross-request guarantees need a separate
joint/sequential contract rather than reusing the same marginal guarantee.

## Reproduction

`examples/coverage_union_bound.synthetic.json` binds a two-node synthetic matrix
and four declared failure bounds of 1/128 each. At its fixed valid time:

```python
from arcana.coverage import evaluate_coverage
from arcana.model import CoveragePolicy
from arcana.schemas import EXAMPLE_DIR, load_typed_fixture

contract = load_typed_fixture(EXAMPLE_DIR / "coverage_union_bound.synthetic.json")
policy = CoveragePolicy(
    max_failure_probability=0.125,
    population_id=contract.population_id,
    design_hash=contract.design_hash,
    evidence_hash=contract.evidence_hash,
    evidence_source_id=contract.evidence_source_id,
    require_empirical_qualification=False,
)
metrics = evaluate_coverage(
    contract, policy, decision_time="2026-09-28T10:00:00Z",
    current_upper=contract.current_upper,
)
assert metrics["coverage_probability_lower"] == 31 / 32
assert metrics["coverage_empirical_qualification"] == "not_established"
```

Deriving policy pins from the fixture is for this synthetic demonstration only;
an operational policy must come from an independent authorized source.

Tests include exhaustive event-set enumeration on a finite probability space,
exact rational rounding oracles, all evaluator/fallback paths, combined
increment/temporal binding, omissions, expiry, resource limits, tampering,
legacy serialization and empirical-gate rejection. Package checks rerun the
self-contained suite against direct and sdist-built wheels outside the checkout.
Local and installed replay are software evidence, not independent human review.
