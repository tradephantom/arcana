# ARCANA Numerical Contract v1

Status: unreleased corrective reference contract, 2026-09-10.
Identifier: `arcana.numerical.v1`.
Computed decision and FastGate metrics carry this numerical contract identifier.
Applies to the working reference implementation, not retroactively to archived
releases or the v1.0 preprint. This is not an empirical calibration claim or a
production authorization.

## Represented Input

The numerical object is a finite, nonnegative, nonempty square binary64 matrix.
An interval bundle additionally requires entrywise ordering, equal dimensions,
equal node ordering and matching graph bindings. All construction paths validate
these invariants; decision evaluation creates a validated defensive snapshot.
Matrix storage uses an immutable bytes backing buffer. Input conversion rejects
non-real types, non-finite values, negative values, overflow and erased nonzero
entries. Ordinary rounding into binary64 is not a statistical uncertainty bound:
calibration must provide conservative matrices at this representation boundary.

## Verified Enclosures

`spectral_bounds(K)` returns `lower <= rho(K) <= upper` for the represented
matrix. `spectral_radius(K)` retains its API name for compatibility but now
returns the **verified upper endpoint**, not an unchecked eigensolver estimate.
An upper endpoint can be loose; it must not be reported as an exact eigenvalue.

For any strictly positive vector `x`, the row ratios `(K*x)[i]/x[i]` enclose
the spectral radius between their minimum and maximum. One way to see the
upper bound is to diagonally rescale by `x`: the infinity norm is the maximum
row ratio and dominates the spectral radius. The lower row-ratio bound follows
from nonnegative matrix iteration. Strongly connected components put a
reducible matrix into block triangular form; its spectral radius is the maximum
of the component radii. Singleton components use their diagonal entry exactly.
Consequently a DAG has spectral radius zero, regardless of large transient edges.

Each input float and candidate vector entry is converted to an exact rational.
Products, sums and row-ratio divisions used for certification are exact rational
operations. Conversion of final endpoints to binary64 is outward: down for the
lower endpoint, up for the upper endpoint, checked against the rational value.
Thus intermediate overflow or underflow cannot silently erase propagation.

NumPy eigenvectors are only optional candidates. Failed, inaccurate or nonpositive
candidates cannot certify a bound. An 80-digit decimal, geometrically damped
positive iteration provides additional candidates, with at most 128 iterations
per nonsingleton component. Its convergence is not a premise of correctness:
only independently verified rational bounds are retained. Wide finite enclosures
remain conservative. An endpoint outside binary64 range produces the explicit
`spectral_bound_unrepresentable` validation issue and cannot authorize admission.

These checks verify numerical enclosures, not calibration coverage, real-world
risk probabilities, formal software correctness or absolute safety.

## Decision and Increment Semantics

For a bundle, `rho_lower` is a verified lower endpoint for `K_lower`,
`rho_upper` is a verified upper endpoint for `K_upper`, and `rho_mean` is a
non-authoritative midpoint estimate from the `K_mean` enclosure, clipped into
the enclosing interval. Admission uses only the verified upper endpoint.

Admission requires `upper + margin < threshold`. Equality and values within the
declared margin do not pass. The margin is rounded upward and the comparison
uses exact rational addition of the represented values. The default absolute
and relative margins remain `1e-12`; these are reference numerical separation
parameters, not calibrated production risk thresholds. Zero threshold permits
no admission. Numerical uncertainty is handled by the enclosure, not by assuming
that an epsilon repairs an arbitrary eigensolver error.

FastGate certifies positive-vector ratios using the same exact arithmetic.
Its after-matrix addition rounds each changed entry upward. The incremental
spectral budget is bounded by `max(0, after_upper - before_lower)`, with upward
rounding. Subtracting a before **upper** bound would not establish an upper
bound on the increment. A loose enclosure can therefore require a larger budget
or deny an otherwise subcritical request. The `exact_recompute` mode name means
full recomputation rather than cached incremental evaluation; it does not mean
symbolically exact eigenvalues. The reference still computes a baseline bound
and is not a demonstrated low-latency implementation.

## Verification and Compatibility

The public corpus `tests/fixtures/numerical_contract_v1.json` defines seven
default threshold cases and six matrix-admission cases. Other implementations
may use different verified algorithms and can reject additional inconclusive
cases; matching this corpus is not general behavioral equivalence.

Regression coverage includes the extreme two-cycle formerly reported as zero,
subnormal self-loops, critical equality, reducible blocks, large DAG edges,
diagonal similarity across extreme scales, broken eigensolver candidates,
immutable input storage, bundle corruption, interval ordering, Collatz scaling,
unrepresentable endpoints and conservative FastGate increments. A seeded set of
128 two-by-two matrices is checked against its characteristic polynomial using
exact rational inequalities, separately from the numerical implementation.

Run `make test`, `make check`, `make demo` and `make paper-check` locally.
Archival manifests, preprint source bindings and prior release artifacts remain
unchanged. A new release and manuscript correction review are separate gates.

## References

- [Python Fraction documentation](https://docs.python.org/3/library/fractions.html):
  exact conversion of represented floating-point values to rational numbers.
- [Collatz-Wielandt quotient](https://arxiv.org/abs/1710.07402):
  mathematical context for positive-vector spectral characterizations.
