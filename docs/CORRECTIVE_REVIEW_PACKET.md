# Corrective Review Packet

Date: 2026-09-10. Status: PREPARED_NOT_INDEPENDENTLY_REVIEWED.

## Review Identity

Review the exact corrected source, not only the archived v0.1.1/preprint.
The R1 merge base is `aaed2db55d889b43714135bfb9774e7ae46f4e9b`; R2 adds
portable distributions, full runtime benchmark provenance and current-state
navigation. That base commit alone does NOT identify R2.

A candidate handoff must include a complete source-file SHA-256 manifest,
source archive hash, base revision, dirty-state declaration, dependency
versions, local test transcript and installed-package receipt. Before approval
or release, bind these bytes to a clean immutable commit and rerun the gates.
The current local packet is preparation evidence, not external review approval.

## Reading and Reproduction

1. Read `PROJECT_STATUS.md`, the public PRD, roadmap and limitations.
2. Read `NUMERICAL_CONTRACT_v1.md` and inspect `_numerics.py`, `matrices.py`,
   `decision.py`, `fastgate.py` and their regression tests.
3. Read `PACKAGE_PORTABILITY.md`; inspect resources, benchmark provenance and
   the isolated distribution gate.
4. Create a clean venv; install `.[dev]`; run `make check test demo paper-check`
   and `make package-check`. Record Python, dependency and toolchain versions.
5. Challenge rather than copy fixture expectations; reproduce adversarial
   numerical cases with an independent exact/analytic oracle.

## Reviewer Acceptance Checklist

- [ ] Named reviewer, relevant expertise, conflicts and automated-tool use disclosed.
- [ ] Exact source identity verified; no unreviewed changes after review.
- [ ] Verified endpoints enclose the represented nonnegative matrix spectrum.
- [ ] Extreme scaling, reducible graphs, DAGs, subnormal values, overflow,
      convergence failure and threshold equality are treated conservatively.
- [ ] FastGate uses a lower before bound for incremental upper accounting;
      rounding, graph updates and fallback decisions do not understate risk.
- [ ] Direct typed construction cannot bypass input validation or immutability.
- [ ] The distinction between model validity and calibration validity is explicit.
- [ ] Clean installed wheels reproduce source results and reject provenance tamper.
- [ ] Missing resources never silently use unrelated local or remote data.
- [ ] Synthetic benchmark scenarios are not treated as empirical A2/A3 evidence.
- [ ] Revised manuscript language explains changed spectral semantics and
      limitations; historical v1.0 publication is not retrospectively changed.
- [ ] Findings have severity, reproducer, disposition and verification evidence.
- [ ] Independent decision is recorded as pass, corrections required or fail.

All checklist items remain unapproved until an accountable reviewer supplies
evidence. Implementation tests are not reviewer signatures. A review with
unresolved material findings cannot authorize a corrective release.

## Publication Boundary

Only public-manifest-approved source and synthetic data belong in the handoff.
No customer evidence, deployment configuration, private adapter code, private
calibration profiles or commercial control-plane details may be included.
Release, preprint revision, external peer review and production qualification
are distinct gates. This packet authorizes none of them.
