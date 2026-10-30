# Temporal Propagation Contract v1

Status: unreleased R3.2 reference contract, conditional on declared premises.
Wire version: `arcana.temporal.v1`. Not production or empirical approval.

## Supported Model

`K[i,j]` bounds expected offspring activations at destination j per activation
at source i in ONE causal generation. A column state therefore evolves under
`K.T`, not `K`. Horizon-total weights cannot be reused as generation operators
by relabelling a duration; explicit generation calibration evidence is required.

Supported modes are `fixed_operator` and `common_envelope`. Both require fixed
node coordinates, a nonnegative initial upper state, a finite generation count,
and no exogenous arrivals after that initial state. For common-envelope mode,
every declared operator must be entrywise dominated by the same nonnegative U.
The actual recurrence must be dominated by the declared family at every
generation. This is a premise about conditional expected propagation, not an
independence claim. Nonlinear state dependence is supported only if that
domination premise really holds. Unknown operators and unsupported arrival or
generation semantics are rejected.

The fixed mode requires exactly one represented operator equal to its envelope.
The common mode covers arbitrary ordering from the declared family, not just
the operator of the current request. The current evaluator/FastGate after
matrix must be a content- and graph-bound member of that family. Graphs may
differ within the family but node ordering and dimensions must agree.

## Proof and Finite Bounds

Assume `0 <= x_0 <= s` and `0 <= x_(g+1) <= K_g.T x_g` with `0 <= K_g <= U`.
Induction gives `x_g <= (U.T)^g s`, including under arbitrary switching among
the declared operators. The reference computes this upper recurrence using
exact rational dot products and rounds each component upward to binary64 after
each generation. It sums each state's components and all generation totals
outward, so rounding cannot reduce a bound. Unrepresentable bounds deny with
specific issue codes; no clipping, infinity-as-success or zero substitution.

Peak is the maximum total over generations 0 through G. Cumulative includes
all G+1 totals, including the initial state; it counts activations, not unique
agents, not damage and not tail probability. Both limits are explicit policy
requirements. A zero initial state is meaningful only under the declared
no-arrivals premise. Equality with a represented finite limit passes; exceeding
it denies. These budget comparisons do not add a numerical epsilon.

The common envelope must also clear the evaluator's subcritical threshold with
its declared numerical margin. Separate subcritical snapshots do not establish
this condition. Conversely a finite sum can exist for a supercritical matrix;
subcriticality here is a conservative admission policy, not necessary for every
finite-horizon acceptable outcome. No infinite-horizon numerical total is
reported and no real-world infinite-horizon claim follows from finite evidence.

The spectral-radius/norm distinction and convergence criterion are summarized
by [Higham](https://nhigham.com/2024/01/12/what-is-the-spectral-radius-of-a-matrix/).
The domination induction and exact rational regression oracles above are the
explicit proof obligations of this reference implementation.

## Binding and Policy

`TemporalContract` binds mode, generation count, model, profile, full horizon,
operators, envelope, initial upper state, units, generation/arrival semantics,
evidence hash/source/scope and validity window. SHA-256 identity includes each
represented matrix/vector value in `float.hex()` form. Hashes are integrity
references, not signatures or empirical validation. A contract's evidence must
declare `joint_generation_envelope` and cover the entire decision horizon.
Generation count is a separate explicit bound; seconds are never converted to
generations by this library. The deployment must justify the count and enforce
the declared horizon, initial-state bound, family and absence of new arrivals.

`AutonomyBudget.temporal_policy` requires mode, generation count, maximum peak
and cumulative activations. A request cannot reduce the required count, change
mode or omit the contract. A supplied contract without a policy is also rejected.
FastGate caches bind both the contract and policy digests; fallback retains the
same temporal gate. Increment and temporal contracts do not automatically
establish joint statistical coverage of their combined claims.

Legacy requests without a temporal policy/contract retain snapshot-only
behavior, labelled `temporal_scope=not_evaluated`. Context/certificate v0.2 cannot
carry temporal proof: serialization, semantic admission and certificate building
from a temporally scoped context reject it explicitly. Standalone temporal
evaluation is a conditional model check, never admission or a certificate.

Reference resource limits are 64 nodes, 64 family members and 256 generations.
These bound verification work, not calibrated operational risk; exceeding them
requires a separately reviewed implementation and never silently truncates.

## Acceptance Criteria

- A nilpotent DAG with large transient edges fails peak/cumulative limits even
  though its radius is zero. Orientation is verified with asymmetric operators.
- Individually nilpotent switching operators fail the common-envelope gate
  when their joint envelope is supercritical. A subcritical common envelope
  bounds every enumerated switching word in independent rational oracles.
- Bounds include generation zero, cannot decrease through rounding and reject
  overflow. Zero, reducible, boundary and unsupported-input cases are tested.
- Missing policy/contract, count/mode mismatch, stale/short evidence windows,
  matrix/graph/profile/horizon changes, object mutation and stale cache fail.
- Main evaluator, exact/Collatz FastGate and fallback cannot bypass the gate.
- Versioned schema/typed fixtures, legacy rejection, complete source tests and
  installed wheel/sdist replay are tied to an exact public-safe source snapshot.
- Empirical joint coverage, loss estimation, performance qualification,
  independent review and production authority remain separate open gates.
