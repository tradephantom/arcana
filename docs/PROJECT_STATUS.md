# ARCANA Project Status

As of: 2026-10-30. Scope: public research/reference only.

This is the current navigation index. Dated release notes and paper artifacts
describe their own revisions, not later code. PRD v0.2 remains the public scope
contract; the public roadmap carries the corrective sequence.

| Surface | State |
| --- | --- |
| Archived software | v0.1.1 at `ca14464a19a9dfaedbb8b3c76bd0d030df6f13b5`, unchanged; superseded by v0.1.2 because it can under-report extreme spectral radii |
| Archived preprint | Paper v1.0, DOI `10.5281/zenodo.21333463`, unchanged |
| R1 | Numerical/input correction merged by PR #3 at `aaed2db55d889b43714135bfb9774e7ae46f4e9b`; post-merge checks passed |
| R2 | PR #4 merged at `be4383c1d5b4cdc9a1b1d3e49627db5ceab8dd17`; post-merge local reproduction and CI passed |
| Corrective release | v0.1.2 ships R1 and R2; see [Release Notes v0.1.2](PUBLIC_RELEASE_NOTES_v0.1.2.md) |
| R3 | Documentation/test-only review frozen at local `add731e`; its runtime is R2; independent review remains open |
| R3.1 | Implemented local unreleased conditional increment scope, lower-baseline accounting and evaluator/cache binding; exact source and installed replay are required for acceptance |
| R3.2 | Implemented local conditional generation model, common-envelope and finite activation gates; exact source and installed replay are required for acceptance |
| R3.3 | Implemented local conditional finite-family coverage contract, exact arbitrary-dependence composition, scope/policy/cache binding and fail-closed empirical requirement; exact source and installed replay are required for acceptance |
| Next technical gate | R3.4 typed loss contract and supported estimator after R3.3 local acceptance; independent review, CI and release approvals remain distinct |
| Empirical authority | Synthetic benchmark only; no new empirical A2/A3 evidence |
| Production authority | Not provided by this repository or by a green test run |

## Current Contracts

1. [Public PRD](ARCANA_PRD_v0.2_Public.md)
2. [Public Roadmap](ARCANA_Roadmap_v0.1_Public.md)
3. [Numerical Contract v1](NUMERICAL_CONTRACT_v1.md)
4. [Installed Package Contract](PACKAGE_PORTABILITY.md)
5. [Corrective Review Packet](CORRECTIVE_REVIEW_PACKET.md)
6. [Limitations](LIMITATIONS_v0.1.md)
7. [R3 Technical and Claim Review](R3_TECHNICAL_CLAIM_REVIEW.md)
8. [Corrective Manuscript Review Draft](ARCANA_Corrective_Manuscript_Review_Draft.md)
9. [Independent Reviewer Record](R3_REVIEWER_RECORD_TEMPLATE.md)
10. [Increment Contract v1](INCREMENT_CONTRACT_v1.md)
11. [Temporal Contract v1](TEMPORAL_CONTRACT_v1.md)
12. [Joint Coverage Contract v1](COVERAGE_CONTRACT_v1.md)

The numerical contract supersedes unchecked spectral-estimate interpretations
for corrected source. It bounds the represented matrix, not calibration truth
or real-world safety. Old benchmark report hashes cannot identify the corrected
evaluator; corrected reports bind its numerical and resource modules as well.

## Identity Discipline

Package metadata and the runtime version identify `0.2.0.dev0`, an UNRELEASED
development candidate that adds the R3 contracts on top of the v0.1.2 release.
Always bind its exact source snapshot and wheel hash; the development version
alone is not a source identity. No package upload, release tag or archive
submission is authorized by this development version increment.

The v1.0 manuscript, `paper/PUBLICATION.json`, `paper/SOURCE.json` and LaTeX
inputs preserve published attribution and archive provenance. Their
historical metadata must not be silently rewritten to describe R1/R2.
`CITATION.cff` describes the latest software release (v0.1.2, Zenodo DOI
`10.5281/zenodo.23804154`) and keeps the v1.0 preprint as preferred citation.
ARCANA has no dedicated website. The repository is its canonical project URL;
`https://getaxcp.com` identifies the related AXCP project, not an ARCANA site.

Preprint deposit and author metadata are complete for v1.0. Independent peer
review, venue acceptance, review of the corrective revision, and a new-version
submission decision remain separate. No production integration is distributed
here; AXCP Core remains independently usable and external integration optional.
