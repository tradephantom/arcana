# ARCANA Public Release Notes v0.1.2

> Release class: corrective numerical and security release
> Release date: set when the maintainer publishes the `v0.1.2` tag
> Paper DOI: 10.5281/zenodo.21333463 (paper v1.0, unchanged)
> Claim boundary: research/reference only; no production authority

## Why This Release Exists

`v0.1.1` computed spectral radii with an unchecked floating-point
eigensolver. For extremely scaled nonnegative matrices that estimate could
fall below the true spectral radius, so the reference evaluator could return
an allow-like verdict for a critical or supercritical input.

Example: `K_upper = [[0, 1e300], [1e-300, 0]]` has spectral radius `1`.
`v0.1.1` reports `0.0` and returns `allow_bounded_autonomy` at threshold
`0.8`. `v0.1.2` reports a verified upper endpoint of `1.0000000000000002`
and denies with `ARCANA_DENY_RHO_UPPER_BOUND`.

Anyone evaluating `v0.1.1` should upgrade. Details are published through the
repository Security Advisories page.

## Numerical Corrections (R1, PR #3)

- Spectral bounds are verified enclosures: exact rational Collatz-Wielandt
  ratios, strongly connected component decomposition, and outward rounding to
  binary64. Eigensolver output is only a candidate and never a certificate.
- `spectral_radius()` keeps its name but returns the verified upper endpoint.
  It can be loose and must not be reported as an exact eigenvalue.
- Admission requires `upper + margin < threshold`. Equality and values within
  the declared margin deny; a zero threshold admits nothing.
- Matrix input rejects non-real, non-finite, negative, overflowing and erased
  nonzero entries. Matrix storage is immutable and decisions evaluate a
  validated snapshot.
- The FastGate spectral increment is bounded by `after_upper - before_lower`
  with upward rounding.
- `docs/NUMERICAL_CONTRACT_v1.md` and `tests/fixtures/numerical_contract_v1.json`
  define the corrected contract.

## Packaging and Provenance (R2, PR #4)

- Installed wheels and sdist builds carry their schemas and examples and verify
  resource provenance; `make package-check` tests installs outside the checkout.
- Benchmark reports bind the numerical and resource modules. Report hashes
  produced by `v0.1.1` do not identify the corrected evaluator.
- `docs/PROJECT_STATUS.md` and `docs/CORRECTIVE_REVIEW_PACKET.md` describe the
  corrected source and its review state.

## Compatibility

- Decisions at exact threshold equality now deny.
- Benchmark report hashes differ from `v0.1.1`.
- Public schemas and reason codes are unchanged.

## Review Status

This release ships a correction for an input class on which `v0.1.1` can fail
open. The corrected source passed local and hosted CI gates. It has not yet
received the independent review described in `docs/CORRECTIVE_REVIEW_PACKET.md`;
that review remains open.

## Not Included

- The R3 increment, temporal and coverage contracts, which are under separate
  review.
- Any change to the archived paper v1.0. A manuscript correction is a separate
  decision.

## Known Limitations

- The spectral radius of an acyclic propagation graph is zero regardless of edge
  weights. A spectral bound alone does not limit single-step or transient risk.
- Autonomy budgets are evaluated per request. Integrations must evaluate each
  request against their committed graph state.

## Local Verification

```sh
make check
make test
make demo
make paper-check
make package-check
```

The distributed source archive and wheel must be tied to the exact `v0.1.2`
release commit.
