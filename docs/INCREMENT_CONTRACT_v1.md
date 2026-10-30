# Increment Contract v1

Status: unreleased R3.1 reference contract, conditional on declared premises.
Wire version: `arcana.increment.v1`. No production or empirical approval.

## Scope and Proof Obligation

For finite entrywise nonnegative represented matrices, let verified numerical
bounds satisfy `l(B) <= rho(B) <= u(B)`. Two distinct budget scopes are supported:

- `upper_model`: charge `max(0, u(U_after) - l(U_before))`. This bounds the
  positive spectral increment of the two represented upper models only.
- `calibration_envelope`: charge `max(0, u(U_after) - l(L_before))`. If the
  initial lower matrix is absent, use zero and label that choice explicitly.

The second bound is valid conditional on the joint premises
`0 <= L_before <= K_before <= U_before` and `0 <= K_after <= U_after`.
Monotonicity of the Perron root implies `rho(K_before) >= rho(L_before)` and
`rho(K_after) <= rho(U_after)`. Subtraction and positive-part monotonicity give
the stated bound. Numerical endpoints and subtraction are rounded outward for
the represented binary64 inputs. FastGate may substitute its verified Collatz
upper endpoint for `u(U_after)`. It never substitutes an upper endpoint for the
initial lower endpoint. Negative increments never credit the budget.

This is an enclosure, not an exact worst-case optimization. A wide interval
can incur a positive charge even for identical upper snapshots. A missing lower
matrix is not invented from the initial upper matrix. No temporal stability,
loss bound, independence or joint statistical coverage follows from this test.

## Binding and Trust

`IncrementContract` binds scope, model, profile, complete decision horizon,
before/after `IncrementSnapshot` hashes, evidence hash/source/scope and a
timezone-aware validity window. Snapshot identity hashes graph identity, node
order and each matrix entry's represented `float.hex()` value. The binding uses
canonical ASCII JSON and SHA-256; it is an integrity reference, not a signature,
authority credential or proof that evidence is true. Evaluators revalidate
snapshots and digests before acting. Coordinates must agree across the pair;
each supplied lower endpoint must be entrywise below its upper endpoint.

Evidence scope is `represented_snapshot_pair` for upper-model accounting and
`joint_before_after_envelope` for calibration-envelope accounting. Results label
evidence assurance `declared_premises_not_empirically_verified`. These strings
cannot upgrade calibration. Callers must supply authorized budgets, matrices,
profiles and actual evidence from outside the reference library's trust boundary.

The budget's `increment_scope` is the required scope, not a caller-selected
fallback. Missing contracts, scope mismatches, scalar overrides, stale evidence,
matrix changes and inconsistent model/profile/horizon bindings fail closed.
FastGate also binds the contract to its actual before matrix and outward-rounded
after update, evidence identity and cache scope/digest. Exact fallback retains
the same contract. Cache binding does not skip recomputation.

## Compatibility

Unscoped main-evaluator requests retain their legacy scalar behavior, explicitly
labelled `legacy_caller_declared`; omission means zero only on that legacy path.
Unscoped FastGate retains represented-upper-model accounting, without acquiring
a calibration-envelope claim. New callers should select a scope explicitly.

`evaluate_increment` computes from a typed contract and time; it accepts no
caller-computed spectral endpoint. Both decision APIs accept the typed contract
through `increment`. Their metrics retain scope, hashes, endpoints, baseline
source and conditional assurance even when a computed increment exhausts budget.

Context/certificate schema v0.2 cannot carry this new proof contract. Its
serialization and semantic admission reject scoped budgets explicitly; there
is no lossy conversion into an old certificate. A future proof-carrying artifact
version requires separate design and review. Archived papers and releases are
unchanged by this contract.

## Acceptance Criteria

- Reproduce C02 analytically: upper-model charge can be below a compatible
  latent-model increment; the calibration-envelope path must reject that budget.
- Test useful nonzero lower endpoints, absent-lower zero, no-change wide
  intervals, decreasing matrices, reducible cases and outward rounding.
- Test main evaluator, exact FastGate, Collatz FastGate and exact fallback with
  the same scope; reject forged scalar overrides and contract/cache mismatches.
- Exercise typed/schema round trips, malformed intervals, time windows, node
  order, hash tampering, direct object mutation and legacy artifact rejection.
- Replay full tests, synthetic demo, benchmark verification, public manifest
  audit and both installed distribution paths; bind evidence to exact source.
- Leave independent review, empirical qualification, temporal/loss findings and
  release approval open until their distinct gates are met.
